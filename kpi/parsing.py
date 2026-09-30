"""Kataklardagi qiymatlarni o'qish: son, vaqt, sana.

Sheets API'dan UNFORMATTED_VALUE bilan, openpyxl'dan esa Python tiplari bilan
keladigan qiymatlarning ikkalasini ham tushunadi.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

_SERIAL_EPOCH = date(1899, 12, 30)
_CLOCK = re.compile(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$")


def is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def to_number(value: object) -> float | None:
    """'1 720 000', '76,64', '75,1%', 155 → float. Bo'sh yoki matn → None."""
    if is_blank(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    for junk in (" ", " ", " ", "so'm", "som", "%"):
        s = s.replace(junk, "")
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    if s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def to_duration_units(value: object) -> float | None:
    """'A:B' ko'rinishidagi vaqtni A*60+B ga aylantiradi.

    O'rtacha qo'ng'iroq (daq:son) uchun natija — soniya, kunlik gaplashish
    (soat:daqiqa) uchun — daqiqa. Sheets "1:43" ni 01:43 soat deb saqlasa ham
    kun ulushi × 1440 xuddi shu sonni beradi, shuning uchun ikkala holat bir xil.
    """
    if is_blank(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, timedelta):
        return value.total_seconds() / 60
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return value.hour * 60 + value.minute + value.second / 60
    if isinstance(value, (int, float)):
        # 1 dan kichik son — Sheets vaqti (kun ulushi); aks holda tayyor son
        return float(value) * 1440 if value < 1 else float(value)
    s = str(value).strip().lower().replace(" ", "")
    m = _CLOCK.match(s)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        return int(a) * 60 + int(b) + (int(c) / 60 if c else 0)
    # "3 soat 5 minut", "1 daqiqa 43 sekund" kabi matnli yozuvlar
    hours = re.search(r"(\d+)soat", s)
    minutes = re.search(r"(\d+)(?:daq|min)", s)
    seconds = re.search(r"(\d+)(?:sek|son)", s)
    if hours:
        return int(hours.group(1)) * 60 + (int(minutes.group(1)) if minutes else 0)
    if seconds:
        return (int(minutes.group(1)) if minutes else 0) * 60 + int(seconds.group(1))
    num = to_number(s)
    return num


def to_date(value: object) -> date | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _SERIAL_EPOCH + timedelta(days=int(value))
    s = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm(value: object) -> str:
    """Taqqoslash uchun: kichik harf, bo'shliqsiz, apostrof variantlari bir xil."""
    s = to_text(value).lower()
    for ch in ("ʻ", "ʼ", "`", "‘", "’"):
        s = s.replace(ch, "'")
    return s


def fmt_mmss(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def fmt_money(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"{int(round(amount)):,}".replace(",", " ")
