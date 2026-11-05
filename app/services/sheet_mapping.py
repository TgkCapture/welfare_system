# app/services/sheet_mapping.py
"""
Where to find things in a group's workbook when it isn't the standard layout.

Every option left at its default means "work it out", which is how the
original Mzugoss layout is read: one sheet per year (named after the year),
the header found by the row holding the month's name, the name column
headed "Name", and Money Dispensed / Total Book Balance rows above the
header. A group whose sheet differs sets only what differs.

Columns are given as spreadsheet letters (A, B, …) and rows as numbers,
as officers see them in Excel or Google Sheets.
"""
import re
from dataclasses import asdict, dataclass, fields

SHEET_MODES = {
    'year':  'One sheet per year',
    'first': 'Always the first sheet',
    'named': 'A sheet with a fixed name',
}
FINANCIALS = {
    'auto':  'Find "Money dispensed" and "Total book balance" rows',
    'cells': 'Read them from given cells',
    'none':  'The sheet has neither',
}
_COLUMN = re.compile(r'^[A-Z]{1,3}$')
_CELL = re.compile(r'^([A-Z]{1,3})([1-9][0-9]*)$')


@dataclass
class SheetMapping:
    sheet_mode: str = 'year'
    # For 'year': the sheet name with {year} in it, e.g. "Contributions {year}".
    # Blank: any sheet whose name contains the year (falling back as the original layout did).
    sheet_pattern: str = ''
    sheet_name: str = ''              # for 'named'
    header_row: int = None            # blank: the row holding the month's name
    name_column: str = ''             # blank: the column headed "Name"
    january_column: str = ''          # blank: each month's column found by its header
    financials: str = 'auto'
    money_dispensed_cell: str = ''
    book_balance_cell: str = ''

    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data) -> 'SheetMapping':
        data = data or {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_form(cls, form) -> 'SheetMapping':
        """Build from submitted form fields (blank text means automatic)."""
        def text(name, upper=False):
            value = (form.get(name) or '').strip()
            return value.upper() if upper else value
        header = text('header_row')
        return cls(
            sheet_mode=text('sheet_mode') or 'year',
            sheet_pattern=text('sheet_pattern'),
            sheet_name=text('sheet_name'),
            header_row=int(header) if header.isdigit() else (header or None),
            name_column=text('name_column', upper=True),
            january_column=text('january_column', upper=True),
            financials=text('financials') or 'auto',
            money_dispensed_cell=text('money_dispensed_cell', upper=True),
            book_balance_cell=text('book_balance_cell', upper=True),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def is_automatic(self) -> bool:
        return self == SheetMapping()

    def errors(self) -> list:
        """Problems with the settings themselves, as sentences for the officer."""
        problems = []
        if self.sheet_mode not in SHEET_MODES:
            problems.append('Choose how the sheet is picked.')
        if self.sheet_mode == 'year' and self.sheet_pattern and '{year}' not in self.sheet_pattern:
            problems.append('The sheet name pattern needs {year} where the year goes, e.g. "Contributions {year}".')
        if self.sheet_mode == 'named' and not self.sheet_name:
            problems.append('Give the name of the sheet to read.')
        if self.header_row is not None and not (isinstance(self.header_row, int) and self.header_row >= 1):
            problems.append('The header row must be a row number (1 or more), or blank.')
        for label, value in (('name column', self.name_column), ('January column', self.january_column)):
            if value and not _COLUMN.match(value):
                problems.append(f'The {label} must be a column letter such as B, or blank.')
        if self.january_column and self.header_row is None:
            problems.append('With a fixed January column, also give the header row (the row above the first member).')
        if self.financials not in FINANCIALS:
            problems.append('Choose where money dispensed and the book balance are.')
        if self.financials == 'cells':
            for label, value in (('money dispensed', self.money_dispensed_cell),
                                 ('book balance', self.book_balance_cell)):
                if value and not _CELL.match(value):
                    problems.append(f'The {label} cell must look like B2, or be blank.')
        return problems


def column_index(letter: str) -> int:
    """0-based column index from a letter (A → 0)."""
    index = 0
    for ch in letter:
        index = index * 26 + (ord(ch) - ord('A') + 1)
    return index - 1


def cell_position(ref: str):
    """(0-based row, 0-based column) from a cell reference like B2."""
    match = _CELL.match(ref)
    return int(match.group(2)) - 1, column_index(match.group(1))


def column_letter(index: int) -> str:
    """A spreadsheet letter from a 0-based column index."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord('A') + rest) + letters
    return letters
