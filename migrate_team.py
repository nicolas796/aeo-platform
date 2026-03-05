"""Database migration script to add team/invitation features"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db

def migrate():
    """Add new columns for team features"""
    app = create_app()
    
    with app.app_context():
        # Check if columns already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        # Get existing columns in users table
        user_columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add new columns to users table if they don't exist
        with db.engine.connect() as conn:
            if 'invited_by' not in user_columns:
                print("Adding 'invited_by' column to users table...")
                conn.execute(db.text("ALTER TABLE users ADD COLUMN invited_by INTEGER"))
                conn.execute(db.text("ALTER TABLE users ADD COLUMN invitation_accepted BOOLEAN DEFAULT 1"))
                conn.commit()
                print("Done!")
            else:
                print("Columns already exist, skipping.")
        
        # Create invitations table
        print("\nCreating invitations table...")
        db.create_all()
        print("Done!")
        
        print("\nMigration complete!")

if __name__ == '__main__':
    migrate()
