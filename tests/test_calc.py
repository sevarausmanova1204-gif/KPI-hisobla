from datetime import date

from conftest import days, entry

from kpi.calc import compute_salary, compute_stats, tier, workdays
from kpi.config import Settings
from kpi.models import Attendance, Dataset, DirectorBonus, Operator

SEP = date(2026, 9, 1)


def test_september_has_26_workdays():
    assert workdays(date(2026, 9, 1), date(2026, 9, 30)) == 26


def test_tiers_take_highest_matching(settings):
    t = settings.tiers("KONV")
    assert tier(24.99, t) == (0, 0)
    assert tier(25, t) == (1, 900_000)
    assert tier(30, t) == (2, 1_440_000)
    assert tier(3 / 10 * 100, t) == (2, 1_440_000)  # suzuvchi nuqta xatosi
    assert tier(40, t) == (3, 1_800_000)
    assert tier(None, t) == (0, 0)


def test_aziza_september_salary(aziza, settings):
    """Qabul mezoni: Aziza 4 820 000 (Fixa 2 mln, davomatsiz)."""
    (row,) = compute_salary(aziza, settings, SEP)
    assert round(row.values["konversiya"], 6) == 34
    assert round(row.values["chek"]) == 573_760
    assert round(row.values["sifat"], 6) == 75.1
    assert row.values["gaplashish"] == 111
    assert row.values["ulanish"] == 118
    assert row.bonuses == {"konversiya": 1_440_000, "ulanish": 0, "chek": 720_000,
                           "sifat": 360_000, "gaplashish": 300_000}
    assert row.fixa == 2_000_000
    assert row.kpi_total == 2_820_000
    assert row.attendance_bonus == 0
    assert row.total == 4_820_000
    assert row.scenario_total == 5_820_000  # Fixa 3 mln bo'lsa


def test_rest_days_and_blanks_do_not_affect_averages():
    ds = Dataset(operators=[Operator("A")])
    ds.entries = [entry(date(2026, 9, 1), "A", ulanish=100, sifat=80),
                  entry(date(2026, 9, 2), "A", ulanish=200, sifat=None),
                  entry(date(2026, 9, 3), "A", status="dam"),
                  entry(date(2026, 9, 4), "A", status="kasal", ulanish=0)]
    st = compute_stats(ds.entries, "A", date(2026, 9, 1), date(2026, 9, 30))
    assert st.ulanish == 150
    assert st.sifat == 80
    assert st.worked_days == 2


def test_new_employees_prorated_fixa(settings):
    """Qabul mezoni: Mashhura 1 615 385 (21 kun), Behzod 1 923 077 (25 kun)."""
    ds = Dataset(operators=[
        Operator("Mashhura", hire_date=date(2026, 9, 7), kind="yangi"),
        Operator("Behzod", hire_date=date(2026, 9, 2), kind="yangi"),
    ])
    ds.entries.append(entry(date(2026, 9, 8), "Mashhura", ulanish=300, sifat=99,
                            sifatli=10, sotuv=9, summa=9_000_000, call_sec=200))
    rows = {r.operator: r for r in compute_salary(ds, settings, SEP)}
    assert rows["Mashhura"].worked_workdays == 21
    assert rows["Mashhura"].fixa == 1_615_385
    assert rows["Mashhura"].kpi_total == 0          # yangi xodim — faqat Fixa
    assert rows["Mashhura"].total == 1_615_385
    assert rows["Behzod"].worked_workdays == 25
    assert rows["Behzod"].total == 1_923_077


def test_missed_days_are_subtracted_and_attendance_sheet_wins(settings):
    ds = Dataset(operators=[Operator("B", hire_date=date(2026, 9, 2), kind="yangi")])
    ds.entries.append(entry(date(2026, 9, 3), "B", status="kelmadi"))
    (row,) = compute_salary(ds, settings, SEP)
    assert row.worked_workdays == 24
    # Davomat bo'lsa, ishlagan kunlar undan olinadi
    ds.attendance = [Attendance(d, "B", "keldi", 0, 8) for d in days(date(2026, 9, 2), 20)]
    (row,) = compute_salary(ds, settings, SEP)
    assert row.worked_workdays == 20
    assert row.fixa == round(2_000_000 / 26 * 20)


def test_full_month_operator_not_prorated_unless_setting(settings):
    ds = Dataset(operators=[Operator("R")])
    ds.entries = [entry(d, "R") for d in days(SEP, 13)]
    ds.entries.append(entry(date(2026, 9, 20 + 1), "R", status="kelmadi"))
    (row,) = compute_salary(ds, settings, SEP)
    assert row.fixa == 2_000_000
    (row,) = compute_salary(ds, Settings({"FIXA_PROPORSIONAL": 1}), SEP)
    assert row.prorated and row.fixa == round(2_000_000 / 26 * 25)


def test_attendance_bonus(settings):
    def make(late_days, hours_per_day):
        ds = Dataset(operators=[Operator("D")])
        ds.attendance = [Attendance(d, "D", "keldi", 5 if i < late_days else 0, hours_per_day)
                         for i, d in enumerate(days(SEP, 26))]
        return compute_salary(ds, settings, SEP)[0].attendance_bonus
    assert make(0, 9.5) == 900_000
    assert make(2, 9.5) == 720_000
    assert make(3, 9.5) == 0
    assert make(0, 9) == 0  # 234 soat < 240


def test_director_bonus_and_settings_change(aziza):
    aziza.director_bonuses.append(DirectorBonus(SEP, "Aziza", 500_000))
    (row,) = compute_salary(aziza, Settings({"FIXA": 3_000_000, "ULAN_1_CHEG": 100}), SEP)
    assert row.director_bonus == 500_000
    assert row.bonuses["ulanish"] == 600_000
    assert row.total == 3_000_000 + 2_820_000 + 600_000 + 500_000


def test_left_operator_included_only_with_data(settings):
    ds = Dataset(operators=[Operator("X", status="ketgan"), Operator("Y", status="ketgan")])
    ds.entries.append(entry(date(2026, 9, 1), "X", ulanish=100))
    names = [r.operator for r in compute_salary(ds, settings, SEP)]
    assert names == ["X"]
