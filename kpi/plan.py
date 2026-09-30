"""Oylik savdo rejasi: operatorlarga taqsimlash va bajarilishini kuzatish.

Formulalar (rahbar bilan kelishilgan):
  Kunlik suma   = Oylik suma / oydagi kunlar (31 — har operatorning dam olish
                  kuni har xil, shuning uchun kalendar kunlari olinadi)
  Haftalik suma = Kunlik suma × 7
  Mijoz oylik   = Oylik suma / o'rtacha chek (REJA_CHEK, 400 000)
  Mijoz kunlik  = Mijoz oylik / kunlar;  Mijoz haftalik = Mijoz kunlik × 7
  Kerakli sifatli lead = Mijoz oylik / konversiya maqsadi
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config as C
from .calc import month_end, month_start
from .models import Dataset
from .parsing import norm, to_date, to_number, to_text


def round_half_up(x: float, nd: int = 0) -> float:
    """Sheets ROUND bilan bir xil (62,5 → 63)."""
    q = 10 ** nd
    return math.floor(x * q + 0.5) / q


@dataclass
class PlanInput:
    month: date
    operator: str
    amount: float
    conversion: float          # maqsad, % (35 = 35%)
    avg_check: float | None = None
    note: str = ""


@dataclass
class PlanRow:
    month: date
    operator: str
    amount: float
    conversion: float
    avg_check: float
    note: str
    daily: float
    weekly: float
    clients_month: float
    clients_week: float
    clients_day: float
    leads_month: float
    leads_day: float
    # fakt (as_of holatiga)
    fact_amount: float = 0.0
    fact_clients: float = 0.0
    fact_leads: float = 0.0
    expected_amount: float = 0.0
    elapsed_days: int = 0
    remaining_days: int = 0
    week_fact: float = 0.0
    week_start: date | None = None
    weeks: list[dict] = field(default_factory=list)

    @property
    def completion(self) -> float:
        return self.fact_amount / self.amount * 100 if self.amount else 0.0

    @property
    def pace(self) -> float | None:
        """Shu kungacha bo'lishi kerak bo'lgan summaga nisbatan, %."""
        return self.fact_amount / self.expected_amount * 100 if self.expected_amount else None

    @property
    def forecast(self) -> float | None:
        total = self.elapsed_days + self.remaining_days
        return self.fact_amount / self.elapsed_days * total if self.elapsed_days else None

    @property
    def need_per_day(self) -> float:
        left = max(0.0, self.amount - self.fact_amount)
        return left / self.remaining_days if self.remaining_days else left

    @property
    def need_clients_per_day(self) -> float:
        left = max(0.0, self.clients_month - self.fact_clients)
        return left / self.remaining_days if self.remaining_days else left

    @property
    def fact_conversion(self) -> float | None:
        return self.fact_clients / self.fact_leads * 100 if self.fact_leads else None


def parse_plan(rows: list[list[object]] | None) -> list[PlanInput]:
    out = []
    for r in (rows or [])[1:]:
        r = list(r) + [None] * 6
        d, name, amount = to_date(r[0]), " ".join(to_text(r[1]).split()), to_number(r[2])
        if not d or not name or amount is None:
            continue
        conv = to_number(r[3]) or 0.0
        if 0 < conv <= 1:
            conv *= 100
        out.append(PlanInput(d.replace(day=1), name, amount, conv, to_number(r[4]), to_text(r[5])))
    return out


def plan_days(month: date, settings: C.Settings) -> int:
    fixed = settings.int("REJA_KUNLAR")
    return fixed if fixed > 0 else month_end(month).day


def month_days(month: date) -> list[date]:
    m0 = month_start(month)
    return [m0 + timedelta(i) for i in range(month_end(m0).day)]


def build_plan(inputs: list[PlanInput], settings: C.Settings, month: date) -> list[PlanRow]:
    days = plan_days(month, settings)
    rows = []
    for p in inputs:
        if p.month != month_start(month):
            continue
        check = p.avg_check or settings.get("REJA_CHEK")
        clients = p.amount / check
        leads = clients / (p.conversion / 100) if p.conversion else 0.0
        rows.append(PlanRow(
            month=p.month, operator=p.operator, amount=p.amount, conversion=p.conversion,
            avg_check=check, note=p.note,
            daily=round_half_up(p.amount / days), weekly=round_half_up(p.amount / days * 7),
            clients_month=round_half_up(clients, 1), clients_week=round_half_up(clients / days * 7, 1),
            clients_day=round_half_up(clients / days, 1),
            leads_month=round_half_up(leads), leads_day=round_half_up(leads / days, 1)))
    return rows


def track(rows: list[PlanRow], ds: Dataset, as_of: date) -> list[PlanRow]:
    """Faktni qo'shadi: oy boshidan `as_of` gacha (faqat "ishladi" kunlari)."""
    for r in rows:
        m0, m1 = r.month, month_end(r.month)
        end = min(as_of, m1)
        wd = month_days(m0)
        r.elapsed_days = sum(1 for d in wd if d <= end)
        r.remaining_days = sum(1 for d in wd if d > end)
        r.expected_amount = min(r.amount, r.daily * r.elapsed_days)
        wk_start = end - timedelta(days=end.weekday())
        r.week_start = wk_start
        r.fact_amount = r.fact_clients = r.fact_leads = r.week_fact = 0.0
        by_day: dict[date, float] = {}
        for e in ds.entries:
            if norm(e.operator) != norm(r.operator) or not (m0 <= e.date <= end) or not e.worked:
                continue
            r.fact_amount += e.summa or 0
            r.fact_clients += e.sotuv or 0
            r.fact_leads += e.sifatli or 0
            by_day[e.date] = by_day.get(e.date, 0) + (e.summa or 0)
            if e.date >= wk_start:
                r.week_fact += e.summa or 0
        r.weeks = calendar_weeks(r, wd, by_day, end)
    return rows


def calendar_weeks(r: PlanRow, wd: list[date], by_day: dict[date, float] | None = None,
                   as_of: date | None = None) -> list[dict]:
    """Oy haftalari (dushanba–yakshanba): kunlar soni va shu hafta uchun reja."""
    weeks: dict[date, list[date]] = {}
    for d in wd:
        weeks.setdefault(d - timedelta(days=d.weekday()), []).append(d)
    out = []
    for i, (start, days) in enumerate(sorted(weeks.items()), 1):
        fact = sum((by_day or {}).get(d, 0) for d in days) if by_day is not None else None
        out.append({
            "n": i, "from": days[0], "to": days[-1], "days": len(days),
            "amount": r.daily * len(days), "clients": round_half_up(r.clients_day * len(days), 1),
            "fact": fact, "done": bool(as_of and days[-1] <= as_of),
        })
    return out
