"""Google Sheets bilan ishlash (gspread)."""
from __future__ import annotations

import json
import os
from datetime import date

from . import config as C
from . import formulas as F
from .calc import SalaryRow
from .models import HEADERS, Dataset, parse_dataset, parse_settings

DATA_SHEETS = [C.SH_SETTINGS, C.SH_OPERATORS, C.SH_DAILY, C.SH_SALES,
               C.SH_ATTENDANCE, C.SH_DIRECTOR, C.SH_PLAN, C.SH_HOLIDAYS]

ANALYSIS_HEADERS = ["Sana", "Operator", "Ko'rsatkich", "Qiymat", "Holat", "Bosqich",
                    "Keyingi chegara", "Chegaragacha", "Ta'sir (so'm)", "Oy oxirigacha kerak",
                    "Chora", "Mas'ul", "Muddat"]
ARCHIVE_HEADERS = ["Oy", "Holat"] + F.MONTHLY_HEADERS


def _client():
    import gspread
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return gspread.service_account_from_dict(json.loads(raw))
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    return gspread.service_account(filename=path)


def _col(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _grid(sheet_id: int, col0: int, col1: int, row0: int = 1, row1: int | None = None) -> dict:
    g = {"sheetId": sheet_id, "startRowIndex": row0, "startColumnIndex": col0,
         "endColumnIndex": col1}
    if row1 is not None:
        g["endRowIndex"] = row1
    return g


class SheetStore:
    def __init__(self, sheet_id: str | None = None):
        self.sheet_id = sheet_id or os.environ.get("GOOGLE_SHEET_ID", "")
        if not self.sheet_id:
            raise RuntimeError("GOOGLE_SHEET_ID o'rnatilmagan")
        self.gc = _client()
        self.sh = self.gc.open_by_key(self.sheet_id)

    # ---- o'qish ----------------------------------------------------------
    def _values(self, title: str) -> list[list[object]]:
        try:
            ws = self.sh.worksheet(title)
        except Exception:
            return []
        return ws.get_values(value_render_option="UNFORMATTED_VALUE")

    def load(self) -> tuple[Dataset, C.Settings]:
        titles = DATA_SHEETS
        ranges = [f"{t}!A1:Z" for t in titles]
        resp = self.sh.values_batch_get(ranges, params={"valueRenderOption": "UNFORMATTED_VALUE"})
        data = {t: vr.get("values", []) for t, vr in zip(titles, resp.get("valueRanges", []))}
        return parse_dataset(data), parse_settings(data.get(C.SH_SETTINGS))

    def read_monthly_calc(self) -> list[list[object]]:
        return self._values(C.SH_CALC_MONTHLY)

    def past_actions(self) -> list[tuple[date, str, str]]:
        from .parsing import to_date
        key_by_name = {k.name: k.key for k in C.KPIS}
        out = []
        for row in self._values(C.SH_ANALYSIS)[1:]:
            row = list(row) + [""] * 13
            d = to_date(row[0])
            if d and row[10] and row[2] in key_by_name:
                out.append((d, str(row[1]), key_by_name[row[2]]))
        return out

    # ---- yozish ----------------------------------------------------------
    def _ws(self, title: str, rows: int = 1000, cols: int = 26):
        try:
            return self.sh.worksheet(title), False
        except Exception:
            return self.sh.add_worksheet(title=title, rows=rows, cols=cols), True

    def write_analysis(self, day: date, rows: list[list[object]]) -> None:
        ws, _ = self._ws(C.SH_ANALYSIS)
        existing = ws.get_values(value_render_option="FORMATTED_VALUE")
        stamp = day.strftime("%d.%m.%Y")
        keep = [r for r in existing[1:] if r and r[0] != stamp]
        body = [ANALYSIS_HEADERS] + keep + rows
        ws.clear()
        ws.update(range_name="A1", values=body, value_input_option="USER_ENTERED")

    def write_archive(self, month: date, salary: list[SalaryRow], status: str = "qoralama") -> None:
        ws, _ = self._ws(C.SH_ARCHIVE)
        existing = ws.get_values(value_render_option="FORMATTED_VALUE")
        tag = month.strftime("%Y-%m")
        if any(r and r[0] == tag and len(r) > 1 and r[1] == "tasdiqlangan" for r in existing[1:]):
            raise RuntimeError(f"{tag} oyi tasdiqlangan — qayta yozilmaydi")
        keep = [r for r in existing[1:] if r and r[0] != tag]
        body = [ARCHIVE_HEADERS] + keep + [[tag, status] + salary_cells(r) for r in salary]
        ws.clear()
        ws.update(range_name="A1", values=body, value_input_option="USER_ENTERED")
        self._protect(ws, f"Arxiv {tag}", warning_only=False)

    def approve_archive(self, month: date) -> int:
        ws, _ = self._ws(C.SH_ARCHIVE)
        tag = month.strftime("%Y-%m")
        values = ws.get_values(value_render_option="FORMATTED_VALUE")
        cells = [f"B{i}" for i, r in enumerate(values, start=1) if i > 1 and r and r[0] == tag]
        if cells:
            ws.batch_update([{"range": c, "values": [["tasdiqlangan"]]} for c in cells])
        return len(cells)

    def _protect(self, ws, description: str, warning_only: bool) -> None:
        meta = self.sh.fetch_sheet_metadata(params={"fields": "sheets(properties,protectedRanges)"})
        for s in meta["sheets"]:
            if s["properties"]["sheetId"] == ws.id and s.get("protectedRanges"):
                return
        prot = {"range": {"sheetId": ws.id}, "description": description,
                "warningOnly": warning_only}
        if not warning_only:
            auth = getattr(self.gc, "auth", None) or getattr(getattr(self.gc, "http_client", None), "auth", None)
            email = getattr(auth, "service_account_email", None)
            if email:
                prot["editors"] = {"users": [email]}
        self.sh.batch_update({"requests": [{"addProtectedRange": {"protectedRange": prot}}]})

    def replace_plan(self, month: date, rows: list[list[object]]) -> None:
        """Reja varag'ida shu oy qatorlarini yangilari bilan almashtiradi (A:F)."""
        from .parsing import to_date
        ws, _ = self._ws(C.SH_PLAN)
        existing = ws.get_values("A1:F", value_render_option="FORMATTED_VALUE")
        keep = []
        for r in existing[1:]:
            d = to_date(r[0]) if r else None
            if r and any(r) and not (d and d.replace(day=1) == month):
                keep.append((list(r) + [""] * 6)[:6])
        body = keep + rows
        ws.batch_clear(["A2:F"])
        if body:
            ws.update(range_name="A2", values=body, value_input_option="USER_ENTERED")

    # ---- tuzilma (1-bosqich) ---------------------------------------------
    def setup(self) -> list[str]:
        """Varaqlar, sarlavhalar, Sozlamalar, validatsiya va formulalarni yaratadi.

        Takroriy ishga tushirish xavfsiz: mavjud ma'lumot o'chirilmaydi,
        faqat Hisob_* varaqlari formulalari qayta yoziladi.
        """
        log = []
        sheets = {}
        for title in DATA_SHEETS + [C.SH_CALC_DAILY, C.SH_CALC_MONTHLY, C.SH_ANALYSIS, C.SH_ARCHIVE]:
            ws, created = self._ws(title, cols=30)
            sheets[title] = ws
            if created:
                log.append(f"+ varaq: {title}")
        for title, headers in HEADERS.items():
            sheets[title].update(range_name="A1", values=[headers])
        # Reja: hisoblangan ustunlar sarlavhasi va formulalari (G2:Q2)
        plan_ws = sheets[C.SH_PLAN]
        plan_ws.update(range_name=f"{F.PLAN_FIRST_CALC_COL}1",
                       values=[F.PLAN_CALC_HEADERS, F.plan_formulas()],
                       value_input_option="USER_ENTERED")
        hol = sheets[C.SH_HOLIDAYS]
        if len(hol.get_values("A1:A3")) <= 1:
            hol.update(range_name="A2", values=[list(h) for h in C.DEFAULT_HOLIDAYS],
                       value_input_option="USER_ENTERED")
            log.append("+ Bayramlar: standart sanalar (hayitlarni qo'shing)")
        sheets[C.SH_ANALYSIS].update(range_name="A1", values=[ANALYSIS_HEADERS])
        sheets[C.SH_ARCHIVE].update(range_name="A1", values=[ARCHIVE_HEADERS])

        # Sozlamalar: yetishmagan kalitlarni qo'shamiz, mavjud qiymatlarga tegmaymiz
        ws = sheets[C.SH_SETTINGS]
        current = ws.get_values(value_render_option="FORMULA")
        have = {str(r[0]).strip().upper(): i for i, r in enumerate(current, start=1) if r and i > 1}
        next_row = max([1] + list(have.values())) + 1
        add = []
        for key, value, note in C.DEFAULT_SETTINGS:
            if key not in have:
                have[key] = next_row
                add.append({"range": f"A{next_row}:C{next_row}", "values": [[key, value, note]]})
                next_row += 1
        if add:
            ws.batch_update(add, value_input_option="USER_ENTERED")
            log.append(f"+ Sozlamalar: {len(add)} ta kalit")
        self._named_ranges(ws.id, have)

        # Formulalar
        hk = sheets[C.SH_CALC_DAILY]
        hk.clear()
        hk.update(range_name="A1", values=[F.DAILY_CALC_HEADERS, F.daily_calc_formulas()],
                  value_input_option="USER_ENTERED")
        ho = sheets[C.SH_CALC_MONTHLY]
        ho.clear()
        ho.batch_update([{"range": cell, "values": [[v]]} for cell, v in F.monthly_header_formulas().items()]
                        + [{"range": f"A{F.MONTHLY_FIRST_ROW - 1}", "values": [F.MONTHLY_HEADERS]}],
                        value_input_option="USER_ENTERED")
        first, last = F.MONTHLY_FIRST_ROW, F.MONTHLY_FIRST_ROW + F.MONTHLY_ROWS - 1
        ho.update(range_name=f"B{first}:W{last}",
                  values=[F.monthly_row_formulas(r) for r in range(first, last + 1)],
                  value_input_option="USER_ENTERED")
        log.append("✓ Hisob_kunlik va Hisob_oylik formulalari yozildi")

        self.sh.batch_update({"requests": self._format_requests(sheets)})
        for title in (C.SH_CALC_DAILY, C.SH_CALC_MONTHLY, C.SH_ANALYSIS):
            self._protect(sheets[title], f"{title}: tizim hisobi", warning_only=True)
        log.append("✓ Validatsiya, formatlar va himoya o'rnatildi")
        return log

    def _named_ranges(self, settings_sheet_id: int, rows: dict[str, int]) -> None:
        meta = self.sh.fetch_sheet_metadata(params={"fields": "namedRanges"})
        reqs = [{"deleteNamedRange": {"namedRangeId": nr["namedRangeId"]}}
                for nr in meta.get("namedRanges", []) if nr["name"].startswith("S_")]
        for key, row in rows.items():
            if not key.replace("_", "").isalnum():
                continue
            reqs.append({"addNamedRange": {"namedRange": {
                "name": F.named(key),
                "range": _grid(settings_sheet_id, 1, 2, row - 1, row)}}})
        if reqs:
            self.sh.batch_update({"requests": reqs})

    def _format_requests(self, sheets: dict) -> list[dict]:
        reqs: list[dict] = []

        def sid(title: str) -> int:
            return sheets[title].id

        def validate(title: str, col: int, rule: dict, msg: str = "", strict: bool = False):
            reqs.append({"setDataValidation": {
                "range": _grid(sid(title), col, col + 1),
                "rule": {**rule, "strict": strict, "showCustomUi": True,
                         **({"inputMessage": msg} if msg else {})}}})

        def one_of(values: list[str]) -> dict:
            return {"condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": v} for v in values]}}

        def custom(formula: str) -> dict:
            return {"condition": {"type": "CUSTOM_FORMULA",
                                  "values": [{"userEnteredValue": "=" + formula}]}}

        date_rule = {"condition": {"type": "DATE_IS_VALID"}}
        op_rule = {"condition": {"type": "ONE_OF_RANGE",
                                 "values": [{"userEnteredValue": f"={C.SH_OPERATORS}!$A$2:$A"}]}}

        def red_if_invalid(title: str, col: int, formula: str):
            reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [_grid(sid(title), col, col + 1)],
                "booleanRule": {"condition": {"type": "CUSTOM_FORMULA",
                                              "values": [{"userEnteredValue": f"=NOT({formula})"}]},
                                "format": {"backgroundColor": {"red": 0.96, "green": 0.6, "blue": 0.6}}}}}})

        def fmt(title: str, col0: int, col1: int, number_format: dict, row0: int = 1):
            reqs.append({"repeatCell": {
                "range": _grid(sid(title), col0, col1, row0),
                "cell": {"userEnteredFormat": {"numberFormat": number_format}},
                "fields": "userEnteredFormat.numberFormat"}})

        date_fmt = {"type": "DATE", "pattern": "dd.mm.yyyy"}
        text_fmt = {"type": "TEXT"}
        money_fmt = {"type": "NUMBER", "pattern": "#,##0"}

        # Clean previous conditional formats on Kunlik_kiritish to keep setup idempotent
        meta = self.sh.fetch_sheet_metadata(params={"fields": "sheets(properties.sheetId,conditionalFormats)"})
        for s in meta["sheets"]:
            if s["properties"]["sheetId"] == sid(C.SH_DAILY):
                for _ in s.get("conditionalFormats", []):
                    reqs.append({"deleteConditionalFormatRule": {"sheetId": sid(C.SH_DAILY), "index": 0}})

        # Kunlik_kiritish
        k = C.SH_DAILY
        validate(k, 0, date_rule, "Sana: KK.OO.YYYY", strict=True)
        validate(k, 1, op_rule, "Operatorlar ro'yxatidan tanlang", strict=True)
        validate(k, 2, one_of(C.DAILY_STATUSES), "Dam/kelmadi kunlari raqamlarni bo'sh qoldiring", strict=True)
        checks = {
            3: (F.valid_between("D2", 0, 400), "0–400"),
            4: (F.valid_clock("E2"), "soat:daqiqa, masalan 3:25"),
            5: (F.valid_between("F2", 0, 100), "0–100, masalan 76,64"),
            6: (F.valid_clock("G2", 600), "daq:son, 0:00–10:00, masalan 1:43"),
            7: (F.valid_nonneg("H2"), "butun son"),
            8: (F.valid_nonneg("I2"), "butun son"),
            9: (F.valid_nonneg("J2"), "butun son"),
            10: (F.valid_nonneg("K2"), "so'm"),
        }
        for col, (formula, msg) in checks.items():
            validate(k, col, custom(formula), msg)
            red_if_invalid(k, col, formula)
        fmt(k, 0, 1, date_fmt)
        fmt(k, 4, 5, text_fmt)
        fmt(k, 6, 7, text_fmt)
        fmt(k, 10, 11, money_fmt)

        # Operatorlar
        o = C.SH_OPERATORS
        validate(o, 1, date_rule)
        validate(o, 3, one_of(C.OPERATOR_STATUSES), strict=True)
        validate(o, 4, one_of(C.OPERATOR_KINDS), "operator = KPI bilan, yangi = faqat Fixa", strict=True)
        fmt(o, 1, 2, date_fmt)
        fmt(o, 2, 3, money_fmt)

        # Kunlik_sotuv
        s = C.SH_SALES
        validate(s, 0, date_rule, strict=True)
        validate(s, 1, op_rule, strict=True)
        validate(s, 3, one_of(C.LEAD_TYPES), strict=True)
        fmt(s, 0, 1, date_fmt)
        fmt(s, 2, 3, money_fmt)

        # Davomat
        d = C.SH_ATTENDANCE
        validate(d, 0, date_rule, strict=True)
        validate(d, 1, op_rule, strict=True)
        validate(d, 2, one_of(C.ATTENDANCE_STATUSES), strict=True)
        validate(d, 4, custom(F.valid_between("E2", 0, 24)), "soat, 0–24")
        fmt(d, 0, 1, date_fmt)

        # Direktor_bonus
        b = C.SH_DIRECTOR
        validate(b, 0, date_rule, "Oyning istalgan sanasi", strict=True)
        validate(b, 1, op_rule, strict=True)
        fmt(b, 0, 1, date_fmt)
        fmt(b, 2, 3, money_fmt)

        # Reja
        pl = C.SH_PLAN
        validate(pl, 0, date_rule, "Oyning 1-sanasi, masalan 01.10.2026", strict=True)
        validate(pl, 1, op_rule, "Operatorlar ro'yxatidan", strict=True)
        validate(pl, 2, custom(F.valid_nonneg("C2")), "so'm")
        validate(pl, 3, custom(F.valid_between("D2", 0, 100)), "masalan 35")
        fmt(pl, 0, 1, {"type": "DATE", "pattern": "mm.yyyy"})
        for i in (2, 4, 6, 7, 12, 16):
            fmt(pl, i, i + 1, money_fmt)
        fmt(C.SH_HOLIDAYS, 0, 1, date_fmt)
        validate(C.SH_HOLIDAYS, 0, date_rule, strict=True)

        # Hisob varaqlari formatlari
        fmt(C.SH_CALC_DAILY, 0, 1, date_fmt)
        fmt(C.SH_CALC_DAILY, 9, 10, money_fmt)
        fmt(C.SH_CALC_DAILY, 11, 12, money_fmt)
        fmt(C.SH_CALC_DAILY, 13, 14, money_fmt)
        ho = C.SH_CALC_MONTHLY
        fmt(ho, 1, 2, date_fmt, row0=0)
        fmt(ho, 2, 3, date_fmt, row0=F.MONTHLY_FIRST_ROW - 1)
        for letter in F.MONEY_COLS:
            i = ord(letter) - 65
            fmt(ho, i, i + 1, money_fmt, row0=F.MONTHLY_FIRST_ROW - 1)
        for letter in "GIMO":
            i = ord(letter) - 65
            fmt(ho, i, i + 1, {"type": "NUMBER", "pattern": "0.0"}, row0=F.MONTHLY_FIRST_ROW - 1)

        # Sarlavhalar qalin va muzlatilgan
        for title, ws in sheets.items():
            header_row = F.MONTHLY_FIRST_ROW - 1 if title == ho else 0
            reqs.append({"repeatCell": {
                "range": {"sheetId": ws.id, "startRowIndex": header_row, "endRowIndex": header_row + 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold"}})
            reqs.append({"updateSheetProperties": {
                "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": header_row + 1}},
                "fields": "gridProperties.frozenRowCount"}})
        return reqs


def salary_cells(r: SalaryRow) -> list[object]:
    """Hisob_oylik ustunlari tartibida (Arxiv va eksport uchun)."""
    v, b = r.values, r.bonuses

    def num(x, nd=1):
        return "" if x is None else round(x, nd)
    return [r.operator, r.kind, r.hire_date.strftime("%d.%m.%Y") if r.hire_date else "",
            r.worked_workdays, r.fixa_full, r.fixa,
            num(v["konversiya"]), b["konversiya"], num(v["ulanish"]), b["ulanish"],
            num(v["chek"], 0), b["chek"], num(v["sifat"]), b["sifat"],
            num(v["gaplashish"]), b["gaplashish"], r.kpi_total,
            r.late_days, r.work_hours, r.attendance_bonus, r.director_bonus,
            r.total, r.scenario_total]
