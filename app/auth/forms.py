
# === app/auth/forms.py ===
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import InputRequired, Email, Length, EqualTo, Optional
from app.models.user import User 

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired("Email is required"),
        Email("Please enter a valid email address")
    ], render_kw={"placeholder": "your@email.com"})
    
    password = PasswordField('Password', validators=[
        InputRequired("Password is required")
    ], render_kw={"placeholder": "••••••••"})
    
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login', render_kw={"class": "btn btn-primary"})

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired("Email is required"),
        Email("Please enter a valid email address")
    ], render_kw={"placeholder": "your@email.com"})
    
    password = PasswordField('Password', validators=[
        InputRequired("Password is required"),
        Length(min=8, message="Password must be at least 8 characters"),
        EqualTo('confirm', message='Passwords must match')
    ], render_kw={"placeholder": "••••••••"})
    
    confirm = PasswordField('Confirm Password', render_kw={"placeholder": "••••••••"})
    
    role = SelectField('Role', 
                      choices=[('viewer', 'Viewer'), ('clerk', 'Clerk'), ('admin', 'Admin')],
                      default='viewer',
                      validators=[Optional()])
    
    submit = SubmitField('Register', render_kw={"class": "btn btn-primary"})

class UserEditForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired("Email is required"),
        Email("Please enter a valid email address")
    ])
    
    role = SelectField('Role', 
                      choices=[('viewer', 'Viewer'), ('clerk', 'Clerk'), ('admin', 'Admin')])
    
    is_active = BooleanField('Active')
    
    submit = SubmitField('Update User', render_kw={"class": "btn btn-primary"})