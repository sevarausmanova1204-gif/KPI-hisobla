"""Dashboard: tahlil natijalarini bitta mustaqil HTML faylga yig'adi.

Hisob-kitob `calc.py` / `analysis.py` da qoladi; HTML faqat tayyor
raqamlarni ko'rsatadi.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import analysis as A
from . import config as C
from .calc import compute_salary, compute_stats, month_start, workdays
from .models import Dataset

TEMPLATE = Path(__file__).with_name("templates") / "dashboard.html"
MONTHS = _MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust",
           "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def _num(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def build_data(ds: Dataset, settings: C.Settings, as_of: date, sample: bool = False) -> dict:
    m0 = month_start(as_of)
    analyses = A.analyze(ds, settings, as_of)
    salary = compute_salary(ds, settings, as_of, as_of)
    dates = [m0 + timedelta(i) for i in range((as_of - m0).days + 1)]

    kpis = [{"key": k.key, "name": k.name, "unit": k.unit,
             "tiers": [[t, b] for t, b in settings.tiers(k.prefix)],
             "action": k.action} for k in C.KPIS]

    operators = []
    for oa in analyses:
        series = {k.key: [] for k in C.KPIS}
        for d in dates:
            st = compute_stats(ds.entries, oa.operator, m0, d)
            for k in C.KPIS:
                series[k.key].append(_num(st.value(k.key)))
        operators.append({
            "name": oa.operator,
            "model": oa.model,
            "missing": oa.missing_days,
            "kpis": [{
                "key": k.key, "value": _num(k.value), "display": A.fmt_value(k.key, k.value),
                "status": k.status, "level": k.level, "bonus": k.bonus,
                "next": k.next_threshold, "nextDisplay": A.fmt_value(k.key, k.next_threshold),
                "gap": A.fmt_gap(k.key, k.gap) if k.gap is not None else "",
                "delta": k.next_bonus_delta, "need": k.need_text, "reachable": k.reachable,
            } for k in oa.kpis],
            "actions": [{"kpi": a.kpi_key, "title": a.title, "detail": a.detail,
                         "action": a.action, "owner": a.owner, "deadline": a.deadline}
                        for a in oa.actions],
            "series": series,
        })

    return {
        "meta": {
            "month": m0.strftime("%Y-%m"),
            "monthLabel": f"{_MONTHS[m0.month - 1]} {m0.year}",
            "asOf": as_of.strftime("%d.%m.%Y"),
            "remaining": workdays(as_of + timedelta(days=1), A.month_end(as_of)),
            "workdays": settings.int("ISH_KUNLARI"),
            "sample": sample,
            "missing": A.expected_entries(ds, as_of),
        },
        "dates": [d.strftime("%d.%m") for d in dates],
        "kpis": kpis,
        "operators": operators,
        "salary": [{
            "name": r.operator, "kind": r.kind, "days": r.worked_workdays,
            "prorated": r.prorated, "fixa": r.fixa, "bonuses": r.bonuses,
            "values": {k: _num(v) for k, v in r.values.items()},
            "kpiTotal": r.kpi_total, "attendance": r.attendance_bonus,
            "director": r.director_bonus, "total": r.total, "scenario": r.scenario_total,
        } for r in salary],
    }


def render(data: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return html.replace("/*__DATA__*/null", payload)


def write_dashboard(path: str, ds: Dataset, settings: C.Settings, as_of: date,
                    sample: bool = False) -> str:
    Path(path).write_text(render(build_data(ds, settings, as_of, sample)), encoding="utf-8")
    return path


PLAN_TEMPLATE = Path(__file__).with_name("templates") / "reja.html"


def build_plan_data(rows: list, month: date, as_of: date, settings: C.Settings) -> dict:
    from .plan import plan_days
    started = as_of >= month
    ops = []
    for r in sorted(rows, key=lambda r: -r.amount):
        ops.append({
            "name": r.operator, "note": r.note, "amount": r.amount, "conversion": r.conversion,
            "check": r.avg_check, "daily": r.daily, "weekly": r.weekly,
            "clientsMonth": r.clients_month, "clientsWeek": r.clients_week, "clientsDay": r.clients_day,
            "leadsMonth": r.leads_month, "leadsDay": r.leads_day,
            "fact": r.fact_amount if started else None, "factClients": r.fact_clients if started else None,
            "expected": r.expected_amount, "pace": r.pace, "completion": r.completion,
            "needDay": r.need_per_day, "needClientsDay": r.need_clients_per_day,
            "factConversion": r.fact_conversion,
            "weeks": [{**w, "from": w["from"].strftime("%d.%m"), "to": w["to"].strftime("%d.%m")}
                      for w in r.weeks],
        })
    first = rows[0] if rows else None
    return {
        "meta": {
            "month": month.strftime("%Y-%m"),
            "monthLabel": f"{MONTHS[month.month - 1]} {month.year}",
            "asOf": as_of.strftime("%d.%m.%Y") if started else None,
            "started": started,
            "planDays": plan_days(month, settings),
            "check": first.avg_check if first else settings.get("REJA_CHEK"),
            "baseOld": settings.get("REJA_BAZA_ESKI"),
            "baseLead": settings.get("REJA_BAZA_LEAD"),
        },
        "operators": ops,
    }


def write_plan_page(path: str, rows: list, month: date, as_of: date, settings: C.Settings) -> str:
    html = PLAN_TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(build_plan_data(rows, month, as_of, settings), ensure_ascii=False,
                         default=str).replace("</", "<\\/")
    Path(path).write_text(html.replace("/*__DATA__*/null", payload), encoding="utf-8")
    return path
