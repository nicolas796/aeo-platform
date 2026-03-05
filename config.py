# AEO Platform Configuration
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///aeoplatform.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session config
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # API Keys (load from env)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY')
    SENDGRID_API_KEY = (os.environ.get('SENDGRID_API_KEY') or '').strip() or None
    SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@aeoplatform.local')
    
    # Scheduling
    WEEKLY_SCAN_DAY = os.environ.get('WEEKLY_SCAN_DAY', 'sunday')  # Day to run weekly scans
    WEEKLY_SCAN_TIME = os.environ.get('WEEKLY_SCAN_TIME', '02:00')  # Time to run (24h format)
    
    # AEO Settings
    MAX_KEYWORDS_PER_BRAND = int(os.environ.get('MAX_KEYWORDS_PER_BRAND', '50'))
    MAX_COMPETITORS_PER_BRAND = int(os.environ.get('MAX_COMPETITORS_PER_BRAND', '5'))
    SCAN_TIMEOUT_SECONDS = int(os.environ.get('SCAN_TIMEOUT_SECONDS', '300'))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Production should always have proper SECRET_KEY

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}