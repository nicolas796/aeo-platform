from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Keyword
from app.services.keyword_research import KeywordResearchService

keywords_bp = Blueprint('keywords', __name__)

@keywords_bp.route('/')
@login_required
def index():
    tenant_id = current_user.tenant_id
    keywords = Keyword.query.filter_by(tenant_id=tenant_id).order_by(Keyword.priority_score.desc()).all()
    return render_template('keywords/index.html', keywords=keywords)

@keywords_bp.route('/add', methods=['POST'])
@login_required
def add():
    tenant_id = current_user.tenant_id
    
    prompt_text = request.form.get('prompt_text', '').strip()
    category = request.form.get('category', '').strip()
    
    if not prompt_text:
        flash('Prompt text is required', 'error')
        return redirect(url_for('keywords.index'))
    
    # Check for duplicates
    existing = Keyword.query.filter_by(tenant_id=tenant_id, prompt_text=prompt_text).first()
    if existing:
        flash('This keyword is already being tracked', 'error')
        return redirect(url_for('keywords.index'))
    
    keyword = Keyword(
        tenant_id=tenant_id,
        prompt_text=prompt_text,
        category=category
    )
    db.session.add(keyword)
    db.session.commit()
    
    flash('Keyword added successfully', 'success')
    return redirect(url_for('keywords.index'))

@keywords_bp.route('/discover', methods=['POST'])
@login_required
def discover():
    """Auto-discover keywords based on website analysis"""
    tenant_id = current_user.tenant_id
    
    service = KeywordResearchService()
    try:
        keywords = service.discover_keywords(tenant_id)
        flash(f'Discovered {len(keywords)} new keywords from your website', 'success')
    except Exception as e:
        flash(f'Error discovering keywords: {str(e)}', 'error')
    
    return redirect(url_for('keywords.index'))

@keywords_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    tenant_id = current_user.tenant_id
    keyword = Keyword.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    keyword.active = False
    db.session.commit()
    
    flash('Keyword removed from tracking', 'success')
    return redirect(url_for('keywords.index'))

@keywords_bp.route('/<int:id>/score', methods=['POST'])
@login_required
def score(id):
    """Update keyword scores"""
    tenant_id = current_user.tenant_id
    keyword = Keyword.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    keyword.relevance_score = float(request.form.get('relevance_score', 0))
    keyword.volume_score = float(request.form.get('volume_score', 0))
    keyword.winability_score = float(request.form.get('winability_score', 0))
    keyword.intent_score = float(request.form.get('intent_score', 0))
    keyword.calculate_priority()
    
    db.session.commit()
    
    return jsonify({'success': True, 'priority_score': keyword.priority_score})