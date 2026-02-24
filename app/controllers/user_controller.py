# app/controllers/user_controller.py
from flask import render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.decorators.permissions import role_required, permission_required
from app.auth.forms import RegisterForm, UserEditForm
from app.models.user import User
from app.extensions import db

class UserController:
    """Handles user management business logic"""
    
    # ==================== ADMIN USER MANAGEMENT ====================
    
    @staticmethod
    @role_required('admin')
    def admin_users():
        """Admin user management page - list all users"""
        users = User.query.order_by(User.created_at.desc()).all()
        
        return render_template(
            'main/admin_users.html',
            version=current_app.version,
            users=users,
            current_user=current_user
        )
    
    @staticmethod
    @role_required('admin')
    def create_user():
        """Create a new user (admin can create any role)"""
        form = RegisterForm()
        
        # Admin sees all role options
        form.role.choices = [
            ('admin', 'Administrator'),
            ('clerk', 'Clerk'),
            ('viewer', 'Viewer')
        ]
        
        if form.validate_on_submit():
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already registered', 'danger')
                return redirect(url_for('main.create_user'))
            
            try:
                new_user = User(
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='scrypt'),
                    role=form.role.data
                )
                db.session.add(new_user)
                db.session.commit()
                
                flash(f'User {new_user.email} created successfully as {new_user.role}!', 'success')
                return redirect(url_for('main.admin_users'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'User creation failed: {str(e)}', 'danger')
        
        return render_template(
            'main/create_user.html',
            version=current_app.version,
            form=form,
            is_admin=True
        )
    
    @staticmethod
    @role_required('admin')
    def edit_user(user_id):
        """Edit any user (admin)"""
        user = User.query.get_or_404(user_id)
        
        # Prevent editing self
        if user.id == current_user.id:
            flash('Please use your profile page to edit your own account.', 'info')
            return redirect(url_for('auth.profile'))
        
        form = UserEditForm(obj=user)
        
        # Admin can set any role
        form.role.choices = [
            ('admin', 'Administrator'),
            ('clerk', 'Clerk'),
            ('viewer', 'Viewer')
        ]
        
        if form.validate_on_submit():
            try:
                user.email = form.email.data
                user.role = form.role.data
                user.is_active = form.is_active.data
                
                db.session.commit()
                flash(f'User {user.email} updated successfully!', 'success')
                return redirect(url_for('main.admin_users'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Update failed: {str(e)}', 'danger')
        
        return render_template('main/edit_user.html', 
                             form=form, 
                             user=user,
                             version=current_app.version,
                             is_admin=True)
    
    @staticmethod
    @role_required('admin')
    def delete_user(user_id):
        """Delete any user (admin)"""
        user = User.query.get_or_404(user_id)
        
        # Prevent self-deletion
        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'danger')
            return redirect(url_for('main.admin_users'))
        
        try:
            email = user.email
            db.session.delete(user)
            db.session.commit()
            flash(f'User {email} deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Deletion failed: {str(e)}', 'danger')
        
        return redirect(url_for('main.admin_users'))
    
    @staticmethod
    @role_required('admin')
    def toggle_user_active(user_id):
        """Toggle any user active status (admin)"""
        user = User.query.get_or_404(user_id)
        
        # Prevent deactivating self
        if user.id == current_user.id:
            flash('You cannot deactivate your own account.', 'danger')
            return redirect(url_for('main.admin_users'))
        
        try:
            user.is_active = not user.is_active
            db.session.commit()
            
            status = 'activated' if user.is_active else 'deactivated'
            flash(f'User {user.email} {status} successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
        
        return redirect(url_for('main.admin_users'))
    
    # ==================== CLERK USER MANAGEMENT ====================
    
    @staticmethod
    @role_required('clerk')
    def clerk_users():
        """Clerk user management page - list only viewers"""
        # Clerks can only see viewers
        viewers = User.query.filter_by(role='viewer').order_by(User.created_at.desc()).all()
        
        return render_template(
            'main/clerk_users.html',  # New template for clerk user management
            version=current_app.version,
            users=viewers,
            current_user=current_user
        )
    
    @staticmethod
    @role_required('clerk')
    def create_viewer():
        """Create a new viewer (clerk can only create viewers)"""
        form = RegisterForm()
        
        # Clerk can only create viewers
        form.role.choices = [('viewer', 'Viewer')]
        form.role.data = 'viewer'  # Default to viewer
        
        if form.validate_on_submit():
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already registered', 'danger')
                return redirect(url_for('main.create_viewer'))
            
            try:
                new_user = User(
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='scrypt'),
                    role='viewer'  # Force viewer role for clerk
                )
                db.session.add(new_user)
                db.session.commit()
                
                flash(f'Viewer {new_user.email} created successfully!', 'success')
                return redirect(url_for('main.clerk_users'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'User creation failed: {str(e)}', 'danger')
        
        return render_template(
            'main/create_user.html',
            version=current_app.version,
            form=form,
            is_admin=False  # Different template context for clerk
        )
    
    @staticmethod
    @role_required('clerk')
    def edit_viewer(user_id):
        """Edit a viewer (clerk can only edit viewers)"""
        user = User.query.get_or_404(user_id)
        
        # Clerk can only edit viewers
        if user.role != 'viewer':
            flash('You can only edit viewer accounts.', 'danger')
            return redirect(url_for('main.clerk_users'))
        
        form = UserEditForm(obj=user)
        
        # Clerk can only set viewer role
        form.role.choices = [('viewer', 'Viewer')]
        form.role.data = 'viewer'
        
        if form.validate_on_submit():
            try:
                user.email = form.email.data
                user.is_active = form.is_active.data
                # Role stays as 'viewer'
                
                db.session.commit()
                flash(f'Viewer {user.email} updated successfully!', 'success')
                return redirect(url_for('main.clerk_users'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Update failed: {str(e)}', 'danger')
        
        return render_template('main/edit_user.html', 
                             form=form, 
                             user=user,
                             version=current_app.version,
                             is_admin=False)  # Different template for clerk
    
    @staticmethod
    @role_required('clerk')
    def toggle_viewer_active(user_id):
        """Toggle viewer active status (clerk)"""
        user = User.query.get_or_404(user_id)
        
        # Clerk can only toggle viewers
        if user.role != 'viewer':
            flash('You can only manage viewer accounts.', 'danger')
            return redirect(url_for('main.clerk_users'))
        
        try:
            user.is_active = not user.is_active
            db.session.commit()
            
            status = 'activated' if user.is_active else 'deactivated'
            flash(f'Viewer {user.email} {status} successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
        
        return redirect(url_for('main.clerk_users'))
    
