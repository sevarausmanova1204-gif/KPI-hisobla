import csv
from datetime import date

from conftest import entry

from kpi.config import Settings
from kpi.models import Dataset, Operator, apply_aliases, parse_dataset
from kpi.plan import build_plan, parse_plan, round_half_up, track
from kpi.report import plan_distribution, plan_progress_block

OCT = date(2026, 10, 1)


def _october():
    with open("rejalar/2026-10.csv", encoding="utf-8-sig") as fh:
        return parse_plan(list(csv.reader(fh)))


def test_october_plan_uses_31_days_and_week_of_7():
    rows = {r.operator: r for r in build_plan(_october(), Settings(), OCT)}
    m = rows["Muxsima"]
    assert m.daily == round_half_up(250_000_000 / 31) == 8_064_516
    assert m.weekly == round_half_up(250_000_000 / 31 * 7) == 56_451_613
    assert (m.clients_month, m.clients_day, m.clients_week) == (625, 20.2, 141.1)
    assert m.leads_month == 1786  # 625 / 35%
    d = rows["Dildora"]
    assert (d.clients_month, d.clients_day) == (250, 8.1)
    assert rows["Shohida"].amount == rows["E'zoza"].amount == 130_000_000
    assert len(rows) == 11
    assert sum(x.amount for x in rows.values()) == 1_870_000_000


def test_fixed_days_setting():
    (r, *_) = build_plan(_october(), Settings({"REJA_KUNLAR": 26}), OCT)
    assert r.daily == round_half_up(r.amount / 26)


def test_tracking_fact_and_need():
    ds = Dataset(plans=_october())
    ds.entries = [entry(date(2026, 10, d), "Aziza", sotuv=20, summa=8_000_000, sifatli=55)
                  for d in (1, 2, 3)]
    rows = track(build_plan(ds.plans, Settings(), OCT), ds, date(2026, 10, 3))
    a = next(r for r in rows if r.operator == "Aziza")
    assert a.fact_amount == 24_000_000 and a.fact_clients == 60
    assert a.elapsed_days == 3 and a.remaining_days == 28
    assert a.expected_amount == a.daily * 3
    assert round(a.pace) == 124
    assert [w["days"] for w in a.weeks] == [4, 7, 7, 7, 6]
    assert "Aziza" in plan_progress_block(rows)
    text = "\n".join(plan_distribution("Oktabr 2026", rows))
    assert "31 kun" in text and "kunlik × 7" in text


def test_aliases_join_spellings_but_not_similar_names():
    ds = parse_dataset({
        "Operatorlar": [["Ism"], ["Behzod", None, None, "faol", "operator", "", "Bekzod"],
                        ["Ruxshona"], ["Ruhshona"]],
        "Reja": [["Oy"], ["01.10.2026", "Bekzod", 200_000_000, 35],
                 ["01.10.2026", "Ruhshona", 130_000_000, 25]],
        "Kunlik_kiritish": [["Sana"], ["01.10.2026", "bekzod", "ishladi", 100]],
    })
    assert ds.plans[0].operator == "Behzod"
    assert ds.entries[0].operator == "Behzod"
    assert ds.plans[1].operator == "Ruhshona"   # Ruxshona bilan birlashtirilmaydi
    apply_aliases(ds, {})
    assert isinstance(ds.operators[0], Operator)


def test_round_half_up():
    assert round_half_up(62.5) == 63
    assert round_half_up(156.25, 1) == 156.3
