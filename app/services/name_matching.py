# app/services/name_matching.py
"""
Spotting names that may belong to one person ("Steve" / "Steven Ngoma",
"wapozga" / "wapozga Munyenyembe"). Used to suggest merges; never to merge
on its own.

Names are compared in normalised form (see models.member.normalise_name).
"""
import difflib

SIMILAR = 0.8


def similarity(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 2)


def may_be_same_person(a: str, b: str) -> bool:
    """True if two normalised names look like spellings of one name."""
    return a != b and (similarity(a, b) >= SIMILAR or short_form(a, b) or short_form(b, a))


def short_form(a: str, b: str) -> bool:
    """True if *a* could be a shorter or variant way of writing *b*.

    Every word of *a* must match a different word of *b*, in order, by starting
    it or by close spelling: 'chiso mwale' / 'chisomo mwale', 'wapozga' /
    'wapozga munyenyembe', 'agness' / 'agnes nomsa'. Same words in another
    order also count.
    """
    wa, wb = a.split(), b.split()
    if wa == wb or len(wa) > len(wb):
        return False
    if sorted(wa) == sorted(wb):
        return True
    rest = iter(wb)
    return all(any(_word_matches(x, y) for y in rest) for x in wa)


def _word_matches(x, y):
    return (len(x) >= 3 and y.startswith(x)) or difflib.SequenceMatcher(None, x, y).ratio() >= SIMILAR
