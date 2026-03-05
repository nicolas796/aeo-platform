from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Competitor

competitors_bp = Blueprint('competitors', __name__)

@competitors_bp.route('/')
@login_required
def index():
    tenant_id = current_user.tenant_id
    competitors = Competitor.query.filter_by(tenant_id=tenant_id, active=True).all()
    return render_template('competitors/index.html', competitors=competitors)

@competitors_bp.route('/add', methods=['POST'])
@login_required
def add():
    tenant_id = current_user.tenant_id
    
    name = request.form.get('name', '').strip()
    domain = request.form.get('domain', '').strip()
    website_url = request.form.get('website_url', '').strip()
    
    if not name or not domain:
        flash('Name and domain are required', 'error')
        return redirect(url_for('competitors.index'))
    
    # Normalize domain
    domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
    
    competitor = Competitor(
        tenant_id=tenant_id,
        name=name,
        domain=domain,
        website_url=website_url or f'https://{domain}'
    )
    db.session.add(competitor)
    db.session.commit()
    
    flash(f'Competitor "{name}" added', 'success')
    return redirect(url_for('competitors.index'))

@competitors_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    tenant_id = current_user.tenant_id
    competitor = Competitor.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    competitor.active = False
    db.session.commit()
    
    flash('Competitor removed', 'success')
    return redirect(url_for('competitors.index'))


@competitors_bp.route('/<int:id>/analyze', methods=['POST'])
@login_required
def analyze(id):
    """Analyze competitor and generate comparison keywords"""
    tenant_id = current_user.tenant_id
    competitor = Competitor.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    from app.services.competitor_research import CompetitorResearchService
    service = CompetitorResearchService()
    
    try:
        # Run full analysis
        result = service.analyze_competitor(id)
        
        if result.get('status') == 'success':
            # Save suggested keywords
            keywords = result.get('suggested_keywords', [])
            added = service.save_competitor_keywords(id, keywords)
            
            gaps_count = len(result.get('content_gaps', []))
            
            flash(f'Analysis complete! Added {added} comparison keywords. Found {gaps_count} content gaps.', 'success')
        else:
            flash(f"Analysis failed: {result.get('error', 'Unknown error')}", 'error')
            
    except Exception as e:
        flash(f'Error analyzing competitor: {str(e)}', 'error')
    
    return redirect(url_for('competitors.index'))