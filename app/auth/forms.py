# app/auth/forms.py
"""
WTForms form definitions for authentication and user management.
"""
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
)
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    ValidationError,
)

from app.models.group import Group
from app.models.role import Role
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
    """New officer account, created by an officer with manage_users."""

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
    # Choices (the group's roles the officer may grant) are set in the controller
    role   = SelectField('Role', coerce=int)
    submit = SubmitField('Create Account')

    def __init__(self, *args, group_id=None, **kwargs):
        # The group the account is created in; defaults to the creator's group
        self.group_id = group_id
        super().__init__(*args, **kwargs)

    # ── Custom validators ──────────────────────────────────────────────

    def validate_email(self, field):
        """Reject emails already registered in the target group."""
        group_id = self.group_id if self.group_id is not None else current_user.group_id
        if User.email_taken(field.data.strip(), group_id):
            raise ValidationError('That email address is already registered.')


# ---------------------------------------------------------------------------
# Admin / clerk user-edit form
# ---------------------------------------------------------------------------

class UserEditForm(FlaskForm):
    """Edit an existing user's email, role and active status."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', coerce=int)
    is_active = BooleanField('Active')
    submit = SubmitField('Update User')

    def __init__(self, *args, **kwargs):
        # Extract the original user object if passed via obj=user
        self.user = kwargs.get('obj', None)
        super(UserEditForm, self).__init__(*args, **kwargs)

    def validate_email(self, field):
        # Unique within the edited user's group; a user may keep their own email
        group_id = self.user.group_id if self.user else current_user.group_id
        exclude_id = self.user.id if self.user else None
        if User.email_taken(field.data, group_id, exclude_id=exclude_id):
            raise ValidationError('That email address is already in use.')


# ---------------------------------------------------------------------------
# Group roles
# ---------------------------------------------------------------------------

class MultiCheckboxField(SelectMultipleField):
    """A multiple-choice field rendered as a list of checkboxes."""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class RoleForm(FlaskForm):
    """Create or edit one of the group's roles."""
    name = StringField('Role name', validators=[DataRequired(), Length(max=50)])
    # Choices (the permissions the officer holds) are set in the controller
    permissions = MultiCheckboxField('Permissions')
    submit = SubmitField('Save role')

    def __init__(self, *args, role=None, **kwargs):
        self.role = role
        super().__init__(*args, **kwargs)

    def validate_name(self, field):
        """Role names are unique within the group."""
        field.data = field.data.strip()
        query = Role.for_group().filter(Role.name == field.data)
        if self.role is not None:
            query = query.filter(Role.id != self.role.id)
        if query.first():
            raise ValidationError('Your group already has a role with that name.')


# ---------------------------------------------------------------------------
# Platform: groups
# ---------------------------------------------------------------------------

class GroupForm(FlaskForm):
    """Rename a group. The slug is fixed once created (URLs and folders use it)."""
    name = StringField('Group name', validators=[DataRequired(), Length(max=150)])
    submit = SubmitField('Save')


class GroupCreateForm(GroupForm):
    """A new group together with its first officer (Chairperson)."""
    slug = StringField(
        'URL slug', validators=[DataRequired(), Length(max=60)],
        render_kw={'placeholder': 'e.g. mzugoss'},
    )
    officer_email = StringField(
        'First officer email', validators=[DataRequired(), Email(), Length(max=150)],
    )
    officer_password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
        ],
    )
    confirm_password = PasswordField(
        'Confirm password',
        validators=[
            DataRequired(),
            EqualTo('officer_password', message='Passwords must match.'),
        ],
    )
    submit = SubmitField('Create group')

    def validate_slug(self, field):
        field.data = field.data.strip().lower()
        if not Group.is_valid_slug(field.data):
            raise ValidationError('Use lowercase letters, digits and single hyphens.')
        if Group.query.filter_by(slug=field.data).first():
            raise ValidationError('A group with that slug already exists.')


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