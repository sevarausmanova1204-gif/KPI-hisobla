from datetime import date, timedelta

import pytest

from kpi.config import Settings
from kpi.models import Dataset, DailyEntry, Operator


def entry(d, name, status="ishladi", **kw):
    return DailyEntry(date=d, operator=name, status=status, **kw)


def days(start, n):
    """n ta ish kuni (yakshanbasiz)."""
    out, d = [], start
    while len(out) < n:
        if d.weekday() != 6:
            out.append(d)
        d += timedelta(days=1)
    return out


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def aziza():
    """Aziza, sentabr: konversiya 34%, chek 573 760, sifat 75,1%, 1:51, 118 ta."""
    ds = Dataset(operators=[Operator("Aziza")])
    calls = [110, 120, 118, 124, 118]
    sales = [3, 4, 3, 4, 3]
    summa = [1_950_000] * 4 + [9_753_920 - 4 * 1_950_000]
    for i, d in enumerate(days(date(2026, 9, 1), 5)):
        ds.entries.append(entry(d, "Aziza", ulanish=calls[i], gaplashish_min=205, sifat=75.1,
                                call_sec=111, lead=18, sifatli=10, sotuv=sales[i], summa=summa[i]))
    ds.entries.append(entry(date(2026, 9, 7), "Aziza", status="dam"))
    return ds
