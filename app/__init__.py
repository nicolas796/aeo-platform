from flask import Flask
from flask_login import LoginManager
from config import config
from app.models import db, User, Tenant

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.keywords import keywords_bp
    from app.routes.competitors import competitors_bp
    from app.routes.scans import scans_bp
    from app.routes.reports import reports_bp
    from app.routes.team import team_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(keywords_bp, url_prefix='/keywords')
    app.register_blueprint(competitors_bp, url_prefix='/competitors')
    app.register_blueprint(scans_bp, url_prefix='/scans')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(team_bp, url_prefix='/team')
    
    # Create tables
    with app.app_context():
        db.create_all()
        _create_default_tenant_and_admin(app)
    
    # Initialize scheduler
    from app.services.scheduler import SchedulerService
    scheduler = SchedulerService(app)
    
    return app

def _create_default_tenant_and_admin(app):
    """Create default tenant and admin user if none exist"""
    # Check if any tenants exist
    if Tenant.query.first() is None:
        # Create default tenant
        default_tenant = Tenant(
            name='Demo Brand',
            domain='demo.aeoplatform.local',
            website_url='https://example.com',
            description='Default demo tenant',
            industry='Technology'
        )
        db.session.add(default_tenant)
        db.session.commit()
        
        # Create admin user
        admin_user = User(
            email='admin@aeoplatform.local',
            first_name='Admin',
            last_name='User',
            role='admin',
            tenant_id=default_tenant.id
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"Created default tenant: {default_tenant.name}")
        print(f"Created admin user: {admin_user.email} / password: admin123")

# Import for easier access
from app.models import db