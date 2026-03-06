import json
import os
import re
from datetime import datetime
from html import unescape
from typing import Dict, Any, List, Optional

import requests
from flask import current_app

from app.models import db, BrandSoul, Tenant


class BrandSoulService:
    """Analyze and persist each tenant's brand soul + ICP research"""

    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY') or current_app.config.get('GEMINI_API_KEY')
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
            if self.gemini_api_key else None
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def get_or_create_brand_soul(self, tenant_id: int) -> BrandSoul:
        brand_soul = BrandSoul.query.filter_by(tenant_id=tenant_id).first()
        if not brand_soul:
            brand_soul = BrandSoul(
                tenant_id=tenant_id,
                brand_soul_content='',
                icp_research=json.dumps(self._default_icp_profile())
            )
            db.session.add(brand_soul)
            db.session.commit()
        return brand_soul

    def save_brand_soul(
        self,
        tenant_id: int,
        soul_content: Optional[str] = None,
        icp_data: Optional[Dict[str, Any]] = None,
        social_media: Optional[List[Dict[str, Any]]] = None,
        website_sections: Optional[List[Dict[str, Any]]] = None,
        analyzed_at: Optional[datetime] = None,
    ) -> BrandSoul:
        brand_soul = self.get_or_create_brand_soul(tenant_id)
        if soul_content is not None:
            brand_soul.brand_soul_content = soul_content
        if icp_data is not None:
            brand_soul.icp_research = json.dumps(icp_data)
        if social_media is not None:
            brand_soul.social_media_analyzed = json.dumps(social_media)
        if website_sections is not None:
            brand_soul.website_content_analyzed = json.dumps(website_sections)
        if analyzed_at:
            brand_soul.last_analyzed_at = analyzed_at
        brand_soul.updated_at = datetime.utcnow()
        db.session.commit()
        return brand_soul

    # ------------------------------------------------------------------
    # Analysis routines
    # ------------------------------------------------------------------
    def analyze_brand(self, tenant: Tenant) -> Dict[str, Any]:
        """Use Gemini to summarize brand voice from website + social content."""
        website_copy = self._fetch_website_content(tenant.website_url)
        prompt = f"""You are the keeper of a brand's soul. Analyze the brand described below
and return structured JSON.

Brand Name: {tenant.name}
Industry: {tenant.industry or 'general'}
Website: {tenant.website_url}

Website copy sample (trimmed):
\"\"\"{website_copy}\"\"\"

Instructions:
1. Summarize the brand's voice, values, promises, differentiators, and proof points. Write it as a cohesive Brand Soul document with short headings.
2. Identify the 3-5 most important website sections/pages you see. For each, capture the key message and tone.
3. Research recent social media activity for this brand (LinkedIn, Instagram, TikTok, etc.). Use the googleSearch tool to infer top-of-mind themes. Return 3-5 highlights with platform, summary, tone, and takeaway.

Return ONLY valid JSON with keys:
{{
  "brand_soul_document": "...",
  "website_sections": [{{"section": "", "insight": "", "tone": ""}}],
  "social_highlights": [{{"platform": "", "summary": "", "tone": "", "takeaway": ""}}]
}}"""

        result = self._call_gemini(prompt, tools=[{"googleSearch": {}}])
        # Ensure result is a dict and extract values safely
        if not isinstance(result, dict):
            result = {}
        brand_doc = result.get('brand_soul_document', '')
        if isinstance(brand_doc, dict):
            brand_doc = json.dumps(brand_doc)
        return {
            'brand_soul_document': str(brand_doc).strip(),
            'website_sections': result.get('website_sections', []) if isinstance(result.get('website_sections'), list) else [],
            'social_highlights': result.get('social_highlights', []) if isinstance(result.get('social_highlights'), list) else []
        }

    def analyze_icp(self, tenant: Tenant) -> Dict[str, str]:
        """Generate ICP research snapshot for the tenant."""
        prompt = f"""You are creating an ICP (ideal customer profile) brief for {tenant.name}.
Consider their industry ({tenant.industry or 'general'}) and offerings inferred from {tenant.website_url}.
Return JSON with:
- who_for: Describe the audience this brand was built for.
- problems_solved: Bullet-depth narrative of the pain points.
- customer_profile: Paint a narrative of the typical buyer (role, mindset, triggers).
- needs: What do they need to see/hear to trust the brand?
- aspirations: Desired future state once they succeed with the brand.

Write vivid language that can be pasted into a strategy doc.
Return ONLY JSON."""

        result = self._call_gemini(prompt, tools=[{"googleSearch": {}}])
        return {**self._default_icp_profile(), **result}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _call_gemini(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.endpoint:
            raise RuntimeError('Gemini API key not configured')
        payload: Dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        if tools:
            payload["tools"] = tools
        try:
            response = requests.post(self.endpoint, json=payload, timeout=60)
            if response.status_code != 200:
                print(f"Gemini error: {response.status_code} {response.text[:200]}")
                return {}
            data = response.json()
            if not data.get('candidates'):
                return {}
            text = data['candidates'][0]['content']['parts'][0].get('text', '')
            return self._extract_json(text)
        except Exception as exc:  # pragma: no cover
            print(f"Gemini request failed: {exc}")
            return {}

    def _extract_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        snippet = text.strip()
        if '```json' in snippet:
            snippet = snippet.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in snippet:
            snippet = snippet.split('```', 1)[1].split('```', 1)[0].strip()
        snippet = snippet.strip()
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            try:
                start = snippet.index('{')
                end = snippet.rindex('}') + 1
                return json.loads(snippet[start:end])
            except Exception:
                return {}

    def _fetch_website_content(self, url: Optional[str], max_chars: int = 4000) -> str:
        if not url:
            return ''
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            html = resp.text
            html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.S | re.I)
            html = re.sub(r'<style.*?>.*?</style>', '', html, flags=re.S | re.I)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = unescape(text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:max_chars]
        except Exception:
            return ''

    def _default_icp_profile(self) -> Dict[str, str]:
        return {
            'who_for': '',
            'problems_solved': '',
            'customer_profile': '',
            'needs': '',
            'aspirations': ''
        }
