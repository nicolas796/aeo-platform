import requests
import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from app.models import db, Scan, ScanResult, Keyword, Competitor, Tenant

class AEOSCANNER:
    """Service for scanning AEO visibility across AI assistants"""
    
    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        self.use_gemini = bool(self.gemini_api_key)
    
    def run_scan(self, scan_id: int):
        """Run a complete AEO scan for a scan record"""
        scan = Scan.query.get(scan_id)
        if not scan:
            return
        
        scan.status = 'running'
        db.session.commit()
        
        try:
            tenant = Tenant.query.get(scan.tenant_id)
            keywords = Keyword.query.filter_by(tenant_id=tenant.id, active=True).all()
            competitors = Competitor.query.filter_by(tenant_id=tenant.id, active=True).all()
            
            brand_names = [tenant.name, tenant.domain.replace('.com', '').replace('.io', '')]
            competitor_names = {c.domain: c.name for c in competitors}
            
            for keyword in keywords:
                result = self._scan_keyword(keyword, brand_names, competitor_names)
                
                scan_result = ScanResult(
                    scan_id=scan.id,
                    keyword_id=keyword.id,
                    mentioned=result['mentioned'],
                    cited=result['cited'],
                    sentiment=result.get('sentiment'),
                    mention_excerpt=result.get('excerpt'),
                    cited_urls=json.dumps(result.get('cited_urls', [])),
                    competitor_mentions=json.dumps(result.get('competitor_mentions', {})),
                    ai_response=result.get('response', '')[:2000],  # Limit storage
                    sources=json.dumps(result.get('sources', []))
                )
                db.session.add(scan_result)
                
                scan.completed_keywords += 1
                db.session.commit()
            
            scan.status = 'completed'
            db.session.commit()
            
            # Generate report after scan completes
            try:
                from app.services.report_generator import ReportGenerator
                generator = ReportGenerator()
                report = generator.generate_weekly_report(scan.tenant_id)
                if report:
                    print(f"Report generated for tenant {scan.tenant_id}: {report.mention_rate}% mention rate")
            except Exception as report_error:
                print(f"Failed to generate report: {report_error}")
            
        except Exception as e:
            scan.status = 'failed'
            scan.error_message = str(e)
            db.session.commit()
            raise
    
    def _scan_keyword(self, keyword: Keyword, brand_names: List[str], competitor_names: Dict[str, str]) -> Dict:
        """Scan a single keyword for brand mentions and citations"""
        
        if self.use_gemini:
            return self._scan_with_gemini(keyword, brand_names, competitor_names)
        else:
            return self._scan_with_web_search(keyword, brand_names, competitor_names)
    
    def _scan_with_gemini(self, keyword: Keyword, brand_names: List[str], competitor_names: Dict[str, str]) -> Dict:
        """Use Gemini API with grounding to check visibility"""
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": keyword.prompt_text}]
            }],
            "tools": [{
                "googleSearch": {}
            }]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract response text
            ai_text = ""
            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if 'text' in part:
                            ai_text += part['text']
            
            # Extract grounding chunks (sources)
            sources = []
            cited_urls = []
            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'groundingMetadata' in candidate:
                    metadata = candidate['groundingMetadata']
                    if 'groundingChunks' in metadata:
                        for chunk in metadata['groundingChunks']:
                            if 'web' in chunk:
                                web_data = chunk['web']
                                sources.append({
                                    'title': web_data.get('title', ''),
                                    'uri': web_data.get('uri', '')
                                })
                                cited_urls.append(web_data.get('uri', ''))
            
            # Check for brand mentions
            mentioned = False
            excerpt = ""
            text_lower = ai_text.lower()
            for brand in brand_names:
                if brand.lower() in text_lower:
                    mentioned = True
                    # Extract sentence containing brand
                    sentences = ai_text.split('.')
                    for sent in sentences:
                        if brand.lower() in sent.lower():
                            excerpt = sent.strip()
                            break
                    break
            
            # Check for citations (brand domain in sources)
            cited = False
            brand_domain = brand_names[1] if len(brand_names) > 1 else brand_names[0].lower().replace(' ', '')
            for url in cited_urls:
                if brand_domain.lower() in url.lower():
                    cited = True
                    break
            
            # Check for competitor mentions
            comp_mentions = {}
            for domain, name in competitor_names.items():
                count = text_lower.count(name.lower()) + text_lower.count(domain.lower())
                if count > 0:
                    comp_mentions[name] = count
            
            # Determine sentiment
            sentiment = self._analyze_sentiment(ai_text, brand_names)
            
            return {
                'mentioned': mentioned,
                'cited': cited,
                'sentiment': sentiment,
                'excerpt': excerpt,
                'cited_urls': cited_urls,
                'competitor_mentions': comp_mentions,
                'response': ai_text,
                'sources': sources
            }
            
        except Exception as e:
            # Fallback to web search method
            return self._scan_with_web_search(keyword, brand_names, competitor_names)
    
    def _scan_with_web_search(self, keyword: Keyword, brand_names: List[str], competitor_names: Dict[str, str]) -> Dict:
        """Fallback: Use web search to approximate visibility"""
        
        # This is a simplified fallback - in production you'd use Brave Search API
        # For now, return unknown status
        return {
            'mentioned': False,
            'cited': False,
            'sentiment': 'unknown',
            'excerpt': '',
            'cited_urls': [],
            'competitor_mentions': {},
            'response': 'Web search fallback - configure Gemini API for full scans',
            'sources': []
        }
    
    def _analyze_sentiment(self, text: str, brand_names: List[str]) -> str:
        """Simple sentiment analysis based on context"""
        text_lower = text.lower()
        
        # Find sentences mentioning brand
        sentences = text.split('.')
        brand_sentences = []
        for sent in sentences:
            for brand in brand_names:
                if brand.lower() in sent.lower():
                    brand_sentences.append(sent.lower())
                    break
        
        if not brand_sentences:
            return 'neutral'
        
        # Simple keyword-based sentiment
        positive_words = ['best', 'top', 'excellent', 'great', 'recommended', 'leading', 'popular', 'effective']
        negative_words = ['worst', 'avoid', 'poor', 'bad', 'disappointing', 'limited', 'expensive']
        
        pos_count = sum(1 for word in positive_words for sent in brand_sentences if word in sent)
        neg_count = sum(1 for word in negative_words for sent in brand_sentences if word in sent)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'