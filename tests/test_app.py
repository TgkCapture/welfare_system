import os

from app.models.report import GeneratedReport


def test_testing_config_ignores_instance_config(app):
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'


def test_health_check(client):
    assert client.get('/api/health').status_code == 200


def test_login_page_renders(client):
    assert client.get('/auth/login').status_code == 200


def test_upload_requires_login(client):
    response = client.get('/upload-dashboard')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_upload_generates_and_records_report(app, client, make_user, login, mzugoss_workbook):
    make_user()
    login()

    with open(mzugoss_workbook, 'rb') as fh:
        response = client.post(
            '/upload',
            data={'file': (fh, 'mzugoss.xlsx'), 'year': '2026', 'month': '3'},
            content_type='multipart/form-data',
        )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/reports/preview')

    report = GeneratedReport.query.one()
    assert (report.month, report.year) == (3, 2026)
    assert report.total_contributions == 2500.0
    assert report.contributors_count == 3
    assert report.defaulters_count == 4
    assert os.path.exists(report.file_path)
