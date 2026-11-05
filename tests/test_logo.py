"""
Group logos: uploaded with the branding settings, re-encoded and stored per
group, served from /g/<slug>/logo.png and shown in the app and on PDFs.
"""
import io
import os

import pytest
from PIL import Image

from app.extensions import db
from app.models.group import Group
from app.services import logo
from app.services.branding import brand_for
from app.services.pdf_service import PDFGenerator

BRANDING = {'section': 'branding', 'display_name': 'Mzugoss', 'short_name': '', 'currency': 'MWK',
            'primary_color': '#1d4ed8', 'report_title': ''}


def _image(fmt='PNG', size=(600, 300), color='red'):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format=fmt)
    buf.seek(0)
    return buf


@pytest.fixture
def chair(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')


def _upload(client, data, name='logo.png'):
    return client.post('/settings', data={**BRANDING, 'logo': (data, name)}, content_type='multipart/form-data')


def test_upload_is_resized_reencoded_and_served(app, client, group, chair):
    _upload(client, _image('JPEG'), name='logo.jpg')

    settings = db.session.get(Group, group.id).settings
    path = logo.path_for(db.session.get(Group, group.id))
    assert settings.logo_path.endswith('.png') and path.startswith(app.config['BRANDING_FOLDER'])
    with Image.open(path) as img:
        assert img.format == 'PNG' and max(img.size) == logo.LOGO_SIZE

    page = client.get('/').data.decode()
    assert f'/g/mzugoss/logo.png?v={settings.logo_path}' in page
    served = client.get('/g/mzugoss/logo.png')
    assert served.mimetype == 'image/png' and served.data.startswith(b'\x89PNG')


def test_replacing_a_logo_removes_the_old_file(client, group, chair):
    _upload(client, _image())
    first = logo.path_for(db.session.get(Group, group.id))
    _upload(client, _image(color='blue'))
    assert not os.path.exists(first)
    assert logo.path_for(db.session.get(Group, group.id)) != first


def test_logo_can_be_removed(client, group, chair):
    _upload(client, _image())
    path = logo.path_for(db.session.get(Group, group.id))
    client.post('/settings', data={**BRANDING, 'remove_logo': '1'})
    assert db.session.get(Group, group.id).settings.logo_path is None
    assert not os.path.exists(path)
    assert client.get('/g/mzugoss/logo.png').status_code == 404


@pytest.mark.parametrize('payload,name', [
    (io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'), 'logo.svg'),
    (io.BytesIO(b'not an image at all'), 'logo.png'),
    (io.BytesIO(b'x' * (logo.MAX_BYTES + 10)), 'big.png'),
])
def test_unusable_files_are_refused(client, group, chair, payload, name):
    response = _upload(client, payload, name=name)
    assert response.status_code == 302
    assert db.session.get(Group, group.id).settings.logo_path is None
    assert b'the logo was not' in client.get('/settings').data


def test_logo_is_per_group(client, group, make_group, chair):
    make_group(name='Another Welfare', slug='another')
    _upload(client, _image())
    assert client.get('/g/another/logo.png').status_code == 404
    assert brand_for(Group.query.filter_by(slug='another').one()).logo is None


def test_pdfs_carry_the_logo(app, client, group, chair):
    plain = PDFGenerator.generate_welfare_rules_pdf(brand_for(group), [])
    _upload(client, _image())
    with_logo = PDFGenerator.generate_welfare_rules_pdf(brand_for(db.session.get(Group, group.id)), [])
    assert b'/Subtype /Image' in with_logo and b'/Subtype /Image' not in plain
