# app/services/rules_markup.py
"""
The small formatting syntax officers use to write welfare rules.

    Blank lines separate blocks.
    - item          a bulleted list (or "* item")
    1. item         a numbered list
    > text          a highlighted note or example
    anything else   a paragraph
    **bold**  *italic*

Everything is HTML-escaped first, so officers can't (even by accident)
put HTML or scripts on the public page. The only markup in the output is
<b> and <i>, which both the web page and ReportLab's PDF paragraphs
understand, so one parse feeds both.
"""
import re
from dataclasses import dataclass

from markupsafe import Markup, escape

_BULLET = re.compile(r'^\s*[-*]\s+(.*)$')
_NUMBER = re.compile(r'^\s*\d+[.)]\s+(.*)$')
_NOTE = re.compile(r'^\s*>\s?(.*)$')
_BOLD = re.compile(r'\*\*(.+?)\*\*')
_ITALIC = re.compile(r'(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)')


@dataclass
class Block:
    kind: str           # 'p', 'ul', 'ol' or 'note'
    items: list         # inline markup (Markup) — one item for 'p' and 'note'


def inline(text: str) -> Markup:
    """Escape *text*, then turn **bold** and *italic* into <b> and <i>."""
    html = str(escape(text))
    html = _BOLD.sub(r'<b>\1</b>', html)
    html = _ITALIC.sub(lambda m: f'<i>{m.group(1) or m.group(2)}</i>', html)
    return Markup(html)


def parse(body: str) -> list:
    """Split a section body into blocks."""
    blocks = []
    for chunk in re.split(r'\n\s*\n', (body or '').replace('\r\n', '\n').strip()):
        current = None                        # a blank line always starts a new block
        for line in chunk.split('\n'):
            if not line.strip():
                continue
            kind, text = _classify(line)
            if current is not None and current.kind == kind:
                if kind in ('ul', 'ol'):
                    current.items.append(inline(text))
                else:                         # paragraph and note lines run on
                    current.items[0] = Markup(f'{current.items[0]} {inline(text)}')
            else:
                current = Block(kind, [inline(text)])
                blocks.append(current)
    return blocks


def _classify(line):
    for kind, pattern in (('ul', _BULLET), ('ol', _NUMBER), ('note', _NOTE)):
        match = pattern.match(line)
        if match:
            return kind, match.group(1)
    return 'p', line.strip()
