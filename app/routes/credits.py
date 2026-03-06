"""Credits/billing routes"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.services.credit_tracker import CreditTracker

credits_bp = Blueprint('credits', __name__)

@credits_bp.route('/')
@login_required
def index():
    """Show credit balance and usage"""
    tenant_id = current_user.tenant_id
    
    # Get current balance
    credit_data = CreditTracker.get_tenant_credits(tenant_id)
    
    # Get usage summary
    usage_summary = CreditTracker.get_usage_summary(tenant_id, days=30)
    
    return render_template('credits/index.html',
                         balance=credit_data['balance'],
                         transactions=credit_data['transactions'],
                         costs=credit_data['costs'],
                         usage=usage_summary)

@credits_bp.route('/api/balance')
@login_required
def api_balance():
    """API endpoint for current balance"""
    tenant_id = current_user.tenant_id
    credit_data = CreditTracker.get_tenant_credits(tenant_id)
    return jsonify(credit_data['balance'])
