import re

from kpi import formulas as F
from kpi.config import DEFAULT_SETTINGS


def _balanced(s: str) -> bool:
    depth, in_str = 0, False
    for ch in s:
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            depth += ch == "("
            depth -= ch == ")"
            if depth < 0:
                return False
    return depth == 0 and not in_str


def all_formulas():
    yield from F.daily_calc_formulas()
    yield from (v for v in F.monthly_header_formulas().values() if v.startswith("="))
    yield from F.monthly_row_formulas(F.MONTHLY_FIRST_ROW)
    yield F.valid_clock("G2", 600)


def test_formulas_are_well_formed():
    for f in all_formulas():
        assert f.startswith("=") or f.startswith("OR(")
        assert _balanced(f), f


def test_column_counts():
    assert len(F.daily_calc_formulas()) == len(F.DAILY_CALC_HEADERS)
    assert len(F.monthly_row_formulas(5)) == len(F.MONTHLY_HEADERS) - 1


def test_named_ranges_exist_in_settings():
    keys = {k for k, _, _ in DEFAULT_SETTINGS}
    for f in all_formulas():
        for name in re.findall(r"\bS_([A-Z0-9_]+)", f):
            assert name in keys, name
