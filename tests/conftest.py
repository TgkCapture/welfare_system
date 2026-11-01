import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.user import User
from tests.workbooks import build_mzugoss_workbook


@pytest.fixture
def app(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'REPORT_FOLDER': str(tmp_path / 'reports'),
        'LOGS_FOLDER':   str(tmp_path / 'logs'),
    })
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
def make_user(app):
    def _make_user(email='admin@example.com', password='secret123', role='admin'):
        user = User(email=email, password=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        return user
    return _make_user


@pytest.fixture
def login(client):
    def _login(email='admin@example.com', password='secret123'):
        return client.post(
            '/auth/login',
            data={'email': email, 'password': password},
            follow_redirects=False,
        )
    return _login
