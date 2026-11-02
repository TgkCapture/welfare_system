# app/services/branding.py
"""
How a group presents itself: its name in page titles and headers, its
report title, currency and colour. Built from GroupSettings, with platform
defaults when there is no group (superadmins, the login finder).

Templates get it as ``brand``: the signed-in officer's group, or the group
whose public page is being shown (set with ``use_group_brand``).
"""
import re
from dataclasses import dataclass

from flask import g

from app.models.tenancy import current_group

PLATFORM_NAME = 'Welfare System'
DEFAULT_COLOR = '#1d4ed8'
_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


@dataclass(frozen=True)
class Brand:
    name: str                   # full name, e.g. in page titles
    short_name: str             # for the header logo
    report_title: str           # heading of contribution reports
    currency: str
    color: str
    slug: str = None
    logo: str = None            # the logo's file name, which changes when it is replaced
    logo_file: str = None       # its path on disk, for PDFs

    @property
    def file_prefix(self) -> str:
        """A safe start for download filenames."""
        return self.slug or 'welfare'

    @property
    def rgb(self) -> str:
        """The colour as CSS channels ("29 78 216") for --brand-rgb."""
        return ' '.join(str(c) for c in _channels(self.color))

    @property
    def dark_rgb(self) -> str:
        """A darker shade of the colour, for hover states."""
        return ' '.join(str(int(c * 0.85)) for c in _channels(self.color))


def _channels(color):
    color = color if is_valid_color(color) else DEFAULT_COLOR
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


PLATFORM = Brand(PLATFORM_NAME, 'Welfare', 'Monthly contributions report', 'MWK', DEFAULT_COLOR)


def is_valid_color(value: str) -> bool:
    return bool(_HEX.match(value or ''))


def brand_for(group) -> Brand:
    if group is None:
        return PLATFORM
    from app.services import logo
    s = group.settings
    name = (s.display_name if s and s.display_name else group.name)
    logo_file = logo.path_for(group)
    return Brand(
        name=name,
        short_name=(s.short_name if s and s.short_name else name),
        report_title=(s.report_title if s and s.report_title else f'{name} — monthly contributions report'),
        currency=(s.currency if s and s.currency else 'MWK'),
        color=(s.primary_color if s and is_valid_color(s.primary_color) else DEFAULT_COLOR),
        slug=group.slug,
        logo=s.logo_path if logo_file else None,
        logo_file=logo_file,
    )


def use_group_brand(group) -> None:
    """Show *group*'s branding on this request's public page."""
    g.brand_group = group


def current_brand() -> Brand:
    return brand_for(g.get('brand_group') or current_group())
