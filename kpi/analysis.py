"""Avtomatik tahlil va maslahatlar (TZ 6-bo'lim)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config as C
from .calc import (SalaryRow, Stats, compute_salary, compute_stats, is_workday,
                   month_end, month_start, workdays)
from .models import Dataset
from .parsing import fmt_mmss, fmt_money

GREEN, YELLOW, RED, NODATA = "yashil", "sariq", "qizil", "yo'q"
EMOJI = {GREEN: "🟢", YELLOW: "🟡", RED: "🔴", NODATA: "⚪"}

# Qolgan kunlarda erishib bo'lmaydigan kunlik qiymat chegaralari
_MAX_DAILY = {"ulanish": 400, "sifat": 100, "gaplashish": 600}


def fmt_value(kpi_key: str, value: float | None) -> str:
    if value is None:
        return "—"
    if kpi_key in ("konversiya", "sifat"):
        if abs(value - round(value)) < 1e-9:
            return f"{value:.0f}%"
        return f"{value:.1f}%".replace(".", ",")
    if kpi_key == "gaplashish":
        return fmt_mmss(value)
    if kpi_key == "chek":
        return fmt_money(value)
    return f"{value:.0f}"


def fmt_gap(kpi_key: str, gap: float) -> str:
    if kpi_key in ("konversiya", "sifat"):
        return f"{gap:.1f} punkt".replace(".", ",")
    if kpi_key == "gaplashish":
        return f"{math.ceil(gap - 1e-9)} sek"
    if kpi_key == "chek":
        return f"{fmt_money(gap)} so'm"
    return f"{math.ceil(gap - 1e-9)} ta"


@dataclass
class KpiStatus:
    key: str
    value: float | None
    level: int
    bonus: float
    status: str
    next_threshold: float | None = None
    gap: float | None = None
    next_bonus_delta: float = 0.0
    need_text: str = ""
    reachable: bool = True

    @property
    def kpi(self) -> C.KpiDef:
        return C.KPI_BY_KEY[self.key]

    def distance_text(self) -> str:
        """"sifat 67,9% → 70% ga 2,1 punkt kerak = +360 000 so'm"."""
        if self.gap is None or self.next_threshold is None:
            return ""
        return (f"{self.kpi.name.lower()} {fmt_value(self.key, self.value)} → "
                f"{fmt_value(self.key, self.next_threshold)} ga {fmt_gap(self.key, self.gap)} kerak"
                f" = +{fmt_money(self.next_bonus_delta)} so'm")


@dataclass
class Action:
    kpi_key: str | None     # None = ma'lumot yo'q
    title: str
    action: str
    owner: str
    deadline: str
    detail: str = ""


@dataclass
class OperatorAnalysis:
    operator: str
    kpis: list[KpiStatus]
    actions: list[Action] = field(default_factory=list)
    model: bool = False
    missing_days: int = 0
    salary: SalaryRow | None = None
    remaining_days: int = 0

    @property
    def behind(self) -> bool:
        return any(k.status in (RED, YELLOW, NODATA) for k in self.kpis) or self.missing_days > 0


def status_of(value: float | None, tiers: list[tuple[float, float]], yellow_pct: float) -> str:
    if value is None or not tiers:
        return NODATA
    t1 = tiers[0][0]
    if value >= t1 - 1e-9:
        return GREEN
    if value >= t1 * yellow_pct / 100:
        return YELLOW
    return RED


def _need(kpi_key: str, st: Stats, target: float, n: int) -> tuple[str, bool]:
    """Qolgan n ish kunida chegaraga chiqish uchun kunlik kerakli qiymat."""
    if n <= 0:
        return "oy tugadi", False
    if kpi_key in ("ulanish", "sifat", "gaplashish"):
        cnt, total = {"ulanish": (st.ulanish_n, st.ulanish_sum),
                      "sifat": (st.sifat_n, st.sifat_sum),
                      "gaplashish": (st.call_n, st.call_sum)}[kpi_key]
        need = (target * (cnt + n) - total) / n
        ok = need <= _MAX_DAILY[kpi_key]
        if kpi_key == "ulanish":
            txt = f"qolgan {n} kunda kuniga o'rtacha {math.ceil(need - 1e-9)} ta qo'ng'iroq kerak"
        elif kpi_key == "sifat":
            txt = f"qolgan {n} kunda o'rtacha {need:.1f}% sifat kerak".replace(".", ",")
        else:
            txt = f"qolgan {n} kunda o'rtacha {fmt_mmss(need)} gaplashish kerak"
        return (txt if ok else txt + " (bu oyda erishib bo'lmaydi)"), ok
    days = max(st.worked_days, 1)
    if kpi_key == "konversiya":
        leads_per_day = st.sifatli / days
        expected_leads = st.sifatli + leads_per_day * n
        extra = target / 100 * expected_leads - st.sotuv
        per_day = math.ceil(extra / n - 1e-9)
        ok = extra / n <= leads_per_day + 1e-9 and leads_per_day > 0
        txt = (f"{fmt_value('konversiya', target)} ga chiqishi uchun qolgan {n} kunda "
               f"har kuni {max(per_day, 1)} ta sotuv kerak")
        return (txt if ok else txt + " (lead yetmaydi)"), ok
    # chek
    sales_per_day = st.sotuv / days
    new_sales = sales_per_day * n
    if new_sales <= 0:
        return "sotuv yo'q", False
    need = (target * (st.sotuv + new_sales) - st.summa) / new_sales
    return (f"qolgan {n} kunda yangi sotuvlarda o'rtacha chek {fmt_money(need)} so'm bo'lishi kerak"), True


def missing_workdays(ds: Dataset, operator: str, as_of: date, hire: date | None) -> int:
    """`as_of` dan orqaga ketma-ket nechta ish kuni uchun qator kiritilmagan."""
    dates = {e.date for e in ds.entries if e.operator == operator}
    count, d = 0, as_of
    m0 = month_start(as_of)
    while d >= m0 and (hire is None or d >= hire):
        if is_workday(d):
            if d in dates:
                break
            count += 1
        d -= timedelta(days=1)
    return count


def analyze(ds: Dataset, settings: C.Settings, as_of: date) -> list[OperatorAnalysis]:
    m0, m1 = month_start(as_of), month_end(as_of)
    remaining = workdays(as_of + timedelta(days=1), m1)
    yellow = settings.get("SARIQ_FOIZ")
    max_actions = settings.int("MAX_CHORA")
    salaries = {r.operator: r for r in compute_salary(ds, settings, as_of, as_of)}
    out = []
    for op in ds.operators:
        if op.status == "ketgan" or not op.gets_kpi or op.name not in salaries:
            continue
        st = compute_stats(ds.entries, op.name, m0, as_of)
        kpis = []
        for k in C.KPIS:
            tiers = settings.tiers(k.prefix)
            value = st.value(k.key)
            row = salaries[op.name]
            ks = KpiStatus(key=k.key, value=value, level=row.levels[k.key],
                           bonus=row.bonuses[k.key], status=status_of(value, tiers, yellow))
            if value is not None and ks.level < len(tiers):
                threshold, next_bonus = tiers[ks.level]
                ks.next_threshold = threshold
                ks.gap = threshold - value
                ks.next_bonus_delta = next_bonus - ks.bonus
                ks.need_text, ks.reachable = _need(k.key, st, threshold, remaining)
            kpis.append(ks)

        oa = OperatorAnalysis(operator=op.name, kpis=kpis, salary=salaries[op.name],
                              remaining_days=remaining)
        oa.missing_days = missing_workdays(ds, op.name, as_of, op.hire_date)
        actions: list[Action] = []
        if oa.missing_days >= settings.int("MALUMOT_YOQ_KUN"):
            title, act, owner, deadline = C.NO_DATA_ACTION
            actions.append(Action(None, title, act, owner, deadline,
                                  f"{oa.missing_days} ish kuni ma'lumot yo'q"))
        # Bonusga yetmagan ko'rsatkichlar: eng katta pul ta'siri bor ikkitasi,
        # ichida chegaraga eng yaqini birinchi.
        weak = [k for k in kpis if k.status in (RED, YELLOW) and k.gap is not None]
        weak.sort(key=lambda k: (not k.reachable, -k.next_bonus_delta, k.gap / k.next_threshold))
        chosen = weak[:max(0, max_actions - len(actions))]
        chosen.sort(key=lambda k: (not k.reachable, k.gap / k.next_threshold))
        for k in chosen:
            detail = k.distance_text()
            if k.need_text:
                detail += f"; {k.need_text}"
            actions.append(Action(k.key, k.kpi.name, k.kpi.action, k.kpi.owner,
                                  k.kpi.deadline, detail))
        oa.actions = actions
        oa.model = all(k.status == GREEN for k in kpis)
        out.append(oa)
    return out


# ---- Haftalik -------------------------------------------------------------

@dataclass
class WeeklyRow:
    operator: str
    this_week: Stats
    prev_week: Stats
    kpi_total: float
    action_results: list[tuple[str, float | None, float | None]] = field(default_factory=list)


def week_bounds(any_day: date) -> tuple[date, date]:
    start = any_day - timedelta(days=any_day.weekday())
    return start, start + timedelta(days=6)


def weekly(ds: Dataset, settings: C.Settings, week_end: date,
           past_actions: list[tuple[date, str, str]] | None = None) -> list[WeeklyRow]:
    """`past_actions`: [(sana, operator, kpi_key)] — o'tgan hafta berilgan choralar."""
    start, end = week_bounds(week_end)
    p_start, p_end = start - timedelta(days=7), start - timedelta(days=1)
    salaries = {r.operator: r for r in compute_salary(ds, settings, end, end)}
    rows = []
    for op in ds.operators:
        if op.status == "ketgan" or not op.gets_kpi:
            continue
        cur = compute_stats(ds.entries, op.name, start, end)
        prev = compute_stats(ds.entries, op.name, p_start, p_end)
        wr = WeeklyRow(op.name, cur, prev,
                       salaries[op.name].kpi_total if op.name in salaries else 0.0)
        seen = set()
        for d, name, kpi_key in past_actions or []:
            if name != op.name or kpi_key not in C.KPI_BY_KEY or kpi_key in seen:
                continue
            if p_start <= d <= end:
                seen.add(kpi_key)
                wr.action_results.append((kpi_key, prev.value(kpi_key), cur.value(kpi_key)))
        rows.append(wr)
    return rows


def expected_entries(ds: Dataset, day: date) -> list[str]:
    """Shu kun uchun qator kutilayotgan, lekin kiritilmagan operatorlar."""
    if not is_workday(day):
        return []
    have = {e.operator for e in ds.entries if e.date == day}
    return [op.name for op in ds.operators
            if op.status != "ketgan" and (op.hire_date is None or op.hire_date <= day)
            and op.name not in have]


def sales_mismatches(ds: Dataset, day: date) -> list[str]:
    """Kunlik_sotuv va Kunlik_kiritish orasidagi farqlar."""
    out = []
    by_op: dict[str, list[float]] = {}
    for s in ds.sales:
        if s.date == day:
            by_op.setdefault(s.operator, []).append(s.amount)
    for e in ds.entries:
        if e.date != day or e.operator not in by_op:
            continue
        amounts = by_op[e.operator]
        if (e.sotuv or 0) != len(amounts) or abs((e.summa or 0) - sum(amounts)) > 0.5:
            out.append(f"{e.operator}: kiritish {int(e.sotuv or 0)} ta / {fmt_money(e.summa or 0)}, "
                       f"Kunlik_sotuv {len(amounts)} ta / {fmt_money(sum(amounts))}")
    return out
