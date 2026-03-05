from flask import Blueprint, render_template, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import Keyword, Scan, WeeklyReport, Competitor
from sqlalchemy import func
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    tenant_id = current_user.tenant_id
    
    # Get stats
    total_keywords = Keyword.query.filter_by(tenant_id=tenant_id, active=True).count()
    total_competitors = Competitor.query.filter_by(tenant_id=tenant_id, active=True).count()
    
    # Get latest scan
    latest_scan = Scan.query.filter_by(tenant_id=tenant_id).order_by(Scan.scan_date.desc()).first()
    
    # Get latest report
    latest_report = WeeklyReport.query.filter_by(tenant_id=tenant_id).order_by(WeeklyReport.report_date.desc()).first()
    
    # Calculate mention and citation rates from latest report
    mention_rate = latest_report.mention_rate if latest_report else 0
    citation_rate = latest_report.citation_rate if latest_report else 0
    
    # Calculate next scheduled scan
    next_scan = _calculate_next_scan(latest_scan)
    
    return render_template('dashboard/index.html',
                         tenant=current_user.tenant,
                         total_keywords=total_keywords,
                         total_competitors=total_competitors,
                         latest_scan=latest_scan,
                         latest_report=latest_report,
                         mention_rate=mention_rate,
                         citation_rate=citation_rate,
                         next_scan=next_scan)

def _calculate_next_scan(latest_scan):
    """Calculate when the next scan is scheduled"""
    day_of_week = current_app.config.get('WEEKLY_SCAN_DAY', 'sunday').lower()
    hour, minute = current_app.config.get('WEEKLY_SCAN_TIME', '02:00').split(':')
    
    day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 
               'friday': 4, 'saturday': 5, 'sunday': 6}
    target_day = day_map.get(day_of_week, 6)  # Default to Sunday
    target_hour = int(hour)
    target_minute = int(minute)
    
    now = datetime.now()
    
    # Find next occurrence of target day
    days_ahead = target_day - now.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    
    next_scan = now + timedelta(days=days_ahead)
    next_scan = next_scan.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    return next_scan

@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_stats():
    tenant_id = current_user.tenant_id
    
    # Get trend data (last 8 weeks)
    reports = WeeklyReport.query.filter_by(tenant_id=tenant_id).order_by(WeeklyReport.report_date.desc()).limit(8).all()
    reports.reverse()  # Oldest first for chart
    
    trend_data = {
        'labels': [r.report_date.strftime('%b %d') for r in reports],
        'mention_rates': [r.mention_rate for r in reports],
        'citation_rates': [r.citation_rate for r in reports]
    }
    
    # Get keyword priority distribution
    keywords = Keyword.query.filter_by(tenant_id=tenant_id, active=True).all()
    priority_dist = {'tier1': 0, 'tier2': 0, 'tier3': 0}
    for kw in keywords:
        if kw.priority_score >= 3.5:
            priority_dist['tier1'] += 1
        elif kw.priority_score >= 2.5:
            priority_dist['tier2'] += 1
        else:
            priority_dist['tier3'] += 1
    
    return jsonify({
        'trend_data': trend_data,
        'priority_distribution': priority_dist,
        'total_keywords': len(keywords)
    })

@dashboard_bp.route('/onboard', methods=['POST'])
@login_required
def run_onboarding():
    """Manually trigger onboarding for the current tenant"""
    from app.services.onboarding import OnboardingService
    
    service = OnboardingService()
    service.start_onboarding(current_user.tenant_id)
    
    flash('Onboarding started! Keywords are being discovered from your website.', 'success')
    return redirect(url_for('dashboard.index'))