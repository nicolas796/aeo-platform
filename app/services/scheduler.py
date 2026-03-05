from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
from app.models import Tenant, Scan
from app.services.aeo_scanner import AEOSCANNER
from app.services.report_generator import ReportGenerator
import threading

class SchedulerService:
    """Service for scheduling weekly AEO scans and reports"""
    
    def __init__(self, app=None):
        self.scheduler = BackgroundScheduler()
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        self._schedule_jobs()
        self.scheduler.start()
    
    def _schedule_jobs(self):
        """Schedule recurring jobs"""
        # Weekly scan - runs on configured day/time
        day_of_week = self.app.config.get('WEEKLY_SCAN_DAY', 'sunday').lower()[:3]
        hour, minute = self.app.config.get('WEEKLY_SCAN_TIME', '02:00').split(':')
        
        self.scheduler.add_job(
            func=self._run_weekly_scans,
            trigger=CronTrigger(day_of_week=day_of_week, hour=int(hour), minute=int(minute)),
            id='weekly_aeo_scan',
            name='Weekly AEO Visibility Scan',
            replace_existing=True
        )
        
        # Daily report generation (after scans complete)
        self.scheduler.add_job(
            func=self._run_daily_reports,
            trigger=CronTrigger(hour=4, minute=0),
            id='daily_report_generation',
            name='Daily Report Generation',
            replace_existing=True
        )
    
    def _run_weekly_scans(self):
        """Run scans for all active tenants"""
        app = self.app
        with app.app_context():
            tenants = Tenant.query.filter_by(active=True).all()
            
            for tenant in tenants:
                try:
                    # Check if scan already running for this tenant
                    running = Scan.query.filter_by(tenant_id=tenant.id, status='running').first()
                    if running:
                        continue
                    
                    # Create scan record
                    from app.models import Keyword
                    keywords = Keyword.query.filter_by(tenant_id=tenant.id, active=True).all()
                    
                    if not keywords:
                        continue
                    
                    scan = Scan(
                        tenant_id=tenant.id,
                        status='pending',
                        total_keywords=len(keywords)
                    )
                    from app.models import db
                    db.session.add(scan)
                    db.session.commit()
                    
                    # Run scan in background
                    def run_scan_async(scan_id, app_ref):
                        with app_ref.app_context():
                            scanner = AEOSCANNER()
                            scanner.run_scan(scan_id)
                    
                    thread = threading.Thread(target=run_scan_async, args=(scan.id, app))
                    thread.daemon = True
                    thread.start()
                    
                except Exception as e:
                    print(f"Error scheduling scan for tenant {tenant.id}: {e}")
    
    def _run_daily_reports(self):
        """Generate reports for tenants with completed scans"""
        with self.app.app_context():
            tenants = Tenant.query.filter_by(active=True).all()
            
            for tenant in tenants:
                try:
                    # Check if there's a recent scan without a report
                    latest_scan = Scan.query.filter_by(tenant_id=tenant.id, status='completed').order_by(Scan.scan_date.desc()).first()
                    
                    if not latest_scan:
                        continue
                    
                    from app.models import WeeklyReport
                    latest_report = WeeklyReport.query.filter_by(tenant_id=tenant.id).order_by(WeeklyReport.report_date.desc()).first()
                    
                    # Generate report if scan is newer than last report
                    if not latest_report or latest_scan.scan_date > latest_report.report_date:
                        generator = ReportGenerator()
                        generator.generate_weekly_report(tenant.id)
                        
                except Exception as e:
                    print(f"Error generating report for tenant {tenant.id}: {e}")
    
    def shutdown(self):
        self.scheduler.shutdown()