"""Team management routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import db, User, Invitation, Tenant
from app.services.email_service import EmailService
from datetime import datetime, timedelta
import secrets

team_bp = Blueprint('team', __name__)


@team_bp.route('/')
@login_required
def index():
    """Show team members and invitations"""
    tenant_id = current_user.tenant_id
    
    # Get all users in the tenant
    users = User.query.filter_by(tenant_id=tenant_id).order_by(User.created_at.desc()).all()
    
    # Get pending invitations
    invitations = Invitation.query.filter_by(
        tenant_id=tenant_id, 
        status='pending'
    ).order_by(Invitation.created_at.desc()).all()
    
    return render_template('team/index.html', users=users, invitations=invitations)


@team_bp.route('/invite', methods=['POST'])
@login_required
def invite():
    """Send invitation to a new team member"""
    email = request.form.get('email')
    role = request.form.get('role', 'user')
    
    if not email:
        flash('Please provide an email address.', 'error')
        return redirect(url_for('team.index'))
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('A user with this email already exists.', 'error')
        return redirect(url_for('team.index'))
    
    # Check if there's already a pending invitation
    existing_invite = Invitation.query.filter_by(
        email=email, 
        tenant_id=current_user.tenant_id,
        status='pending'
    ).first()
    
    if existing_invite and not existing_invite.is_expired():
        flash('An invitation has already been sent to this email.', 'error')
        return redirect(url_for('team.index'))
    
    # Create invitation
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        tenant_id=current_user.tenant_id,
        invited_by=current_user.id,
        email=email,
        token=token,
        role=role,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    
    db.session.add(invitation)
    db.session.commit()
    
    # Send invitation email
    service = EmailService()
    invite_url = url_for('team.accept_invite', token=token, _external=True)
    success, error = service.send_invitation_email(email, current_user, invite_url)
    
    if success:
        flash(f'Invitation sent to {email}!', 'success')
    else:
        flash(f'Invitation created but email failed: {error}. Share this link: {invite_url}', 'warning')
    
    return redirect(url_for('team.index'))


@team_bp.route('/invite/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_invite(id):
    """Cancel a pending invitation"""
    invitation = Invitation.query.filter_by(
        id=id,
        tenant_id=current_user.tenant_id,
        status='pending'
    ).first_or_404()
    
    invitation.status = 'cancelled'
    db.session.commit()
    
    flash('Invitation cancelled.', 'success')
    return redirect(url_for('team.index'))


@team_bp.route('/accept/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    """Accept an invitation and create account"""
    invitation = Invitation.query.filter_by(token=token, status='pending').first()
    
    if not invitation:
        flash('Invalid or expired invitation.', 'error')
        return redirect(url_for('auth.login'))
    
    if invitation.is_expired():
        invitation.status = 'expired'
        db.session.commit()
        flash('This invitation has expired.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([first_name, last_name, password]):
            flash('Please fill in all fields.', 'error')
            return render_template('team/accept_invite.html', invitation=invitation)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('team/accept_invite.html', invitation=invitation)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('team/accept_invite.html', invitation=invitation)
        
        # Create user
        user = User(
            email=invitation.email,
            first_name=first_name,
            last_name=last_name,
            tenant_id=invitation.tenant_id,
            role=invitation.role,
            invited_by=invitation.invited_by,
            invitation_accepted=True
        )
        user.set_password(password)
        
        db.session.add(user)
        
        # Mark invitation as accepted
        invitation.status = 'accepted'
        invitation.accepted_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Welcome! Your account has been created. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('team/accept_invite.html', invitation=invitation)


@team_bp.route('/user/<int:id>/remove', methods=['POST'])
@login_required
def remove_user(id):
    """Remove a user from the team"""
    # Can't remove yourself
    if id == current_user.id:
        flash('You cannot remove yourself.', 'error')
        return redirect(url_for('team.index'))
    
    # Only admins can remove users
    if not current_user.is_admin():
        flash('Only admins can remove team members.', 'error')
        return redirect(url_for('team.index'))
    
    user = User.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    
    # Deactivate user instead of deleting
    user.active = False
    db.session.commit()
    
    flash(f'{user.email} has been removed from the team.', 'success')
    return redirect(url_for('team.index'))


@team_bp.route('/user/<int:id>/role', methods=['POST'])
@login_required
def change_role(id):
    """Change a user's role"""
    if not current_user.is_admin():
        flash('Only admins can change roles.', 'error')
        return redirect(url_for('team.index'))
    
    # Can't change your own role
    if id == current_user.id:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('team.index'))
    
    user = User.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    new_role = request.form.get('role')
    
    if new_role not in ['admin', 'user']:
        flash('Invalid role.', 'error')
        return redirect(url_for('team.index'))
    
    user.role = new_role
    db.session.commit()
    
    flash(f'{user.email} is now a {new_role}.', 'success')
    return redirect(url_for('team.index'))
