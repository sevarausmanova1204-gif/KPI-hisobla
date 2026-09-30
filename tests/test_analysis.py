from datetime import date

from conftest import days, entry

from kpi import analysis as A
from kpi.models import Dataset, Operator
from kpi.report import daily_report, monthly_report, split_messages, weekly_report
from kpi.calc import compute_salary


def _op(name, n=10, **kw):
    base = dict(ulanish=160, sifat=80, call_sec=120, lead=20, sifatli=10, sotuv=3, summa=1_500_000)
    base.update(kw)
    return [entry(d, name, **base) for d in days(date(2026, 9, 1), n)]


def test_statuses(settings):
    t = settings.tiers("GAPL")
    assert A.status_of(109, t, 90) == A.YELLOW   # Muxsima: 109/110
    assert A.status_of(110, t, 90) == A.GREEN
    assert A.status_of(98, t, 90) == A.RED
    assert A.status_of(None, t, 90) == A.NODATA


def test_distance_text_matches_spec(settings):
    ds = Dataset(operators=[Operator("Javohir")], entries=_op("Javohir", sifat=67.9))
    (oa,) = A.analyze(ds, settings, date(2026, 9, 11))
    sifat = next(k for k in oa.kpis if k.key == "sifat")
    assert sifat.status == A.YELLOW  # 67,9 / 70 = 97%
    assert sifat.distance_text() == "sifat 67,9% → 70% ga 2,1 punkt kerak = +360 000 so'm"


def test_conversion_forecast_needs_sales_per_day(settings):
    # 10 kun: 100 sifatli lead, 20 sotuv = 20%. Qolgan kunlar: 12..30 sentabr = 16 ish kuni.
    ds = Dataset(operators=[Operator("A")], entries=_op("A", sotuv=2))
    (oa,) = A.analyze(ds, settings, date(2026, 9, 11))
    konv = next(k for k in oa.kpis if k.key == "konversiya")
    assert oa.remaining_days == 16
    # 25% × (100 + 10×16) = 65 → 45 ta qo'shimcha / 16 kun → kuniga 3 ta
    assert "har kuni 3 ta sotuv kerak" in konv.need_text
    assert konv.reachable


def test_max_two_actions_closest_first(settings):
    ds = Dataset(operators=[Operator("A")],
                 entries=_op("A", ulanish=100, sifat=65, call_sec=105, sotuv=2, summa=800_000))
    (oa,) = A.analyze(ds, settings, date(2026, 9, 11))
    assert len(oa.actions) == 2
    # eng katta pul ta'siri: konversiya (900k) va ulanish (600k) → yaqinroq birinchi
    assert {a.kpi_key for a in oa.actions} == {"konversiya", "ulanish"}
    gaps = {k.key: k.gap / k.next_threshold for k in oa.kpis}
    first, second = oa.actions
    assert gaps[first.kpi_key] <= gaps[second.kpi_key]


def test_model_operator_and_missing_data(settings):
    ds = Dataset(operators=[Operator("Top"), Operator("Lost")],
                 entries=_op("Top", n=8) + _op("Lost", n=6))
    # 1–9 sentabr ish kunlari: Top 8 kun (1..9 sentabr, 6-yakshanba), Lost 6 kun
    res = {oa.operator: oa for oa in A.analyze(ds, settings, date(2026, 9, 9))}
    assert res["Top"].model and not res["Top"].actions
    assert res["Lost"].missing_days == 2
    assert res["Lost"].actions[0].kpi_key is None
    assert A.expected_entries(ds, date(2026, 9, 9)) == ["Lost"]
    assert A.expected_entries(ds, date(2026, 9, 6)) == []  # yakshanba


def test_reports_render(aziza, settings):
    day = date(2026, 9, 5)
    msgs = daily_report(day, A.analyze(aziza, settings, day), ["Zuhra"], [])
    text = "\n".join(msgs)
    assert "Aziza" in text and "Zuhra" in text and "05.09.2026" in text
    rows = A.weekly(aziza, settings, date(2026, 9, 6), [(date(2026, 9, 1), "Aziza", "ulanish")])
    assert "Aziza" in "\n".join(weekly_report(date(2026, 8, 31), date(2026, 9, 6), rows))
    month_text = "\n".join(monthly_report(date(2026, 9, 1), compute_salary(aziza, settings, date(2026, 9, 1))))
    assert "4 820 000" in month_text


def test_split_messages():
    parts = split_messages(["a" * 3000, "b" * 3000, "c" * 10], limit=4000)
    assert len(parts) == 2 and all(len(p) <= 4000 for p in parts)
