"""Hisob-kitob qoidalari (TZ 5-bo'lim) va oylik maosh (TZ 8-bo'lim)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config as C
from .models import Dataset, DailyEntry, Operator

EPS = 1e-9


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def is_workday(d: date) -> bool:
    return d.weekday() != 6  # yakshanba ish kuni emas


def workdays(start: date, end: date) -> int:
    if end < start:
        return 0
    return sum(1 for i in range((end - start).days + 1) if is_workday(start + timedelta(i)))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@dataclass
class Stats:
    """Davr bo'yicha operator ko'rsatkichlari."""
    worked_days: int = 0
    ulanish_n: int = 0
    ulanish_sum: float = 0.0
    sifat_n: int = 0
    sifat_sum: float = 0.0
    call_n: int = 0
    call_sum: float = 0.0
    talk_n: int = 0
    talk_sum: float = 0.0
    lead: float = 0.0
    sifatli: float = 0.0
    sotuv: float = 0.0
    summa: float = 0.0

    @property
    def ulanish(self) -> float | None:
        return self.ulanish_sum / self.ulanish_n if self.ulanish_n else None

    @property
    def sifat(self) -> float | None:
        return self.sifat_sum / self.sifat_n if self.sifat_n else None

    @property
    def gaplashish(self) -> float | None:
        """O'rtacha gaplashish (1 qo'ng'iroq), sek."""
        return self.call_sum / self.call_n if self.call_n else None

    @property
    def kunlik_gaplashish(self) -> float | None:
        """Kunlik gaplashish, daqiqa."""
        return self.talk_sum / self.talk_n if self.talk_n else None

    @property
    def konversiya(self) -> float | None:
        return self.sotuv / self.sifatli * 100 if self.sifatli > 0 else None

    @property
    def chek(self) -> float | None:
        return self.summa / self.sotuv if self.sotuv > 0 else None

    def value(self, kpi_key: str) -> float | None:
        return getattr(self, kpi_key)


def compute_stats(entries: list[DailyEntry], operator: str, start: date, end: date) -> Stats:
    """Faqat "ishladi" kunlari hisobga olinadi; bo'sh kataklar o'rtachaga kirmaydi."""
    st = Stats()
    for e in entries:
        if e.operator != operator or not (start <= e.date <= end) or not e.worked:
            continue
        st.worked_days += 1
        if e.ulanish is not None:
            st.ulanish_n += 1
            st.ulanish_sum += e.ulanish
        if e.sifat is not None:
            st.sifat_n += 1
            st.sifat_sum += e.sifat
        if e.call_sec is not None:
            st.call_n += 1
            st.call_sum += e.call_sec
        if e.gaplashish_min is not None:
            st.talk_n += 1
            st.talk_sum += e.gaplashish_min
        st.lead += e.lead or 0
        st.sifatli += e.sifatli or 0
        st.sotuv += e.sotuv or 0
        st.summa += e.summa or 0
    return st


def tier(value: float | None, tiers: list[tuple[float, float]]) -> tuple[int, float]:
    """(bosqich raqami 0..3, bonus). Eng yuqori mos bosqich olinadi."""
    level, bonus = 0, 0.0
    if value is None:
        return level, bonus
    for i, (threshold, amount) in enumerate(tiers, start=1):
        if value >= threshold - EPS:
            level, bonus = i, amount
    return level, bonus


@dataclass
class SalaryRow:
    operator: str
    kind: str
    hire_date: date | None
    worked_workdays: int
    fixa_full: float
    fixa: float
    prorated: bool
    values: dict[str, float | None] = field(default_factory=dict)
    levels: dict[str, int] = field(default_factory=dict)
    bonuses: dict[str, float] = field(default_factory=dict)
    kpi_total: float = 0.0
    late_days: int = 0
    work_hours: float = 0.0
    attendance_bonus: float = 0.0
    director_bonus: float = 0.0
    total: float = 0.0
    scenario_total: float = 0.0
    stats: Stats | None = None


