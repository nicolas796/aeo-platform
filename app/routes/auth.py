from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Tenant

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email, active=True).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = db.func.now()
            db.session.commit()
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration - requires tenant invite code or creates new tenant"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        tenant_name = request.form.get('tenant_name', '').strip()
        website_url = request.form.get('website_url', '').strip()
        industry = request.form.get('industry', '').strip()
        
        # Validation
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('auth/register.html')
        
        # Create tenant
        domain = email.split('@')[1] if '@' in email else tenant_name.lower().replace(' ', '-')
        tenant = Tenant(
            name=tenant_name,
            domain=domain,
            website_url=website_url or f'https://{domain}',
            industry=industry or 'general'
        )
        db.session.add(tenant)
        db.session.commit()
        
        # Create user as admin of their tenant
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='admin',
            tenant_id=tenant.id
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        
        # Trigger automated onboarding research
        from app.services.onboarding import OnboardingService
        onboarding = OnboardingService()
        onboarding.start_onboarding(tenant.id)
        
        flash('Account created successfully! We\'re analyzing your website and setting up your dashboard...', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/register.html')