import requests
from typing import List
from app.models import db, Keyword, Tenant
from app.services.aeo_scanner import AEOSCANNER

class KeywordResearchService:
    """Service for discovering and researching keywords"""
    
    def __init__(self):
        pass
    
    def discover_keywords(self, tenant_id: int) -> List[Keyword]:
        """Discover keywords by analyzing the tenant's website"""
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return []
        
        # Fetch website content
        try:
            from web_fetch import web_fetch
            content = web_fetch(tenant.website_url)
        except:
            # Fallback: create generic keywords based on industry
            return self._create_generic_keywords(tenant)
        
        # Parse content and extract topics
        keywords = self._extract_keywords_from_content(content, tenant)
        
        # Save to database
        for kw_data in keywords:
            existing = Keyword.query.filter_by(tenant_id=tenant_id, prompt_text=kw_data['prompt_text']).first()
            if not existing:
                keyword = Keyword(
                    tenant_id=tenant_id,
                    prompt_text=kw_data['prompt_text'],
                    category=kw_data.get('category', 'general'),
                    relevance_score=kw_data.get('relevance_score', 3.0),
                    volume_score=kw_data.get('volume_score', 3.0),
                    winability_score=kw_data.get('winability_score', 3.0),
                    intent_score=kw_data.get('intent_score', 3.0)
                )
                keyword.calculate_priority()
                db.session.add(keyword)
        
        db.session.commit()
        
        return Keyword.query.filter_by(tenant_id=tenant_id).all()
    
    def _extract_keywords_from_content(self, content: str, tenant: Tenant) -> List[dict]:
        """Extract potential keywords from website content"""
        # Simplified keyword extraction
        # In production, this would use NLP or LLM analysis
        
        industry = tenant.industry or 'general'
        company_name = tenant.name
        
        # Template-based keyword generation
        templates = {
            'technology': [
                f"What is {company_name} and what does it do?",
                f"How does {company_name} work?",
                f"{company_name} vs competitors",
                f"Best {industry} solutions for small business",
                f"How to choose {industry} software",
                f"{company_name} pricing and plans",
                f"Is {company_name} worth it?",
            ],
            'ecommerce': [
                f"What does {company_name} sell?",
                f"{company_name} reviews",
                f"Best products from {company_name}",
                f"{company_name} shipping and returns",
                f"Is {company_name} legit?",
            ],
            'services': [
                f"What services does {company_name} offer?",
                f"{company_name} pricing",
                f"Hiring {company_name} vs doing it yourself",
                f"{company_name} reviews and testimonials",
                f"How to work with {company_name}",
            ],
            'general': [
                f"What is {company_name}?",
                f"How does {company_name} work?",
                f"{company_name} reviews",
                f"Best alternatives to {company_name}",
                f"Is {company_name} worth it?",
            ]
        }
        
        prompts = templates.get(industry.lower(), templates['general'])
        
        keywords = []
        for prompt in prompts:
            keywords.append({
                'prompt_text': prompt,
                'category': 'solution-aware' if 'what is' in prompt or 'how does' in prompt else 'comparison' if 'vs' in prompt or 'alternatives' in prompt else 'evaluation',
                'relevance_score': 4.0,
                'volume_score': 3.5,
                'winability_score': 3.0,
                'intent_score': 4.0
            })
        
        return keywords
    
    def _create_generic_keywords(self, tenant: Tenant) -> List[Keyword]:
        """Create generic keywords when website can't be fetched"""
        keywords_data = self._extract_keywords_from_content("", tenant)
        
        # Save to database
        for kw_data in keywords_data:
            existing = Keyword.query.filter_by(tenant_id=tenant.id, prompt_text=kw_data['prompt_text']).first()
            if not existing:
                keyword = Keyword(
                    tenant_id=tenant.id,
                    prompt_text=kw_data['prompt_text'],
                    category=kw_data.get('category', 'general'),
                    relevance_score=kw_data.get('relevance_score', 3.0),
                    volume_score=kw_data.get('volume_score', 3.0),
                    winability_score=kw_data.get('winability_score', 3.0),
                    intent_score=kw_data.get('intent_score', 3.0)
                )
                keyword.calculate_priority()
                db.session.add(keyword)
        
        db.session.commit()
        
        return Keyword.query.filter_by(tenant_id=tenant.id).all()