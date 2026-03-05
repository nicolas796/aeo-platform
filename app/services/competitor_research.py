"""Competitor analysis and research service"""
import requests
from typing import Dict, List
from flask import current_app
from app.models import db, Competitor, Keyword, Tenant


class CompetitorResearchService:
    """Research competitor websites and discover their keywords/content"""

    def __init__(self):
        self.gemini_api_key = None

    def _get_gemini_key(self):
        """Lazy load API key"""
        if not self.gemini_api_key:
            self.gemini_api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        return self.gemini_api_key

    def analyze_competitor(self, competitor_id: int) -> Dict:
        """Full competitor analysis - website, keywords, content gaps"""
        competitor = Competitor.query.get(competitor_id)
        if not competitor:
            return {'error': 'Competitor not found'}

        tenant = competitor.tenant

        try:
            # Step 1: Fetch and analyze competitor website
            website_analysis = self._analyze_website(competitor.website_url)

            # Step 2: Generate competitor-focused keywords
            keywords = self._generate_competitor_keywords(competitor, tenant, website_analysis)

            # Step 3: Identify content gaps vs brand
            gaps = self._identify_content_gaps(competitor, tenant, website_analysis)

            return {
                'competitor_name': competitor.name,
                'website_analysis': website_analysis,
                'suggested_keywords': keywords,
                'content_gaps': gaps,
                'status': 'success'
            }

        except Exception as e:
            return {'error': str(e), 'status': 'failed'}

    def _analyze_website(self, url: str) -> Dict:
        """Analyze competitor website content using Gemini"""
        import os

        # Try to fetch website content
        try:
            # Use requests as fallback since web_fetch might not be available
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; AEOBot/1.0)'}
            response = requests.get(url, headers=headers, timeout=10)
            content = response.text[:5000]  # First 5000 chars
        except:
            content = f"Website URL: {url}"

        # Use Gemini to analyze
        api_key = self._get_gemini_key()
        if not api_key:
            return {'error': 'No API key available'}

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

        prompt = f"""Analyze this competitor website and extract:
1. Main value proposition (what they do)
2. Target audience
3. Key products/services mentioned
4. Main topics they cover
5. Content themes

Website content (first part):
{content[:3000]}

Return as JSON:
{{
  "value_proposition": "...",
  "target_audience": "...",
  "products_services": ["...", "..."],
  "content_topics": ["...", "..."],
  "content_themes": ["...", "..."]
}}"""

        try:
            response = requests.post(
                gemini_url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    text = data['candidates'][0]['content']['parts'][0]['text']
                    # Extract JSON
                    import json
                    import re
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())

        except Exception as e:
            print(f"Gemini analysis error: {e}")

        # Fallback
        return {
            'value_proposition': f'Analysis of {url}',
            'target_audience': 'General audience',
            'products_services': [],
            'content_topics': [],
            'content_themes': []
        }

    def _generate_competitor_keywords(self, competitor: Competitor, tenant: Tenant, analysis: Dict) -> List[Dict]:
        """Generate keywords focused on competitor comparisons"""

        brand_name = tenant.name
        competitor_name = competitor.name
        topics = analysis.get('content_topics', [])

        # Generate comparison keywords
        keywords = [
            {
                'prompt_text': f"{brand_name} vs {competitor_name}",
                'category': 'comparison',
                'relevance_score': 5.0,
                'intent_score': 5.0
            },
            {
                'prompt_text': f"{competitor_name} vs {brand_name}",
                'category': 'comparison',
                'relevance_score': 5.0,
                'intent_score': 5.0
            },
            {
                'prompt_text': f"{competitor_name} alternatives",
                'category': 'comparison',
                'relevance_score': 4.5,
                'intent_score': 4.5
            },
            {
                'prompt_text': f"Best alternative to {competitor_name}",
                'category': 'comparison',
                'relevance_score': 4.5,
                'intent_score': 4.5
            },
            {
                'prompt_text': f"Is {competitor_name} better than {brand_name}?",
                'category': 'comparison',
                'relevance_score': 4.0,
                'intent_score': 4.5
            }
        ]

        # Add topic-based keywords
        for topic in topics[:3]:
            keywords.append({
                'prompt_text': f"{topic} - {brand_name} vs {competitor_name}",
                'category': 'comparison',
                'relevance_score': 4.0,
                'intent_score': 4.0
            })

        return keywords

    def _identify_content_gaps(self, competitor: Competitor, tenant: Tenant, analysis: Dict) -> List[Dict]:
        """Identify content gaps where competitor has coverage but brand doesn't"""

        # Get brand's existing keywords
        brand_keywords = Keyword.query.filter_by(tenant_id=tenant.id, active=True).all()
        brand_topics = set(kw.prompt_text.lower() for kw in brand_keywords)

        gaps = []

        # Check competitor's topics against brand's coverage
        for topic in analysis.get('content_topics', []):
            topic_lower = topic.lower()
            # Check if brand covers this topic
            has_coverage = any(topic_lower in bk or bk in topic_lower for bk in brand_topics)

            if not has_coverage:
                gaps.append({
                    'topic': topic,
                    'competitor_covers': True,
                    'brand_covers': False,
                    'opportunity': f"Create content about '{topic}' to match competitor coverage",
                    'suggested_prompt': f"{topic} for {tenant.name}"
                })

        return gaps

    def save_competitor_keywords(self, competitor_id: int, keywords: List[Dict]):
        """Save discovered keywords to database"""
        competitor = Competitor.query.get(competitor_id)
        if not competitor:
            return

        tenant_id = competitor.tenant_id
        added = 0

        for kw_data in keywords:
            # Check if already exists
            existing = Keyword.query.filter_by(
                tenant_id=tenant_id,
                prompt_text=kw_data['prompt_text']
            ).first()

            if not existing:
                keyword = Keyword(
                    tenant_id=tenant_id,
                    prompt_text=kw_data['prompt_text'],
                    category=kw_data.get('category', 'comparison'),
                    relevance_score=kw_data.get('relevance_score', 3.0),
                    volume_score=kw_data.get('volume_score', 3.0),
                    winability_score=kw_data.get('winability_score', 3.0),
                    intent_score=kw_data.get('intent_score', 3.0)
                )
                keyword.calculate_priority()
                db.session.add(keyword)
                added += 1

        db.session.commit()
        return added
