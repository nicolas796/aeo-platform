from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Scan, ScanResult, Keyword
from app.services.aeo_scanner import AEOSCANNER
import threading

scans_bp = Blueprint('scans', __name__)

# Need to import current_app properly for thread context
import flask

@scans_bp.route('/')
@login_required
def index():
    tenant_id = current_user.tenant_id
    scans = Scan.query.filter_by(tenant_id=tenant_id).order_by(Scan.scan_date.desc()).all()
    return render_template('scans/index.html', scans=scans)

@scans_bp.route('/run', methods=['POST'])
@login_required
def run_scan():
    tenant_id = current_user.tenant_id
    
    # Check if scan already running
    running_scan = Scan.query.filter_by(tenant_id=tenant_id, status='running').first()
    if running_scan:
        flash('A scan is already in progress', 'warning')
        return redirect(url_for('scans.index'))
    
    # Get active keywords
    keywords = Keyword.query.filter_by(tenant_id=tenant_id, active=True).all()
    if not keywords:
        flash('No active keywords to scan. Add keywords first.', 'error')
        return redirect(url_for('keywords.index'))
    
    # Create scan record
    scan = Scan(
        tenant_id=tenant_id,
        status='pending',
        total_keywords=len(keywords)
    )
    db.session.add(scan)
    db.session.commit()
    
    # Run scan in background thread
    app = current_app._get_current_object()
    def run_async():
        with app.app_context():
            scanner = AEOSCANNER()
            scanner.run_scan(scan.id)
    
    thread = threading.Thread(target=run_async)
    thread.daemon = True
    thread.start()
    
    flash(f'Scan started for {len(keywords)} keywords', 'success')
    return redirect(url_for('scans.detail', id=scan.id))

@scans_bp.route('/<int:id>')
@login_required
def detail(id):
    tenant_id = current_user.tenant_id
    scan = Scan.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    results = ScanResult.query.filter_by(scan_id=scan.id).all()
    return render_template('scans/detail.html', scan=scan, results=results)

@scans_bp.route('/<int:id>/status')
@login_required
def status(id):
    tenant_id = current_user.tenant_id
    scan = Scan.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    return jsonify(scan.to_dict())