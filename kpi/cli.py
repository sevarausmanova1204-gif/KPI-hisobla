"""Buyruqlar: python -m kpi <buyruq> ...

  setup            Sheets tuzilmasini yaratish (varaqlar, validatsiya, formulalar)
  ogohlantirish    Kecha kiritilmagan ma'lumotlar haqida ogohlantirish (12:00)
  kunlik           Kunlik tahlil → Tahlil varag'i + Telegram
  haftalik         Haftalik hisobot (dushanba)
  oylik            Oylik maosh → Arxiv + Excel + Telegram (1-sana)
  tasdiqlash       Arxivdagi oy maoshini "tasdiqlangan" deb belgilash
  tekshir          Python hisobini Sheets formulalari bilan solishtirish
  shablon          Offlayn sinov uchun bo'sh .xlsx shablon
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta

from . import analysis as A
from . import report as R
from .calc import compute_salary, month_end, month_start
from .parsing import fmt_money


def _today() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(os.environ.get("KPI_TZ", "Asia/Tashkent"))).date()
    except Exception:
        return date.today()


def _parse_day(s: str | None) -> date:
    if not s:
        return _today() - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise SystemExit(f"Sana noto'g'ri: {s}")


def _parse_month(s: str | None) -> date:
    if not s:
        return month_start(_today().replace(day=1) - timedelta(days=1))
    return datetime.strptime(s, "%Y-%m").date()


def _load(args):
    if args.xlsx:
        from .local import load_xlsx
        return None, *load_xlsx(args.xlsx)
    from .sheets import SheetStore
    store = SheetStore()
    return store, *store.load()


def _send(args, messages: list[str], director: bool = False) -> None:
    if args.yuborma or not messages:
        for m in messages:
            print(m, "\n" + "-" * 40)
        return
    from .telegram import Telegram
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if director:
        chat = os.environ.get("TELEGRAM_DIRECTOR_CHAT_ID", "") or chat
    if not chat:
        raise SystemExit("TELEGRAM_CHAT_ID o'rnatilmagan")
    Telegram().send(chat, messages)


def cmd_setup(args) -> None:
    from .sheets import SheetStore
    for line in SheetStore().setup():
        print(line)


def cmd_warn(args) -> None:
    _, ds, _settings = _load(args)
    day = _parse_day(args.sana)
    missing = A.expected_entries(ds, day)
    if missing:
        _send(args, R.missing_report(day, missing))
    else:
        print(f"{day}: hamma ma'lumot kiritilgan")


def analysis_rows(day: date, analyses: list[A.OperatorAnalysis]) -> list[list[object]]:
    rows = []
    stamp = day.strftime("%d.%m.%Y")
    for oa in analyses:
        by_kpi = {a.kpi_key: a for a in oa.actions}
        for k in oa.kpis:
            a = by_kpi.get(k.key)
            rows.append([stamp, oa.operator, k.kpi.name, A.fmt_value(k.key, k.value), k.status,
                         k.level, A.fmt_value(k.key, k.next_threshold),
                         A.fmt_gap(k.key, k.gap) if k.gap is not None else "",
                         k.next_bonus_delta or "", k.need_text,
                         a.action if a else "", a.owner if a else "", a.deadline if a else ""])
        if None in by_kpi:
            a = by_kpi[None]
            rows.append([stamp, oa.operator, a.title, "", "yo'q", "", "", "", "", a.detail,
                         a.action, a.owner, a.deadline])
        rows.append([stamp, oa.operator, "JAMI (prognoz)",
                     fmt_money(oa.salary.total) if oa.salary else "",
                     "namuna" if oa.model else "", "", "", "",
                     oa.salary.kpi_total if oa.salary else "", "", "", "", ""])
    return rows


def cmd_daily(args) -> None:
    store, ds, settings = _load(args)
    day = _parse_day(args.sana)
    analyses = A.analyze(ds, settings, day)
    missing = A.expected_entries(ds, day)
    if store and not args.yuborma:
        store.write_analysis(day, analysis_rows(day, analyses))
    _send(args, R.daily_report(day, analyses, missing, A.sales_mismatches(ds, day)))


def cmd_weekly(args) -> None:
    store, ds, settings = _load(args)
    day = _parse_day(args.sana)
    # dushanba kuni ishga tushsa — o'tgan hafta
    start, end = A.week_bounds(day)
    past = store.past_actions() if store else []
    rows = A.weekly(ds, settings, end, past)
    _send(args, R.weekly_report(start, end, rows), director=False)
    if not args.yuborma and os.environ.get("TELEGRAM_DIRECTOR_CHAT_ID"):
        _send(args, R.weekly_report(start, end, rows), director=True)


def cmd_monthly(args) -> None:
    store, ds, settings = _load(args)
    month = _parse_month(args.oy)
    rows = compute_salary(ds, settings, month, month_end(month))
    if store and not args.yuborma:
        store.write_archive(month, rows)
    path = None
    if not args.eksportsiz:
        from .local import export_salary
        path = export_salary(args.fayl or f"maosh_{month.strftime('%Y_%m')}.xlsx", month, rows)
        print(f"Excel: {path}")
    _send(args, R.monthly_report(month, rows, settings.int("ISH_KUNLARI")), director=True)
    if path and not args.yuborma:
        from .telegram import Telegram
        chat = os.environ.get("TELEGRAM_DIRECTOR_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID", "")
        Telegram().send_file(chat, path, f"Maosh jadvali {month.strftime('%m.%Y')}")


def cmd_approve(args) -> None:
    from .sheets import SheetStore
    month = _parse_month(args.oy)
    n = SheetStore().approve_archive(month)
    print(f"{month.strftime('%Y-%m')}: {n} ta qator tasdiqlandi")


def cmd_check(args) -> int:
    """Hisob_oylik (formulalar) va Python hisobini so'mgacha solishtiradi."""
    from .formulas import MONTHLY_FIRST_ROW
    from .parsing import to_date, to_number
    from .sheets import SheetStore
    store = SheetStore()
    ds, settings = store.load()
    values = store.read_monthly_calc()
    month = to_date(values[0][1]) if values and len(values[0]) > 1 else None
    as_of = to_date(values[1][1]) if len(values) > 1 and len(values[1]) > 1 else None
    if not month:
        raise SystemExit("Hisob_oylik!B1 da oy topilmadi — avval `setup` bajaring")
    py = {r.operator: r for r in compute_salary(ds, settings, month, as_of)}
    bad = 0
    for row in values[MONTHLY_FIRST_ROW - 1:]:
        if not row or not row[0]:
            continue
        name = str(row[0])
        r = py.get(name)
        sheet_total = to_number(row[21]) if len(row) > 21 else None
        if r is None or sheet_total is None or abs(r.total - sheet_total) > 0.5:
            bad += 1
            print(f"✗ {name}: Sheets {fmt_money(sheet_total)} ≠ Python {fmt_money(r.total if r else None)}")
        else:
            print(f"✓ {name}: {fmt_money(r.total)}")
    return 1 if bad else 0


