"""Ma'lumot modellari va varaq qatorlaridan ularni yig'ish."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import config as C
from .parsing import norm, to_date, to_duration_units, to_number, to_text


@dataclass
class Operator:
    name: str
    hire_date: date | None = None
    fixa: float | None = None
    status: str = "faol"
    kind: str = "operator"
    telegram_id: str = ""

    @property
    def gets_kpi(self) -> bool:
        return self.kind == "operator"


@dataclass
class DailyEntry:
    date: date
    operator: str
    status: str
    ulanish: float | None = None
    gaplashish_min: float | None = None
    sifat: float | None = None
    call_sec: float | None = None
    lead: float | None = None
    sifatli: float | None = None
    sotuv: float | None = None
    summa: float | None = None

    @property
    def worked(self) -> bool:
        return self.status == C.WORKED


@dataclass
class Attendance:
    date: date
    operator: str
    status: str
    late_min: float | None = None
    hours: float | None = None


@dataclass
class Sale:
    date: date
    operator: str
    amount: float
    lead_type: str = ""


@dataclass
class DirectorBonus:
    month: date
    operator: str
    amount: float
    note: str = ""


@dataclass
class Dataset:
    operators: list[Operator] = field(default_factory=list)
    entries: list[DailyEntry] = field(default_factory=list)
    attendance: list[Attendance] = field(default_factory=list)
    sales: list[Sale] = field(default_factory=list)
    director_bonuses: list[DirectorBonus] = field(default_factory=list)
    plans: list = field(default_factory=list)       # plan.PlanInput

    def operator(self, name: str) -> Operator | None:
        for op in self.operators:
            if op.name == name:
                return op
        return None


# Varaq sarlavhalari (setup va o'qish uchun bir xil)
HEADERS = {
    C.SH_OPERATORS: ["Ism", "Ishga kirgan sana", "Fixa", "Holat", "Turi", "Telegram ID",
                     "Boshqa yozilishi (vergul bilan)"],
    C.SH_DAILY: ["Sana", "Operator", "Holat", "Ulanish (qo'ng'iroq)", "Kunlik gaplashish",
                 "Sifat", "O'rtacha qo'ng'iroq", "Umumiy lead", "Sifatli lead",
                 "Sotuv soni", "Sotuv summasi"],
    C.SH_SALES: ["Sana", "Operator", "Summa", "Lead turi"],
    C.SH_ATTENDANCE: ["Sana", "Operator", "Holat", "Kechikish (daq)", "Ish soati"],
    C.SH_DIRECTOR: ["Oy", "Operator", "Summa", "Izoh"],
    C.SH_SETTINGS: ["Kalit", "Qiymat", "Izoh"],
    C.SH_PLAN: ["Oy", "Operator", "Oylik reja (so'm)", "Konversiya maqsadi %",
                "O'rtacha chek (bo'sh = Sozlamalar)", "Izoh"],
}


def _rows(rows: list[list[object]] | None) -> list[list[object]]:
    """Sarlavhani tashlab, bo'sh qatorlarni o'tkazib yuboradi."""
    out = []
    for row in (rows or [])[1:]:
        if any(to_text(v) for v in row):
            out.append(list(row) + [None] * 12)
    return out


def _name(value: object) -> str:
    return " ".join(to_text(value).split())


def parse_settings(rows: list[list[object]] | None) -> C.Settings:
    values = {}
    for row in _rows(rows):
        key = to_text(row[0]).upper()
        if key:
            values[key] = row[1]
    return C.Settings(values)


def parse_dataset(sheets: dict[str, list[list[object]]]) -> Dataset:
    ds = Dataset()
    aliases: dict[str, list[str]] = {}
    for r in _rows(sheets.get(C.SH_OPERATORS)):
        name = _name(r[0])
        if not name:
            continue
        aliases[name] = [_name(a) for a in to_text(r[6]).split(",") if _name(a)]
        kind = norm(r[4]) or "operator"
        ds.operators.append(Operator(
            name=name, hire_date=to_date(r[1]), fixa=to_number(r[2]),
            status=norm(r[3]) or "faol",
            kind=kind if kind in C.OPERATOR_KINDS else "operator",
            telegram_id=to_text(r[5])))
    for r in _rows(sheets.get(C.SH_DAILY)):
        d, name = to_date(r[0]), _name(r[1])
        if not d or not name:
            continue
        ds.entries.append(DailyEntry(
            date=d, operator=name, status=norm(r[2]) or C.WORKED,
            ulanish=to_number(r[3]), gaplashish_min=to_duration_units(r[4]),
            sifat=to_number(r[5]), call_sec=to_duration_units(r[6]),
            lead=to_number(r[7]), sifatli=to_number(r[8]),
            sotuv=to_number(r[9]), summa=to_number(r[10])))
    for r in _rows(sheets.get(C.SH_ATTENDANCE)):
        d, name = to_date(r[0]), _name(r[1])
        if not d or not name:
            continue
        ds.attendance.append(Attendance(
            date=d, operator=name, status=norm(r[2]) or "keldi",
            late_min=to_number(r[3]), hours=to_number(r[4])))
    for r in _rows(sheets.get(C.SH_SALES)):
        d, name, amount = to_date(r[0]), _name(r[1]), to_number(r[2])
        if not d or not name or amount is None:
            continue
        ds.sales.append(Sale(date=d, operator=name, amount=amount, lead_type=norm(r[3])))
    for r in _rows(sheets.get(C.SH_DIRECTOR)):
        d, name, amount = to_date(r[0]), _name(r[1]), to_number(r[2])
        if not d or not name or amount is None:
            continue
        ds.director_bonuses.append(DirectorBonus(
            month=d.replace(day=1), operator=name, amount=amount, note=to_text(r[3])))
    from .plan import parse_plan
    ds.plans = parse_plan(sheets.get(C.SH_PLAN))
    apply_aliases(ds, {a: n for n, names in aliases.items() for a in names})
    return ds


def apply_aliases(ds: Dataset, alias_to_name: dict[str, str]) -> None:
    """Bir odamning turli yozilishini (Bekzod → Behzod) Operatorlar'dagi ismga keltiradi.

    Faqat aniq ko'rsatilgan yozilishlar almashtiriladi; o'xshash ismlar
    (masalan Ruxshona va Ruhshona — ikki xil odam) avtomatik birlashtirilmaydi.
    """
    if not alias_to_name:
        return
    by_norm = {norm(a): n for a, n in alias_to_name.items()}
    for items in (ds.entries, ds.attendance, ds.sales, ds.director_bonuses, ds.plans):
        for item in items:
            item.operator = by_norm.get(norm(item.operator), item.operator)
