# app/controllers/user_controller.py
from flask import render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.decorators.permissions import role_required
from app.auth.forms import RegisterForm
from app.models.user import User
from app.extensions import db

class UserController:
    """Handles user management business logic"""
    
    @staticmethod
    @role_required('admin')
    def admin_users():
        """User management page - list all users"""
        users = User.query.order_by(
            User.created_at.desc()
        ).all()
        
        return render_template(
            'main/admin_users.html',
            version=current_app.version,
            users=users,
            current_user=current_user
        )
    
    @staticmethod
    @role_required('admin')
    def create_user():
        """Create a new user"""
        form = RegisterForm()
        
        if form.validate_on_submit():
            # Check if email already exists
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
            form=form
        )