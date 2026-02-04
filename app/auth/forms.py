# app/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models.user import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired("Email is required"),
        Email("Please enter a valid email address")
    ], render_kw={"placeholder": "your@email.com"})
    
    password = PasswordField('Password', validators=[
        DataRequired("Password is required")
    ], render_kw={"placeholder": "••••••••"})
    
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login', render_kw={"class": "btn btn-primary"})

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired("Email is required"),
        Email("Please enter a valid email address")
    ], render_kw={"placeholder": "your@email.com"})
    
    password = PasswordField('Password', validators=[
        DataRequired("Password is required"),
        Length(min=8, message="Password must be at least 8 characters")
    ], render_kw={"placeholder": "••••••••"})
    
    confirm = PasswordField('Confirm Password', validators=[
        DataRequired("Please confirm your password"),
        EqualTo('password', message='Passwords must match')
    ], render_kw={"placeholder": "••••••••"})
    
    role = SelectField('Role', 
                      choices=[('viewer', 'Viewer'), ('clerk', 'Clerk'), ('admin', 'Admin')],
                      default='viewer')
    
    submit = SubmitField('Register', render_kw={"class": "btn btn-primary"})

class UserEditForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired("Email is required"),
        Email("Please enter a valid email address")
    ])
    
    role = SelectField('Role', 
                      choices=[('viewer', 'Viewer'), ('clerk', 'Clerk'), ('admin', 'Admin')])
    
    is_active = BooleanField('Active')
    
    new_password = PasswordField('New Password (optional)', validators=[
        Optional(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        Optional(),
        EqualTo('new_password', message='Passwords must match')
    ])
    
    submit = SubmitField('Update User', render_kw={"class": "btn btn-primary"})

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[
        DataRequired("Current password is required")
    ], render_kw={"placeholder": "Enter current password"})
    
    new_password = PasswordField('New Password', validators=[
        DataRequired("New password is required"),
        Length(min=8, message='Password must be at least 8 characters')
    ], render_kw={"placeholder": "Enter new password"})
    
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired("Please confirm new password"),
        EqualTo('new_password', message='Passwords must match')
    ], render_kw={"placeholder": "Confirm new password"})
    
    submit = SubmitField('Change Password', render_kw={"class": "btn btn-primary"})

class ProfileForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired("Email is required"),
        Email("Please enter a valid email address")
    ], render_kw={"placeholder": "your@email.com"})
    
    submit = SubmitField('Save Changes', render_kw={"class": "btn btn-primary"})
    
    def validate_email(self, email):
        # This validation only runs when the form is submitted
        # Check if email already exists for another user
        if hasattr(self, '_obj'):
            user = User.query.filter(User.email == email.data, User.id != self._obj.id).first()
            if user:
                raise ValidationError('Email already registered')