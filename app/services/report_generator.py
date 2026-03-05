import json
from typing import List, Dict
from datetime import datetime, timedelta
from app.models import db, WeeklyReport, ContentSuggestion, Keyword, Scan, ScanResult, Competitor

class ReportGenerator:
    """Generate weekly AEO reports with recommendations"""
    
    def generate_weekly_report(self, tenant_id: int) -> WeeklyReport:
        """Generate a comprehensive weekly report"""
        
        # Get latest scan
        latest_scan = Scan.query.filter_by(tenant_id=tenant_id, status='completed').order_by(Scan.scan_date.desc()).first()
        
        if not latest_scan:
            return None
        
        # Get previous scan for comparison
        previous_scan = Scan.query.filter_by(tenant_id=tenant_id, status='completed').filter(Scan.id < latest_scan.id).order_by(Scan.scan_date.desc()).first()
        
        # Calculate metrics
        results = ScanResult.query.filter_by(scan_id=latest_scan.id).all()
        total = len(results)
        mentioned = sum(1 for r in results if r.mentioned)
        cited = sum(1 for r in results if r.cited)
        
        mention_rate = (mentioned / total * 100) if total > 0 else 0
        citation_rate = (cited / total * 100) if total > 0 else 0
        
        # Calculate changes
        mention_rate_change = 0
        citation_rate_change = 0
        
        if previous_scan:
            prev_results = ScanResult.query.filter_by(scan_id=previous_scan.id).all()
            prev_mentioned = sum(1 for r in prev_results if r.mentioned)
            prev_cited = sum(1 for r in prev_results if r.cited)
            prev_total = len(prev_results)
            
            prev_mention_rate = (prev_mentioned / prev_total * 100) if prev_total > 0 else 0
            prev_citation_rate = (prev_cited / prev_total * 100) if prev_total > 0 else 0
            
            mention_rate_change = mention_rate - prev_mention_rate
            citation_rate_change = citation_rate - prev_citation_rate
        
        # Identify top performers and keywords needing attention
        top_performing = []
        needing_attention = []
        
        for result in results:
            if result.mentioned and result.cited:
                top_performing.append({
                    'keyword_id': result.keyword_id,
                    'keyword_text': result.keyword.prompt_text if result.keyword else 'Unknown',
                    'mentioned': True,
                    'cited': True
                })
            elif not result.mentioned:
                needing_attention.append({
                    'keyword_id': result.keyword_id,
                    'keyword_text': result.keyword.prompt_text if result.keyword else 'Unknown',
                    'issue': 'not_mentioned',
                    'opportunity': 'high'
                })
            elif result.mentioned and not result.cited:
                needing_attention.append({
                    'keyword_id': result.keyword_id,
                    'keyword_text': result.keyword.prompt_text if result.keyword else 'Unknown',
                    'issue': 'mentioned_not_cited',
                    'opportunity': 'medium'
                })
        
        # Competitor comparison
        competitors = Competitor.query.filter_by(tenant_id=tenant_id, active=True).all()
        competitor_data = {}
        
        for comp in competitors:
            comp_mentions = 0
            for result in results:
                comp_dict = result.get_competitor_mentions()
                if comp.name in comp_dict:
                    comp_mentions += comp_dict[comp.name]
            
            competitor_data[comp.name] = {
                'mentions': comp_mentions,
                'domain': comp.domain
            }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            mention_rate, citation_rate, 
            needing_attention, top_performing,
            competitor_data
        )
        
        # Create report
        report = WeeklyReport(
            tenant_id=tenant_id,
            total_keywords=total,
            mention_rate=mention_rate,
            citation_rate=citation_rate,
            mention_rate_change=mention_rate_change,
            citation_rate_change=citation_rate_change,
            top_performing_keywords=json.dumps(top_performing[:5]),
            keywords_needing_attention=json.dumps(needing_attention[:10]),
            competitor_comparison=json.dumps(competitor_data),
            recommendations=json.dumps(recommendations)
        )
        
        db.session.add(report)
        db.session.commit()
        
        # Generate content suggestions for high-opportunity keywords
        self._generate_content_suggestions(tenant_id, needing_attention)
        
        return report
    
    def _generate_recommendations(self, mention_rate: float, citation_rate: float, 
                                   needing_attention: List[Dict], top_performing: List[Dict],
                                   competitor_data: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Based on overall performance
        if mention_rate < 30:
            recommendations.append("Your brand mention rate is low. Focus on creating foundational content that answers basic questions about your brand.")
        elif mention_rate < 60:
            recommendations.append("Good progress on brand mentions. Now work on improving citation rate by making content more citation-worthy.")
        else:
            recommendations.append("Excellent brand visibility! Maintain your momentum and expand to new keyword categories.")
        
        if citation_rate < 20:
            recommendations.append("Citation rate needs improvement. Add more specific data, frameworks, and quotable insights to your content.")
        
        # Based on keywords needing attention
        high_opportunity = [k for k in needing_attention if k.get('opportunity') == 'high']
        if high_opportunity:
            recommendations.append(f"You have {len(high_opportunity)} high-opportunity keywords with no mentions. Prioritize creating content for: {high_opportunity[0]['keyword_text'][:50]}...")
        
        mentioned_not_cited = [k for k in needing_attention if k.get('issue') == 'mentioned_not_cited']
        if mentioned_not_cited:
            recommendations.append(f"{len(mentioned_not_cited)} keywords mention your brand but don't cite you. Refresh this content to be more citation-worthy.")
        
        # Based on competitors
        if competitor_data:
            top_competitor = max(competitor_data.items(), key=lambda x: x[1]['mentions'])
            if top_competitor[1]['mentions'] > 0:
                recommendations.append(f"{top_competitor[0]} is being mentioned frequently. Analyze their content strategy and identify gaps you can fill.")
        
        return recommendations
    
    def _generate_content_suggestions(self, tenant_id: int, needing_attention: List[Dict]):
        """Generate content suggestions for keywords needing attention"""
        
        for keyword_data in needing_attention[:5]:  # Top 5 opportunities
            keyword_id = keyword_data.get('keyword_id')
            if not keyword_id:
                continue
            
            keyword = Keyword.query.get(keyword_id)
            if not keyword:
                continue
            
            # Check if suggestion already exists
            existing = ContentSuggestion.query.filter_by(keyword_id=keyword_id, status='pending').first()
            if existing:
                continue
            
            # Generate suggestion
            title = f"How to Answer: {keyword.prompt_text}"
            
            outline = json.dumps([
                {"heading": "Introduction", "content": "Direct answer to the prompt"},
                {"heading": "Key Considerations", "content": "What factors matter most"},
                {"heading": "Best Practices", "content": "Actionable recommendations"},
                {"heading": "Common Mistakes", "content": "What to avoid"},
                {"heading": "Conclusion", "content": "Summary and next steps"}
            ])
            
            key_points = json.dumps([
                "Lead with a clear, quotable answer",
                "Include specific examples and data",
                "Address related sub-questions",
                "Use descriptive headings"
            ])
            
            unique_angle = f"Create the definitive guide for '{keyword.prompt_text}' with original insights and specific examples that AI assistants will want to cite."
            
            suggestion = ContentSuggestion(
                tenant_id=tenant_id,
                keyword_id=keyword_id,
                title=title,
                outline=outline,
                target_word_count=1500,
                key_points=key_points,
                unique_angle=unique_angle,
                status='pending'
            )
            
            db.session.add(suggestion)
        
        db.session.commit()