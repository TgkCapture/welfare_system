# app/services/logo.py
"""
Group logos.

An uploaded image is opened with Pillow, checked, shrunk to fit LOGO_SIZE
and saved again as PNG: only the pixels are kept, never the uploaded file
itself (so no metadata, scripts or odd formats reach the app). SVG is not
accepted because it can carry scripts.

Logos live in BRANDING_FOLDER/<slug>/, apart from uploads and reports
(which expire), under a new name each time so browsers pick up a change.
"""
import os
import secrets

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from app.extensions import db
from app.models.group import Group

LOGO_SIZE = 256                       # pixels, longest side
MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 25_000_000               # refuse huge images before decoding them
ALLOWED_FORMATS = {'PNG', 'JPEG', 'WEBP', 'GIF'}


class LogoError(ValueError):
    """An image that can't be used, with a message for the officer."""


def folder(group) -> str:
    if not Group.is_valid_slug(group.slug):
        raise ValueError(f'Invalid group slug {group.slug!r}.')
    path = os.path.join(current_app.config['BRANDING_FOLDER'], group.slug)
    os.makedirs(path, exist_ok=True)
    return path


def path_for(group):
    """The group's logo file on disk, or None."""
    name = group.settings.logo_path if group.settings else None
    if not name:
        return None
    path = os.path.join(current_app.config['BRANDING_FOLDER'], group.slug, name)
    return path if os.path.isfile(path) else None


def save(group, upload) -> None:
    """Replace the group's logo with the uploaded image (a werkzeug FileStorage)."""
    data = upload.read(MAX_BYTES + 1)
    if not data:
        raise LogoError('Choose an image file.')
    if len(data) > MAX_BYTES:
        raise LogoError('The image is too large: use one under 2 MB.')
    try:
        from io import BytesIO
        image = Image.open(BytesIO(data))
        if image.format not in ALLOWED_FORMATS:
            raise LogoError('Use a PNG, JPEG, WebP or GIF image.')
        if image.width * image.height > MAX_PIXELS:
            raise LogoError('The image has too many pixels: use a smaller one.')
        image.load()
    except (UnidentifiedImageError, OSError):
        raise LogoError("That file isn't an image we can read: use a PNG, JPEG, WebP or GIF.")

    image = ImageOps.exif_transpose(image).convert('RGBA')
    image.thumbnail((LOGO_SIZE, LOGO_SIZE))
    name = f'logo-{secrets.token_hex(6)}.png'
    image.save(os.path.join(folder(group), name), format='PNG', optimize=True)

    _delete_file(group)
    group.settings.logo_path = name
    db.session.commit()


def remove(group) -> None:
    _delete_file(group)
    group.settings.logo_path = None
    db.session.commit()


def _delete_file(group):
    old = path_for(group)
    if old:
        try:
            os.remove(old)
        except OSError as e:
            current_app.logger.warning(f'Could not remove old logo {old}: {e}')
