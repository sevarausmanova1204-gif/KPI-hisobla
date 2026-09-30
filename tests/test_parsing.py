from datetime import date, time

from kpi.parsing import fmt_mmss, fmt_money, to_date, to_duration_units, to_number


def test_numbers():
    assert to_number("1 720 000") == 1_720_000
    assert to_number("76,64") == 76.64
    assert to_number("75,1%") == 75.1
    assert to_number("1,720,000") == 1_720_000
    assert to_number(155) == 155
    assert to_number("") is None
    assert to_number(None) is None
    assert to_number("abc") is None


def test_durations():
    assert to_duration_units("1:43") == 103          # daq:son → sek
    assert to_duration_units("3:25") == 205          # soat:daqiqa → daq
    assert round(to_duration_units(103 / 1440), 6) == 103  # Sheets 01:43 vaqti
    assert to_duration_units(time(1, 51)) == 111
    assert to_duration_units("3 soat 5 minut") == 185
    assert to_duration_units("1 daqiqa 43 sekund") == 103
    assert to_duration_units("") is None


def test_dates_and_format():
    assert to_date("17.09.2026") == date(2026, 9, 17)
    assert to_date(46282) == date(2026, 9, 17)  # Sheets seriya raqami
    assert to_date("2026-09-17") == date(2026, 9, 17)
    assert fmt_mmss(111) == "1:51"
    assert fmt_money(4_820_000) == "4 820 000"
