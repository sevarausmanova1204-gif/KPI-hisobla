import csv
from datetime import date

from conftest import entry

from kpi.config import Settings
from kpi.models import Dataset
from kpi.plan import build_plan, parse_plan, plan_workdays, round_half_up, track
from kpi.report import plan_distribution, plan_progress_block

OCT = date(2026, 10, 1)


def _october():
    with open("rejalar/2026-10.csv", encoding="utf-8-sig") as fh:
        return parse_plan(list(csv.reader(fh)))


def test_october_plan_matches_given_table():
    rows = {r.operator: r for r in build_plan(_october(), Settings(), OCT)}
    m = rows["Muxsima"]
    assert (m.daily, m.weekly, m.clients_month, m.clients_week, m.clients_day) == \
        (9_615_385, 62_500_000, 625, 156.3, 24.0)
    a = rows["Aziza"]
    assert (a.daily, a.weekly, a.clients_month, a.clients_week) == (7_692_308, 50_000_000, 500, 125)
    r = rows["Ruhshona"]
    assert (r.daily, r.weekly, r.clients_month, r.clients_day, r.conversion) == \
        (5_000_000, 32_500_000, 325, 12.5, 25)
    d = rows["Dildora"]
    assert (d.weekly, d.clients_month, d.clients_week, d.clients_day) == (25_000_000, 250, 62.5, 9.6)
    assert m.leads_month == 1786  # 625 / 35%
    assert sum(x.amount for x in rows.values()) == 1_740_000_000


def test_october_workdays_with_holiday():
    assert len(plan_workdays(OCT, date(2026, 10, 31), set())) == 27
    assert len(plan_workdays(OCT, date(2026, 10, 31), {OCT})) == 26


def test_tracking_fact_and_need():
    ds = Dataset(plans=_october())
    ds.entries = [entry(date(2026, 10, d), "Aziza", sotuv=20, summa=8_000_000, sifatli=55)
                  for d in (2, 3, 5)]
    rows = track(build_plan(ds.plans, Settings(), OCT), ds, date(2026, 10, 5), {OCT})
    a = next(r for r in rows if r.operator == "Aziza")
    assert a.fact_amount == 24_000_000 and a.fact_clients == 60
    assert a.elapsed_days == 3 and a.remaining_days == 23
    assert a.expected_amount == 7_692_308 * 3
    assert round(a.pace) == 104
    assert round(a.need_per_day) == round((200_000_000 - 24_000_000) / 23)
    assert [w["days"] for w in a.weeks] == [2, 6, 6, 6, 6]
    text = plan_progress_block(rows)
    assert "Aziza" in text and "Reja bajarilishi" in text
    assert "Muxsima" in "\n".join(plan_distribution("Oktabr 2026", rows))


def test_round_half_up():
    assert round_half_up(62.5) == 63
    assert round_half_up(156.25, 1) == 156.3
