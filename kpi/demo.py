"""Namuna ma'lumot: sentabr 2026, 17-sanagacha. Dashboard va sinov uchun.

Raqamlar TZ'dagi sentabr misollariga yaqin qilib tanlangan, lekin bu haqiqiy
ma'lumot emas.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import Dataset, DailyEntry, Operator

AS_OF = date(2026, 9, 17)

# ism: (ulanish, sifat, qo'ng'iroq sek, sifatli lead/kun, sotuv/kun, chek)
_PROFILES = {
    "Aziza":    (118, 75.1, 111, 10, 3.4, 573_760),
    "Zuhra":    (126, 72.4, 116, 10, 2.7, 540_000),
    "Muxsima":  (109, 66.2, 109, 10, 3.2, 548_000),
    "Ruxshona": (112, 68.5, 104, 9, 2.9, 531_000),
    "Javohir":  (104, 67.9, 134, 10, 3.1, 441_000),
    "Ruxsora":  (98, 63.0, 97, 8, 2.1, 402_000),
}


def _wave(i: int, amp: float) -> float:
    """Juft kunlar sonida yig'indisi nolga teng tebranish."""
    return amp if i % 2 == 0 else -amp


def demo_dataset(as_of: date = AS_OF) -> Dataset:
    ds = Dataset(operators=[Operator(n) for n in _PROFILES] + [
        Operator("Mashhura", hire_date=date(2026, 9, 7), kind="yangi"),
        Operator("Behzod", hire_date=date(2026, 9, 2), kind="yangi"),
    ])
    start = as_of.replace(day=1)
    days = [start + timedelta(i) for i in range((as_of - start).days + 1)]
    days = [d for d in days if d.weekday() != 6]
    for idx, (name, (ul, sf, call, leads, sales, chek)) in enumerate(_PROFILES.items()):
        rest_day = days[(idx * 3 + 4) % len(days)]
        worked_i = 0
        sold_total = 0.0
        for d in days:
            if name == "Ruxsora" and d > as_of - timedelta(days=2):
                continue  # oxirgi 2 kun kiritilmagan
            if name == "Ruxsora" and d.day in (3, 4, 5, 8, 9, 10):
                ds.entries.append(DailyEntry(d, name, "kasal"))
                continue
            if d == rest_day:
                ds.entries.append(DailyEntry(d, name, "dam"))
                continue
            w = worked_i
            worked_i += 1
            target_sold = sales * worked_i
            sold = round(target_sold - sold_total)
            sold_total += sold
            ds.entries.append(DailyEntry(
                date=d, operator=name, status="ishladi",
                ulanish=ul + _wave(w, 9) + (w % 3 - 1) * 2,
                gaplashish_min=190 + _wave(w, 14),
                sifat=round(sf + _wave(w, 2.4), 2),
                call_sec=call + _wave(w, 6),
                lead=leads * 2, sifatli=leads, sotuv=sold,
                summa=round(sold * (chek + _wave(w, 18_000)))))
    for name in ("Mashhura", "Behzod"):
        op = ds.operator(name)
        for i, d in enumerate(x for x in days if x >= op.hire_date):
            ds.entries.append(DailyEntry(d, name, "ishladi", ulanish=80 + i, sifat=60,
                                         call_sec=90, lead=8, sifatli=4, sotuv=i % 2,
                                         summa=(i % 2) * 380_000))
    return ds
