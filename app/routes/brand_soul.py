from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.services.brand_soul import BrandSoulService

brand_soul_bp = Blueprint('brand_soul', __name__)


@brand_soul_bp.route('/')
@login_required
def index():
    service = BrandSoulService()
    brand_soul = service.get_or_create_brand_soul(current_user.tenant_id)
    context = {
        'brand_soul': brand_soul,
        'icp': brand_soul.get_icp_data(),
        'website_sections': brand_soul.get_website_sections(),
        'social_highlights': brand_soul.get_social_media()
    }
    return render_template('brand_soul/index.html', **context)


@brand_soul_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    service = BrandSoulService()
    tenant = current_user.tenant
    try:
        brand_data = service.analyze_brand(tenant)
        icp_data = service.analyze_icp(tenant)
        service.save_brand_soul(
            tenant_id=tenant.id,
            soul_content=brand_data.get('brand_soul_document', ''),
            icp_data=icp_data,
            social_media=brand_data.get('social_highlights', []),
            website_sections=brand_data.get('website_sections', []),
            analyzed_at=datetime.utcnow()
        )
        flash('Brand Soul updated using the latest analysis.', 'success')
    except Exception as exc:
        print(f"Brand soul analysis failed: {exc}")
        flash('Unable to analyze the brand right now. Please try again soon.', 'error')
    return redirect(url_for('brand_soul.index'))


@brand_soul_bp.route('/save', methods=['POST'])
@login_required
def save():
    service = BrandSoulService()
    section = request.form.get('section', 'brand')
    tenant_id = current_user.tenant_id
    try:
        if section == 'icp':
            icp_payload = {
                'who_for': request.form.get('who_for', ''),
                'problems_solved': request.form.get('problems_solved', ''),
                'customer_profile': request.form.get('customer_profile', ''),
                'needs': request.form.get('needs', ''),
                'aspirations': request.form.get('aspirations', '')
            }
            service.save_brand_soul(tenant_id, icp_data=icp_payload)
            flash('ICP research saved.', 'success')
        else:
            soul_content = request.form.get('brand_soul_content', '').strip()
            service.save_brand_soul(tenant_id, soul_content=soul_content)
            flash('Brand Soul document saved.', 'success')
    except Exception as exc:
        print(f"Brand soul save failed: {exc}")
        flash('Unable to save changes right now. Please try again.', 'error')
    return redirect(url_for('brand_soul.index'))
