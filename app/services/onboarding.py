import threading
from app.models import db, Tenant, Keyword, Competitor, Scan
from app.services.keyword_research import KeywordResearchService
from app.services.aeo_scanner import AEOSCANNER

class OnboardingService:
    """Automated onboarding for new tenants - runs research and initial scan"""
    
    def start_onboarding(self, tenant_id: int):
        """Start the onboarding process in a background thread"""
        thread = threading.Thread(target=self._run_onboarding, args=(tenant_id,))
        thread.daemon = True
        thread.start()
    
    def _run_onboarding(self, tenant_id: int):
        """Run the full onboarding sequence"""
        from flask import current_app
        import traceback
        
        app = current_app._get_current_object()
        
        with app.app_context():
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                print(f"Onboarding: Tenant {tenant_id} not found")
                return
            
            print(f"Onboarding: Starting for tenant {tenant_id} ({tenant.name})")
            
            try:
                # Step 1: Auto-discover keywords from website
                print(f"Onboarding: Step 1 - Discovering keywords...")
                self._discover_keywords(tenant)
                
                # Step 2: Add common competitors based on industry
                print(f"Onboarding: Step 2 - Adding competitors...")
                self._add_default_competitors(tenant)
                
                # Step 3: Run initial scan
                print(f"Onboarding: Step 3 - Running initial scan...")
                self._run_initial_scan(tenant)
                
                print(f"Onboarding: Completed for tenant {tenant_id}")
                
            except Exception as e:
                print(f"Onboarding error for tenant {tenant_id}: {e}")
                print(traceback.format_exc())
    
    def _discover_keywords(self, tenant: Tenant):
        """Discover keywords from the tenant's website - must succeed"""
        service = KeywordResearchService()
        
        keywords = service.discover_keywords(tenant.id)
        if not keywords:
            raise ValueError(f"No keywords discovered for {tenant.name}. Please check the website URL.")
        
        print(f"Onboarding: Discovered {len(keywords)} keywords for {tenant.name}")
    
    def _add_default_competitors(self, tenant: Tenant):
        """Discover competitors from website or leave empty for user to add"""
        # Skip auto-adding generic competitors - let user add their real competitors
        # Could enhance this later by crawling website for "vs" or "compare" mentions
        print(f"Onboarding: Skipping auto-competitors for {tenant.name} - user should add their real competitors")
    
    def _run_initial_scan(self, tenant: Tenant):
        """Run the initial AEO scan"""
        keywords = Keyword.query.filter_by(tenant_id=tenant.id, active=True).all()
        
        if not keywords:
            print(f"Onboarding: No keywords to scan for {tenant.name}")
            return
        
        # Create scan record
        scan = Scan(
            tenant_id=tenant.id,
            status='pending',
            total_keywords=len(keywords)
        )
        db.session.add(scan)
        db.session.commit()
        
        # Run scan
        try:
            scanner = AEOSCANNER()
            scanner.run_scan(scan.id)
            print(f"Onboarding: Initial scan completed for {tenant.name}")
            
            # Generate initial report
            from app.services.report_generator import ReportGenerator
            generator = ReportGenerator()
            report = generator.generate_weekly_report(tenant.id)
            
            if report:
                print(f"Onboarding: Initial report generated for {tenant.name}")
                
        except Exception as e:
            print(f"Onboarding: Scan failed: {e}")
            scan.status = 'failed'
            scan.error_message = str(e)
            db.session.commit()