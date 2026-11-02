import pytest
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.group import Group, GroupSettings
from app.models.ledger import PayoutPurpose
from app.models.role import Role
from app.models.user import User
from tests.workbooks import build_mzugoss_workbook


class FreshContextClient(FlaskClient):
    """Test client that gives every request its own app context, as in production.

    Without this, requests reuse the fixture's app context, so values cached
    on ``g`` (such as Flask-Login's current user) leak between requests.
    """

    def open(self, *args, **kwargs):
        with self.application.app_context():
            response = super().open(*args, **kwargs)
        db.session.expire_all()   # let the test see changes the request made
        return response


@pytest.fixture
def app(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'REPORT_FOLDER': str(tmp_path / 'reports'),
        'LOGS_FOLDER':   str(tmp_path / 'logs'),
    })
    app.test_client_class = FreshContextClient
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mzugoss_workbook(tmp_path):
    return build_mzugoss_workbook(tmp_path / 'mzugoss.xlsx')


@pytest.fixture
def make_group(app):
    def _make_group(name='Mzugoss Class of 2018', slug='mzugoss'):
        group = Group(name=name, slug=slug)
        group.settings = GroupSettings(display_name=name)
        db.session.add(group)
        Role.seed_presets(group)
        PayoutPurpose.seed_defaults(group)
        db.session.commit()
        return group
    return _make_group


@pytest.fixture
def group(make_group):
    return make_group()


@pytest.fixture
def make_user(app, group):
    """Create an officer holding one of the group's roles, by role name."""
    def _make_user(email='admin@example.com', password='secret123', role='Chairperson',
                   group=group, is_active=True):
        user = User(
            email=email, password=generate_password_hash(password),
            group_id=group.id, is_active=is_active,
            role=Role.query.filter_by(group_id=group.id, name=role).one(),
        )
        db.session.add(user)
        db.session.commit()
        return user
    return _make_user


@pytest.fixture
def make_superadmin(app):
    def _make_superadmin(email='root@example.com', password='secret123'):
        user = User(email=email, password=generate_password_hash(password), is_superadmin=True)
        db.session.add(user)
        db.session.commit()
        return user
    return _make_superadmin


@pytest.fixture
def login(client):
    """Sign in on a group's login page (or /platform/login with slug=None)."""
    def _login(email='admin@example.com', password='secret123', slug='mzugoss', next=None):
        url = f'/g/{slug}/login' if slug else '/platform/login'
        if next:
            url += f'?next={next}'
        return client.post(url, data={'email': email, 'password': password})
    return _login
