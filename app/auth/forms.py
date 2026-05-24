# app/auth/forms.py
"""
WTForms form definitions for authentication and user management.
"""
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    ValidationError,
)

from app.models.user import User


# ---------------------------------------------------------------------------
# Auth forms
# ---------------------------------------------------------------------------

class LoginForm(FlaskForm):
    """Standard email + password login."""

    email    = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={'placeholder': 'you@example.com', 'autocomplete': 'email'},
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()],
        render_kw={'placeholder': '••••••••', 'autocomplete': 'current-password'},
    )
    remember = BooleanField('Remember me')
    submit   = SubmitField('Log In')


class RegisterForm(FlaskForm):
    """New user registration — used for both public and admin flows."""

    email    = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={'placeholder': 'you@example.com'},
    )
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
        ],
        render_kw={'placeholder': 'Min. 8 characters'},
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(),
            EqualTo('password', message='Passwords must match.'),
        ],
        render_kw={'placeholder': 'Repeat password'},
    )
    # Choices are overridden in the controller depending on the caller's role
    role   = SelectField(
        'Role',
        choices=[
            ('admin',  'Administrator'),
            ('clerk',  'Clerk'),
            ('viewer', 'Viewer'),
        ],
        default='viewer',
    )
    submit = SubmitField('Create Account')

    # ── Custom validators ──────────────────────────────────────────────

    def validate_email(self, field):
        """Reject emails already registered."""
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('That email address is already registered.')

    def validate_role(self, field):
        """Ensure the submitted role is a known value."""
        User.validate_role(field.data)


# ---------------------------------------------------------------------------
# Admin / clerk user-edit form
# ---------------------------------------------------------------------------

class UserEditForm(FlaskForm):
    """Edit an existing user's email, role and active status."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role')
    is_active = BooleanField('Active')
    submit = SubmitField('Update User')

    def __init__(self, *args, **kwargs):
        # Extract the original user object if passed via obj=user
        self.user = kwargs.get('obj', None)
        super(UserEditForm, self).__init__(*args, **kwargs)

    def validate_email(self, field):
        # Query for a user with the submitted email address
        existing_user = User.query.filter_by(email=field.data).first()
        
        if existing_user:
            # If we are editing an existing user, allow them to keep their own email
            if self.user and existing_user.id == self.user.id:
                return
            
            # Otherwise, it's a genuine duplicate conflict
            raise ValidationError('That email address is already in use.')


# ---------------------------------------------------------------------------
# Profile forms
# ---------------------------------------------------------------------------

class ProfileForm(FlaskForm):
    """Update the current user's own email address."""

    email  = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    submit = SubmitField('Update Profile')


class ChangePasswordForm(FlaskForm):
    """Authenticated password change — requires the current password."""

    current_password = PasswordField(
        'Current Password',
        validators=[DataRequired()],
        render_kw={'placeholder': 'Current password'},
    )
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
        ],
        render_kw={'placeholder': 'New password'},
    )
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(),
            EqualTo('new_password', message='Passwords must match.'),
        ],
        render_kw={'placeholder': 'Repeat new password'},
    )
    submit = SubmitField('Change Password')