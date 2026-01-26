# app/routes/auth.py
from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.auth.forms import LoginForm, RegisterForm, UserEditForm, ChangePasswordForm, ProfileForm
from app.decorators.permissions import role_required
from app.models.user import User
from app.models.setting import Setting
from datetime import datetime

auth = Blueprint('auth', __name__, url_prefix='/auth')

SESSION_TIMEOUT = 1800  # seconds

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if not user or not check_password_hash(user.password, form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if user is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'danger')
            return redirect(url_for('auth.login'))
            
        # Update last login time
        user.last_login = db.func.current_timestamp()
        db.session.commit()
        
        login_user(user, remember=form.remember.data, duration=timedelta(seconds=SESSION_TIMEOUT))
        
        flash('You have been logged in successfully!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))
    
    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
@role_required('admin')  # Only admins can register new users
def register():
    form = RegisterForm()
    
    # For regular users, only show viewer option
    if not current_user.is_admin:
        form.role.choices = [('viewer', 'Viewer')]
    
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))
            
        try:
            # Only admins can create other admins
            role = form.role.data if current_user.is_admin else 'viewer'
            
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='scrypt'),
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'User {new_user.email} registered successfully as {new_user.role}!', 'success')
            return redirect(url_for('auth.user_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html', form=form)

@auth.route('/users')
@role_required('admin')
def user_management():
    """Admin user management page"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/users.html', 
                         users=users,
                         version=current_app.version)

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page - accessible by all users"""
    from app.auth.forms import ChangePasswordForm, ProfileForm
    
    # Get user statistics
    user = User.query.get(current_user.id)
    
    # Get statistics based on role
    reports_generated = 0
    login_count = 1  # At least current login
    days_active = (datetime.now() - user.created_at).days + 1
    
    # For admin and clerk, get reports generated
    if current_user.is_admin or current_user.is_clerk:
        if 'report_data' in session:
            reports_generated = 1  # Simplified for now
    
    # Activity log (simplified)
    recent_activity = [
        {
            'icon': 'sign-in-alt',
            'description': f'Logged in to system',
            'timestamp': user.last_login.strftime('%B %d, %Y %I:%M %p') if user.last_login else 'Never'
        }
    ]
    
    # Add created account activity
    recent_activity.append({
        'icon': 'user-plus',
        'description': 'Account created',
        'timestamp': user.created_at.strftime('%B %d, %Y')
    })
    
    # Load user preferences from settings
    notification_preferences = Setting.get_value(f'user_{user.id}_notifications', 'true') == 'true'
    theme_preference = Setting.get_value(f'user_{user.id}_theme', 'light')
    
    # Initialize forms
    password_form = ChangePasswordForm()
    profile_form = ProfileForm(obj=user)
    
    if request.method == 'POST':
        # Determine which form was submitted
        if 'current_password' in request.form:  # Password change form
            if password_form.validate_on_submit():
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')
                confirm_password = request.form.get('confirm_password')
                
                if not check_password_hash(user.password, current_password):
                    flash('Current password is incorrect', 'danger')
                elif new_password != confirm_password:
                    flash('New passwords do not match', 'danger')
                elif len(new_password) < 8:
                    flash('Password must be at least 8 characters', 'danger')
                else:
                    user.password = generate_password_hash(new_password, method='scrypt')
                    db.session.commit()
                    flash('Password updated successfully! Please login again.', 'success')
                    
                    # Add to activity log
                    recent_activity.insert(0, {
                        'icon': 'key',
                        'description': 'Changed password',
                        'timestamp': datetime.now().strftime('%B %d, %Y %I:%M %p')
                    })
                    
                    return redirect(url_for('auth.logout'))
        
        else:  # Profile update form
            if profile_form.validate_on_submit():
                user.email = profile_form.email.data
                
                # Save preferences
                Setting.set_value(f'user_{user.id}_notifications', 
                                'true' if request.form.get('notification_preferences') else 'false')
                Setting.set_value(f'user_{user.id}_theme', 
                                request.form.get('theme_preference', 'light'))
                
                db.session.commit()
                flash('Profile updated successfully!', 'success')
                
                # Add to activity log
                recent_activity.insert(0, {
                    'icon': 'user-edit',
                    'description': 'Updated profile information',
                    'timestamp': datetime.now().strftime('%B %d, %Y %I:%M %p')
                })
                
                return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html',
                         user=user,
                         password_form=password_form,
                         profile_form=profile_form,
                         reports_generated=reports_generated,
                         login_count=login_count,
                         days_active=days_active,
                         recent_activity=recent_activity,
                         notification_preferences=notification_preferences,
                         theme_preference=theme_preference,
                         version=current_app.version)