def operators_for_month(ds: Dataset, month: date) -> list[Operator]:
    """Ketmaganlar va shu oyda ma'lumoti borlar (ketgan bo'lsa ham)."""
    m0, m1 = month_start(month), month_end(month)
    active_names = {e.operator for e in ds.entries if m0 <= e.date <= m1}
    out = []
    for op in ds.operators:
        if op.hire_date and op.hire_date > m1:
            continue
        if op.status != "ketgan" or op.name in active_names:
            out.append(op)
    return out


def worked_workdays(ds: Dataset, op: Operator, month: date) -> int:
    """Ishlagan ish kunlari: Davomat bo'lsa undan, bo'lmasa kalendardan."""
    m0, m1 = month_start(month), month_end(month)
    start = op.hire_date if op.hire_date and op.hire_date > m0 else m0
    dav = [a for a in ds.attendance if a.operator == op.name and m0 <= a.date <= m1]
    if dav:
        return sum(1 for a in dav if a.status == "keldi" and a.date >= start and is_workday(a.date))
    missed = sum(1 for e in ds.entries
                 if e.operator == op.name and start <= e.date <= m1
                 and e.status == "kelmadi" and is_workday(e.date))
    return workdays(start, m1) - missed


def compute_salary(ds: Dataset, settings: C.Settings, month: date,
                   as_of: date | None = None) -> list[SalaryRow]:
    """Oylik maosh jadvali. KPI qiymatlari `as_of` sanasigacha (standart: oy oxiri)."""
    m0, m1 = month_start(month), month_end(month)
    as_of = min(as_of or m1, m1)
    ish_kunlari = settings.get("ISH_KUNLARI")
    rows = []
    for op in operators_for_month(ds, month):
        fixa_full = op.fixa if op.fixa is not None else settings.get("FIXA")
        days = min(int(ish_kunlari), worked_workdays(ds, op, month))
        prorated = settings.int("FIXA_PROPORSIONAL") == 1 or bool(op.hire_date and op.hire_date > m0)
        fixa = round(fixa_full / ish_kunlari * days) if prorated else fixa_full
        scenario_fixa = settings.get("FIXA_SSENARIY")
        scenario_fixa = round(scenario_fixa / ish_kunlari * days) if prorated else scenario_fixa

        st = compute_stats(ds.entries, op.name, m0, as_of)
        row = SalaryRow(operator=op.name, kind=op.kind, hire_date=op.hire_date,
                        worked_workdays=days, fixa_full=fixa_full, fixa=fixa,
                        prorated=prorated, stats=st)
        for k in C.KPIS:
            value = st.value(k.key)
            level, bonus = tier(value, settings.tiers(k.prefix))
            if not op.gets_kpi:
                level, bonus = 0, 0.0
            row.values[k.key] = value
            row.levels[k.key] = level
            row.bonuses[k.key] = bonus
        row.kpi_total = sum(row.bonuses.values())

        dav = [a for a in ds.attendance if a.operator == op.name and m0 <= a.date <= m1]
        row.late_days = sum(1 for a in dav if (a.late_min or 0) > 0)
        row.work_hours = sum(a.hours or 0 for a in dav)
        if dav and op.gets_kpi and row.work_hours >= settings.get("DAV_SOAT") - EPS:
            if row.late_days == 0:
                row.attendance_bonus = settings.get("DAV_BONUS_0")
            elif row.late_days <= settings.get("DAV_MAX_KECH"):
                row.attendance_bonus = settings.get("DAV_BONUS_1")

        row.director_bonus = sum(b.amount for b in ds.director_bonuses
                                 if b.operator == op.name and b.month == m0)
        extras = row.kpi_total + row.attendance_bonus + row.director_bonus
        row.total = row.fixa + extras
        row.scenario_total = (scenario_fixa + extras) if op.gets_kpi else row.total
        rows.append(row)
    return rows
