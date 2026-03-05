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