@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """API endpoint to change password"""
    user = User.query.get(current_user.id)
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_password or not new_password or not confirm_password:
        flash('All fields are required', 'danger')
        return redirect(url_for('auth.profile'))
    
    if not check_password_hash(user.password, current_password):
        flash('Current password is incorrect', 'danger')
    elif new_password != confirm_password:
        flash('New passwords do not match', 'danger')
    elif len(new_password) < 8:
        flash('Password must be at least 8 characters', 'danger')
    else:
        user.password = generate_password_hash(new_password, method='scrypt')
        db.session.commit()
        flash('Password updated successfully! Please login again.', 'success')
        return redirect(url_for('auth.logout'))
    
    return redirect(url_for('auth.profile'))

@auth.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """API endpoint to update profile"""
    user = User.query.get(current_user.id)
    
    email = request.form.get('email')
    notification_preferences = request.form.get('notification_preferences') == 'on'
    theme_preference = request.form.get('theme_preference', 'light')
    
    if not email:
        flash('Email is required', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Check if email is already taken by another user
    existing_user = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing_user:
        flash('Email already in use by another account', 'danger')
        return redirect(url_for('auth.profile'))
    
    user.email = email
    
    # Save preferences
    Setting.set_value(f'user_{user.id}_notifications', 
                     'true' if notification_preferences else 'false')
    Setting.set_value(f'user_{user.id}_theme', theme_preference)
    
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    
    return redirect(url_for('auth.profile'))

@auth.route('/activity-log')
@login_required
def activity_log():
    """View full activity log"""
    user = User.query.get(current_user.id)
    
    # Get activity from settings (simplified)
    activity_data = Setting.get_value(f'user_{user.id}_activity', '[]')
    
    # Parse activity data (would be JSON in real implementation)
    try:
        import json
        activities = json.loads(activity_data)
    except:
        activities = [
            {
                'icon': 'sign-in-alt',
                'description': 'Account created',
                'timestamp': user.created_at.strftime('%B %d, %Y %I:%M %p')
            }
        ]
        if user.last_login:
            activities.append({
                'icon': 'sign-in-alt',
                'description': 'Last login',
                'timestamp': user.last_login.strftime('%B %d, %Y %I:%M %p')
            })
    
    return render_template('auth/activity_log.html',
                         activities=activities,
                         user=user,
                         version=current_app.version)

@auth.route('/export-data', methods=['POST'])
@login_required
def export_data():
    """Export user data"""
    import csv
    import io
    
    user = User.query.get(current_user.id)
    
    # Create CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Data Type', 'Field', 'Value'])
    
    # Basic profile info
    writer.writerow(['Profile', 'Email', user.email])
    writer.writerow(['Profile', 'Role', user.role])
    writer.writerow(['Profile', 'Account Created', user.created_at])
    writer.writerow(['Profile', 'Last Login', user.last_login])
    writer.writerow(['Profile', 'Account Status', 'Active' if user.is_active else 'Inactive'])
    
    # Get preferences
    notifications = Setting.get_value(f'user_{user.id}_notifications', 'true')
    theme = Setting.get_value(f'user_{user.id}_theme', 'light')
    
    writer.writerow(['Preferences', 'Notifications', 'Enabled' if notifications == 'true' else 'Disabled'])
    writer.writerow(['Preferences', 'Theme', theme])
    
    # Prepare response
    output.seek(0)
    
    response = current_app.make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=user_data_{user.id}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@auth.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account"""
    if not current_user.is_admin:  # Only non-admins can delete their own account
        user = User.query.get(current_user.id)
        
        # Confirm deletion
        confirm_text = request.form.get('confirm_text', '')
        if confirm_text != 'DELETE':
            flash('Please type "DELETE" to confirm account deletion', 'danger')
            return redirect(url_for('auth.profile'))
        
        try:
            # Logout user first
            logout_user()
            
            # Delete user
            db.session.delete(user)
            db.session.commit()
            
            flash('Your account has been deleted successfully.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Account deletion failed: {str(e)}', 'danger')
            return redirect(url_for('auth.profile'))
    
    flash('Admin accounts cannot be deleted through this interface.', 'danger')
    return redirect(url_for('auth.profile'))

@auth.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    
    # Prevent editing self (admin should use profile page)
    if user.id == current_user.id:
        flash('Please use your profile page to edit your own account.', 'info')
        return redirect(url_for('auth.profile'))
    
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        try:
            user.email = form.email.data
            user.role = form.role.data
            user.is_active = form.is_active.data
            
            db.session.commit()
            flash(f'User {user.email} updated successfully!', 'success')
            return redirect(url_for('auth.user_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
    
    return render_template('auth/edit_user.html', 
                         form=form, 
                         user=user,
                         version=current_app.version)

@auth.route('/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('auth.user_management'))
    
    try:
        email = user.email
        db.session.delete(user)
        db.session.commit()
        flash(f'User {email} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Deletion failed: {str(e)}', 'danger')
    
    return redirect(url_for('auth.user_management'))

@auth.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@role_required('admin')
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deactivating self
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('auth.user_management'))
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.email} {status} successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Update failed: {str(e)}', 'danger')
    
    return redirect(url_for('auth.user_management'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))