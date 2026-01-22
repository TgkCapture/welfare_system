# app/routes/auth.py
from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.auth.forms import LoginForm, RegisterForm, UserEditForm
from app.decorators.permissions import role_required

auth = Blueprint('auth', __name__, url_prefix='/auth')

SESSION_TIMEOUT = 1800  # seconds

def get_user_model():
    """Get the User model - handles circular imports"""
    from app.models.user import User
    return User

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    form = LoginForm()
    if form.validate_on_submit():
        User = get_user_model()
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
        User = get_user_model()
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
    User = get_user_model()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/users.html', users=users)

@auth.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_user(user_id):
    """Edit user details"""
    User = get_user_model()
    user = User.query.get_or_404(user_id)
    
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
    
    return render_template('auth/edit_user.html', form=form, user=user)

@auth.route('/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    """Delete a user"""
    User = get_user_model()
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('auth.user_management'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.email} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Deletion failed: {str(e)}', 'danger')
    
    return redirect(url_for('auth.user_management'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    User = get_user_model()
    user = User.query.get(current_user.id)
    
    if request.method == 'POST':
        # Handle password change
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password and new_password and confirm_password:
            if not check_password_hash(user.password, current_password):
                flash('Current password is incorrect', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'danger')
            elif len(new_password) < 8:
                flash('Password must be at least 8 characters', 'danger')
            else:
                user.password = generate_password_hash(new_password, method='scrypt')
                db.session.commit()
                flash('Password updated successfully!', 'success')
                return redirect(url_for('auth.logout'))
    
    return render_template('auth/profile.html', user=user)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))