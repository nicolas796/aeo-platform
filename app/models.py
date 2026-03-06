from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class Tenant(db.Model):
    """A brand/organization in the multi-tenant system"""
    __tablename__ = 'tenants'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    domain = db.Column(db.String(100), unique=True, nullable=False)
    website_url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    industry = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    users = db.relationship('User', backref='tenant', lazy='dynamic')
    keywords = db.relationship('Keyword', backref='tenant', lazy='dynamic')
    competitors = db.relationship('Competitor', backref='tenant', lazy='dynamic')
    scans = db.relationship('Scan', backref='tenant', lazy='dynamic')
    reports = db.relationship('WeeklyReport', backref='tenant', lazy='dynamic')
    content_suggestions = db.relationship('ContentSuggestion', backref='tenant', lazy='dynamic')
    
    def __repr__(self):
        return f'<Tenant {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'website_url': self.website_url,
            'description': self.description,
            'industry': self.industry,
            'created_at': self.created_at.isoformat(),
            'active': self.active,
            'user_count': self.users.count(),
            'keyword_count': self.keywords.count()
        }


class User(UserMixin, db.Model):
    """User model with tenant association"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default='user')  # 'admin', 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    
    # Tenant association
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    
    # Team/invitation tracking
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    invitation_accepted = db.Column(db.Boolean, default=True)  # False until invite accepted
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'tenant_id': self.tenant_id,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Keyword(db.Model):
    """Keywords/prompts to track for AEO visibility"""
    __tablename__ = 'keywords'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # 'problem-aware', 'solution-aware', 'comparison', etc.
    priority_score = db.Column(db.Float, default=0.0)  # 0-5 scale
    relevance_score = db.Column(db.Float, default=0.0)
    volume_score = db.Column(db.Float, default=0.0)
    winability_score = db.Column(db.Float, default=0.0)
    intent_score = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    scan_results = db.relationship('ScanResult', backref='keyword', lazy='dynamic')
    content_suggestions = db.relationship('ContentSuggestion', backref='keyword', lazy='dynamic')
    
    def calculate_priority(self):
        """Calculate priority score from component scores"""
        if all([self.relevance_score, self.volume_score, self.winability_score, self.intent_score]):
            self.priority_score = (self.relevance_score * 2 + self.volume_score + 
                                  self.winability_score + self.intent_score) / 5
        return self.priority_score
    
    def __repr__(self):
        return f'<Keyword {self.prompt_text[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'prompt_text': self.prompt_text,
            'category': self.category,
            'priority_score': round(self.priority_score, 2),
            'active': self.active,
            'created_at': self.created_at.isoformat()
        }


class Competitor(db.Model):
    """Competitors to track for comparison"""
    __tablename__ = 'competitors'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    domain = db.Column(db.String(100), nullable=False)
    website_url = db.Column(db.String(500))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Competitor {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'website_url': self.website_url,
            'active': self.active
        }


class Scan(db.Model):
    """AEO visibility scan run for a tenant"""
    __tablename__ = 'scans'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    scan_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    total_keywords = db.Column(db.Integer, default=0)
    completed_keywords = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    
    # Relationships
    results = db.relationship('ScanResult', backref='scan', lazy='dynamic')
    
    def __repr__(self):
        return f'<Scan {self.id} - {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'scan_date': self.scan_date.isoformat(),
            'status': self.status,
            'total_keywords': self.total_keywords,
            'completed_keywords': self.completed_keywords,
            'progress_percent': round((self.completed_keywords / self.total_keywords * 100), 1) if self.total_keywords > 0 else 0
        }


class ScanResult(db.Model):
    """Individual result for a keyword in a scan"""
    __tablename__ = 'scan_results'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.id'), nullable=False)
    
    # AEO metrics
    mentioned = db.Column(db.Boolean, default=False)
    cited = db.Column(db.Boolean, default=False)
    sentiment = db.Column(db.String(20))  # positive, neutral, negative
    mention_excerpt = db.Column(db.Text)
    cited_urls = db.Column(db.Text)  # JSON array of URLs
    competitor_mentions = db.Column(db.Text)  # JSON object {competitor: count}
    
    # Raw response data
    ai_response = db.Column(db.Text)
    sources = db.Column(db.Text)  # JSON array of sources
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_cited_urls(self):
        return json.loads(self.cited_urls) if self.cited_urls else []
    
    def get_competitor_mentions(self):
        return json.loads(self.competitor_mentions) if self.competitor_mentions else {}
    
    def __repr__(self):
        return f'<ScanResult {self.keyword_id} - M:{self.mentioned} C:{self.cited}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'keyword_id': self.keyword_id,
            'keyword_text': self.keyword.prompt_text if self.keyword else None,
            'mentioned': self.mentioned,
            'cited': self.cited,
            'sentiment': self.sentiment,
            'mention_excerpt': self.mention_excerpt,
            'cited_urls': self.get_cited_urls(),
            'competitor_mentions': self.get_competitor_mentions()
        }


class ContentSuggestion(db.Model):
    """AI-generated content suggestions for keywords"""
    __tablename__ = 'content_suggestions'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    outline = db.Column(db.Text)  # JSON structure
    target_word_count = db.Column(db.Integer, default=1500)
    key_points = db.Column(db.Text)  # JSON array
    unique_angle = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, created
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_outline(self):
        return json.loads(self.outline) if self.outline else []

    def get_key_points(self):
        return json.loads(self.key_points) if self.key_points else []

    def __repr__(self):
        return f'<ContentSuggestion {self.title[:50]}...>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'keyword': self.keyword.prompt_text if self.keyword else None,
            'target_word_count': self.target_word_count,
            'unique_angle': self.unique_angle,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


class GeneratedContent(db.Model):
    """Full articles generated from content suggestions"""
    __tablename__ = 'generated_content'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    suggestion_id = db.Column(db.Integer, db.ForeignKey('content_suggestions.id'), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Full markdown article
    meta_description = db.Column(db.String(200))
    word_count = db.Column(db.Integer)
    sources = db.Column(db.Text)  # JSON array of sources used

    # SEO & Content Enhancement Fields
    seo_keyphrase = db.Column(db.String(200))  # Primary SEO keyphrase
    internal_links = db.Column(db.Text)  # JSON array of suggested internal links
    external_links = db.Column(db.Text)  # JSON array of suggested external links
    thumbnail_path = db.Column(db.String(500))  # Path to generated thumbnail

    status = db.Column(db.String(20), default='draft')  # draft, published, archived

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    suggestion = db.relationship('ContentSuggestion', backref='generated_content', uselist=False)
    
    def get_sources(self):
        return json.loads(self.sources) if self.sources else []

    def get_internal_links(self):
        return json.loads(self.internal_links) if self.internal_links else []

    def get_external_links(self):
        return json.loads(self.external_links) if self.external_links else []

    def __repr__(self):
        return f'<GeneratedContent {self.title[:50]}...>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'word_count': self.word_count,
            'status': self.status,
            'seo_keyphrase': self.seo_keyphrase,
            'thumbnail_path': self.thumbnail_path,
            'created_at': self.created_at.isoformat()
        }


class WeeklyReport(db.Model):
    """Weekly AEO performance report"""
    __tablename__ = 'weekly_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Summary metrics
    total_keywords = db.Column(db.Integer)
    mention_rate = db.Column(db.Float)  # percentage
    citation_rate = db.Column(db.Float)  # percentage
    
    # Trend data (vs previous week)
    mention_rate_change = db.Column(db.Float)
    citation_rate_change = db.Column(db.Float)
    
    # Detailed data
    top_performing_keywords = db.Column(db.Text)  # JSON
    keywords_needing_attention = db.Column(db.Text)  # JSON
    competitor_comparison = db.Column(db.Text)  # JSON
    recommendations = db.Column(db.Text)  # JSON array
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_top_performing(self):
        return json.loads(self.top_performing_keywords) if self.top_performing_keywords else []
    
    def get_needing_attention(self):
        return json.loads(self.keywords_needing_attention) if self.keywords_needing_attention else []
    
    def get_competitor_comparison(self):
        return json.loads(self.competitor_comparison) if self.competitor_comparison else {}
    
    def get_recommendations(self):
        return json.loads(self.recommendations) if self.recommendations else []
    
    def __repr__(self):
        return f'<WeeklyReport {self.report_date.strftime("%Y-%m-%d")}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_date': self.report_date.isoformat(),
            'total_keywords': self.total_keywords,
            'mention_rate': round(self.mention_rate, 1) if self.mention_rate else 0,
            'citation_rate': round(self.citation_rate, 1) if self.citation_rate else 0,
            'mention_rate_change': round(self.mention_rate_change, 1) if self.mention_rate_change else 0,
            'citation_rate_change': round(self.citation_rate_change, 1) if self.citation_rate_change else 0,
            'recommendations': self.get_recommendations()
        }


class Invitation(db.Model):
    """Pending invitations to join a tenant"""
    __tablename__ = 'invitations'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')  # Role to assign when accepted
    status = db.Column(db.String(20), default='pending')  # pending, accepted, expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    
    # Relationships
    tenant = db.relationship('Tenant', backref='invitations')
    inviter = db.relationship('User', foreign_keys=[invited_by], backref='sent_invitations')
    
    def is_expired(self):
        from datetime import datetime
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f'<Invitation {self.email} - {self.status}>'


class ContentShare(db.Model):
    """Shareable links for generated content"""
    __tablename__ = 'content_shares'

    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('generated_content.id'), nullable=False)
    shared_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    recipient_email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    content = db.relationship('GeneratedContent', backref='shares')
    sharer = db.relationship('User', foreign_keys=[shared_by])

    def is_expired(self):
        return datetime.utcnow() > self.expires_at


class CreditBalance(db.Model):
    """Credit balance tracking per tenant"""
    __tablename__ = 'credit_balances'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True)
    credits_total = db.Column(db.Integer, default=0)
    credits_used = db.Column(db.Integer, default=0)
    credits_remaining = db.Column(db.Integer, default=0)
    billing_cycle_start = db.Column(db.DateTime)
    billing_cycle_end = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='credit_balance', uselist=False)

    def __repr__(self):
        return f'<CreditBalance {self.tenant.name}: {self.credits_remaining}>'


class CreditTransaction(db.Model):
    """Individual credit transactions"""
    __tablename__ = 'credit_transactions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    operation = db.Column(db.String(50), nullable=False)  # scan_keyword, content_generate, etc.
    quantity = db.Column(db.Integer, default=1)
    cost_per_unit = db.Column(db.Integer, default=0)
    total_cost = db.Column(db.Integer, default=0)  # Negative = credit added
    description = db.Column(db.String(255))
    meta_data = db.Column(db.Text)  # JSON string for extra data
    balance_after = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='credit_transactions')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'operation': self.operation,
            'quantity': self.quantity,
            'total_cost': self.total_cost,
            'description': self.description,
            'metadata': json.loads(self.meta_data) if self.meta_data else {},
            'balance_after': self.balance_after,
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<CreditTransaction {self.operation}: {self.total_cost}>'
