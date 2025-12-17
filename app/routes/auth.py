# app/routes/auth.py
from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.auth.forms import LoginForm, RegisterForm

auth = Blueprint('auth', __name__, url_prefix='/auth')

SESSION_TIMEOUT = 1800  # seconds

@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Import User inside the function to avoid circular imports
    from app.models.user import User
    
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if not user or not check_password_hash(user.password, form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=form.remember.data, duration=timedelta(seconds=SESSION_TIMEOUT))
        
        flash('You have been logged in successfully!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))
    
    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    # Import User inside the function to avoid circular imports
    from app.models.user import User
    
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))
            
        try:
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='scrypt')
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))