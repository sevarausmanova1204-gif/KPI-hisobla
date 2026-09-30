"""Telegram uchun HTML hisobotlar (TZ 7-bo'lim)."""
from __future__ import annotations

from datetime import date
from html import escape as _escape

from . import config as C
from .analysis import EMOJI, OperatorAnalysis, WeeklyRow, fmt_value
from .calc import SalaryRow
from .parsing import fmt_money

TG_LIMIT = 4000


def escape(text: str) -> str:
    return _escape(text, quote=False)

_KPI_SHORT = {"konversiya": "Konv", "ulanish": "Qo'ng'", "chek": "Chek",
              "sifat": "Sifat", "gaplashish": "Gapl"}


def split_messages(blocks: list[str], limit: int = TG_LIMIT) -> list[str]:
    """Bloklarni Telegram chegarasidan oshmaydigan xabarlarga bo'ladi."""
    out, cur = [], ""
    for block in blocks:
        if cur and len(cur) + len(block) + 2 > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n\n{block}" if cur else block
        while len(cur) > limit:
            out.append(cur[:limit])
            cur = cur[limit:]
    if cur:
        out.append(cur)
    return out


def _d(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def daily_report(day: date, analyses: list[OperatorAnalysis], missing: list[str],
                 mismatches: list[str] | None = None) -> list[str]:
    blocks = [f"<b>📊 Kunlik KPI hisobot — {_d(day)}</b>\n"
              f"Oy boshidan o'rtachalar. Oy oxirigacha {analyses[0].remaining_days if analyses else 0} ish kuni qoldi."]
    if missing:
        blocks.append("⚠️ <b>Kiritilmagan:</b> " + escape(", ".join(missing)))
    for oa in analyses:
        lines = [f"<b>{escape(oa.operator)}</b>" + (" ⭐ namuna" if oa.model else "")]
        lines.append(" | ".join(f"{EMOJI[k.status]} {_KPI_SHORT[k.key]} {fmt_value(k.key, k.value)}"
                                for k in oa.kpis))
        if oa.salary:
            lines.append(f"Prognoz: KPI {fmt_money(oa.salary.kpi_total)}, "
                         f"jami ≈ {fmt_money(oa.salary.total)} so'm")
        for i, a in enumerate(oa.actions, 1):
            lines.append(f"{i}) <b>{escape(a.title)}</b>: {escape(a.detail)}\n"
                         f"   ➜ {escape(a.action)} ({escape(a.owner)}, {escape(a.deadline)})")
        blocks.append("\n".join(lines))
    models = [oa.operator for oa in analyses if oa.model]
    if models:
        blocks.append("⭐ <b>Namuna:</b> " + escape(", ".join(models))
                      + " — yozuvlarini jamoaga ulashing.")
    if mismatches:
        blocks.append("🔎 <b>Sotuvlar mos emas:</b>\n" + escape("\n".join(mismatches)))
    return split_messages(blocks)


def missing_report(day: date, missing: list[str]) -> list[str]:
    if not missing:
        return []
    return [f"⚠️ <b>{_d(day)} ma'lumoti kiritilmagan</b> (muddat 12:00):\n"
            + escape(", ".join(missing))]


def _delta(key: str, prev: float | None, cur: float | None) -> str:
    if prev is None or cur is None:
        return fmt_value(key, cur)
    arrow = "↑" if cur > prev + 1e-9 else ("↓" if cur < prev - 1e-9 else "→")
    return f"{fmt_value(key, cur)} {arrow}"


def weekly_report(week_start: date, week_end: date, rows: list[WeeklyRow]) -> list[str]:
    blocks = [f"<b>📅 Haftalik hisobot — {_d(week_start)}–{_d(week_end)}</b>\n"
              "O'tgan haftaga nisbatan: ↑ o'sdi, ↓ pasaydi."]
    for r in rows:
        line = [f"<b>{escape(r.operator)}</b>",
                " | ".join(f"{_KPI_SHORT[k.key]} {_delta(k.key, r.prev_week.value(k.key), r.this_week.value(k.key))}"
                           for k in C.KPIS)]
        for key, before, after in r.action_results:
            ok = before is not None and after is not None and after > before
            line.append(f"Chora ({C.KPI_BY_KEY[key].name}): "
                        f"{fmt_value(key, before)} → {fmt_value(key, after)} "
                        + ("✅ natija berdi" if ok else "❌ natija bermadi"))
        blocks.append("\n".join(line))
    ranked = sorted(rows, key=lambda r: r.kpi_total, reverse=True)
    if ranked:
        blocks.append(f"🏆 Eng yaxshi: <b>{escape(ranked[0].operator)}</b> "
                      f"(KPI {fmt_money(ranked[0].kpi_total)})\n"
                      f"🐢 Eng orqada: <b>{escape(ranked[-1].operator)}</b> "
                      f"(KPI {fmt_money(ranked[-1].kpi_total)})")
    return split_messages(blocks)


def monthly_report(month: date, rows: list[SalaryRow], ish_kunlari: int = 26) -> list[str]:
    blocks = [f"<b>💰 Oylik maosh — {month.strftime('%m.%Y')}</b>"]
    total = 0.0
    for r in rows:
        total += r.total
        parts = [f"<b>{escape(r.operator)}</b> ({r.kind})",
                 f"Fixa: {fmt_money(r.fixa)}" + (f" ({r.worked_workdays}/{ish_kunlari} kun)" if r.prorated else "")]
        if r.kind == "operator":
            parts.append(" | ".join(f"{_KPI_SHORT[k.key]} {fmt_value(k.key, r.values[k.key])}"
                                    f" → {fmt_money(r.bonuses[k.key])}" for k in C.KPIS))
            parts.append(f"KPI jami: {fmt_money(r.kpi_total)}; davomat: {fmt_money(r.attendance_bonus)}; "
                         f"direktor: {fmt_money(r.director_bonus)}")
        parts.append(f"<b>Jami: {fmt_money(r.total)} so'm</b>")
        blocks.append("\n".join(parts))
    blocks.append(f"<b>Umumiy fond: {fmt_money(total)} so'm</b>\n"
                  "Maosh jadvali direktor tasdig'idan keyin yakuniy hisoblanadi.")
    return split_messages(blocks)


# ---- Reja -----------------------------------------------------------------

def _mln(x: float) -> str:
    v = x / 1_000_000
    return (f"{v:.1f}".rstrip("0").rstrip(".") if v < 100 else f"{v:.0f}").replace(".", ",") + " mln"


def _cl(x: float) -> str:
    return (f"{x:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def plan_distribution(month_label: str, rows: list) -> list[str]:
    """Oy boshida: har operatorga vazifa (kunlik / haftalik / oylik reja)."""
    total = sum(r.amount for r in rows)
    clients = sum(r.clients_month for r in rows)
    blocks = [f"<b>🎯 {escape(month_label)} rejasi — vazifalar taqsimoti</b>\n"
              f"Jami: <b>{fmt_money(total)} so'm</b> · {fmt_money(clients)} mijoz · "
              f"{len(rows)} operator\n"
              f"Kunlik = oylik ÷ 26, haftalik = oylik ÷ 4, mijoz = summa ÷ {fmt_money(rows[0].avg_check if rows else 400000)}"]
    for i, r in enumerate(sorted(rows, key=lambda r: -r.amount), 1):
        note = f" ({escape(r.note)})" if r.note else ""
        blocks.append(
            f"<b>{i}. {escape(r.operator)}</b>{note}\n"
            f"Oy: {fmt_money(r.amount)} so'm · {_cl(r.clients_month)} mijoz\n"
            f"Hafta: {fmt_money(r.weekly)} so'm · {_cl(r.clients_week)} mijoz\n"
            f"Kun: {fmt_money(r.daily)} so'm · {_cl(r.clients_day)} mijoz\n"
            f"Konversiya maqsadi: {_cl(r.conversion)}% → kuniga ≈{_cl(r.leads_day)} sifatli lead kerak")
    return split_messages(blocks)


def plan_progress_block(rows: list) -> str:
    """Kunlik hisobotga qo'shiladigan "reja bajarilishi" bloki."""
    if not rows:
        return ""
    total = sum(r.amount for r in rows)
    fact = sum(r.fact_amount for r in rows)
    expected = sum(r.expected_amount for r in rows)
    lines = [f"<b>🎯 Reja bajarilishi</b>: {_mln(fact)} / {_mln(total)} "
             f"({fact / total * 100:.0f}%) · shu kungacha kerak {_mln(expected)}"]
    for r in sorted(rows, key=lambda r: (r.pace or 0)):
        pace = r.pace
        mark = "🟢" if pace is not None and pace >= 100 else ("🟡" if pace is not None and pace >= 90 else "🔴")
        lines.append(f"{mark} {escape(r.operator)}: {_mln(r.fact_amount)} / {_mln(r.amount)} "
                     f"({r.completion:.0f}%), sur'at {pace or 0:.0f}% · "
                     f"kuniga {_mln(r.need_per_day)} / {_cl(round(r.need_clients_per_day, 1))} mijoz kerak")
    return "\n".join(lines)