def cmd_template(args) -> None:
    from .local import write_template
    write_template(args.fayl)
    print(f"Shablon: {args.fayl}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kpi", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--xlsx", help="Sheets o'rniga .xlsx fayldan o'qish (sinov)")
        sp.add_argument("--yuborma", action="store_true",
                        help="Telegram'ga yubormasdan ekranga chiqarish, Sheets'ga yozmaslik")
        return sp

    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    sp = common(sub.add_parser("ogohlantirish"))
    sp.add_argument("--sana", help="YYYY-MM-DD (standart: kecha)")
    sp.set_defaults(fn=cmd_warn)
    sp = common(sub.add_parser("kunlik"))
    sp.add_argument("--sana", help="YYYY-MM-DD (standart: kecha)")
    sp.set_defaults(fn=cmd_daily)
    sp = common(sub.add_parser("haftalik"))
    sp.add_argument("--sana", help="hafta ichidagi istalgan kun (standart: kecha)")
    sp.set_defaults(fn=cmd_weekly)
    sp = common(sub.add_parser("oylik"))
    sp.add_argument("--oy", help="YYYY-MM (standart: o'tgan oy)")
    sp.add_argument("--fayl", help="Excel fayl nomi")
    sp.add_argument("--eksportsiz", action="store_true")
    sp.set_defaults(fn=cmd_monthly)
    sp = sub.add_parser("tasdiqlash")
    sp.add_argument("--oy", help="YYYY-MM")
    sp.set_defaults(fn=cmd_approve)
    sub.add_parser("tekshir").set_defaults(fn=cmd_check)
    sp = sub.add_parser("shablon")
    sp.add_argument("--fayl", default="kpi_shablon.xlsx")
    sp.set_defaults(fn=cmd_template)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
