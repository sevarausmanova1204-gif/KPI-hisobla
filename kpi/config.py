"""Sozlamalar: KPI ta'riflari va "Sozlamalar" varag'ining standart qiymatlari.

Barcha summalar va chegaralar shu yerdan (yoki Sheets'dagi "Sozlamalar"
varag'idan) o'qiladi — hisob-kitob kodida raqam qattiq yozilmaydi.
"""
from __future__ import annotations

from dataclasses import dataclass

# Varaq nomlari
SH_SETTINGS = "Sozlamalar"
SH_OPERATORS = "Operatorlar"
SH_DAILY = "Kunlik_kiritish"
SH_SALES = "Kunlik_sotuv"
SH_ATTENDANCE = "Davomat"
SH_DIRECTOR = "Direktor_bonus"
SH_CALC_DAILY = "Hisob_kunlik"
SH_CALC_MONTHLY = "Hisob_oylik"
SH_ANALYSIS = "Tahlil"
SH_ARCHIVE = "Arxiv"
SH_PLAN = "Reja"
SH_HOLIDAYS = "Bayramlar"

# Holat qiymatlari
WORKED = "ishladi"
DAILY_STATUSES = ["ishladi", "dam", "kasal", "kelmadi"]
ATTENDANCE_STATUSES = ["keldi", "kelmadi", "dam"]
OPERATOR_STATUSES = ["faol", "sinov", "ketgan"]
OPERATOR_KINDS = ["operator", "yangi"]  # yangi = faqat Fixa, KPI bonussiz
LEAD_TYPES = ["sifatli", "oddiy"]


@dataclass(frozen=True)
class KpiDef:
    key: str          # ichki nom
    name: str         # hisobotdagi nom
    unit: str         # birlik (%, ta, so'm, sek)
    prefix: str       # Sozlamalar kalitlari prefiksi
    action: str       # orqada qolganda tavsiya etiladigan chora
    owner: str        # mas'ul
    deadline: str     # muddat


# Maosh jadvalidagi tartib: konversiya, qo'ng'iroq, chek, sifat, gaplashish
KPIS: list[KpiDef] = [
    KpiDef("konversiya", "Konversiya", "%", "KONV",
           "E'tirozlarga javob mashqi, eng yaxshi operator bilan juftlikda tinglash",
           "Rahbar", "Hafta ichida"),
    KpiDef("ulanish", "Kunlik qo'ng'iroq", "ta", "ULAN",
           "Soatlik reja (≈19 ta/soat), avtodozvon, bo'sh vaqt nazorati",
           "Rahbar", "Ertasi kun"),
    KpiDef("chek", "O'rtacha chek", "so'm", "CHEK",
           "Qo'shimcha xizmat/aksiya paketlarini taklif qilish skripti (aksiya katalogidan)",
           "Rahbar", "Ertasi kun"),
    KpiDef("sifat", "Sifat", "%", "SIFAT",
           "5 ta yozuvni tinglab, skript bo'yicha 15 daqiqalik coaching",
           "Sifat nazoratchisi", "Hafta ichida"),
    KpiDef("gaplashish", "O'rtacha gaplashish", "sek", "GAPL",
           "Ehtiyojni aniqlash savollari va taklif qismini kengaytirish; 3 ta yozuvni tinglash",
           "Rahbar + operator", "2 kun"),
]
KPI_BY_KEY = {k.key: k for k in KPIS}

NO_DATA_ACTION = ("Ma'lumot yo'q (2+ kun)",
                  "Sababini aniqlash: ta'til, kasallik yoki kiritilmagan",
                  "Kirituvchi", "Bugun")

# (kalit, standart qiymat, izoh). Tartib "Sozlamalar" varag'idagi tartib.
DEFAULT_SETTINGS: list[tuple[str, object, str]] = [
    ("JORIY_OY", "=EOMONTH(TODAY()-1,-1)+1", "Hisob_oylik uchun oy (oyning 1-sanasi). Standart: kechagi kun oyi"),
    ("FIXA", 2_000_000, "Operator Fixasi (Operatorlar varag'ida alohida ko'rsatilmasa)"),
    ("FIXA_SSENARIY", 3_000_000, "Ssenariy ustuni uchun muqobil Fixa"),
    ("ISH_KUNLARI", 26, "Oydagi ish kunlari (proporsional Fixa uchun)"),
    ("FIXA_PROPORSIONAL", 0, "1 = hamma uchun Fixa ishlagan kunga proporsional; 0 = faqat oy o'rtasida kirganlar"),
    ("KONV_1_CHEG", 25, "Konversiya 1-bosqich chegarasi, %"),
    ("KONV_1_BONUS", 900_000, "Konversiya 1-bosqich bonusi"),
    ("KONV_2_CHEG", 30, "Konversiya 2-bosqich chegarasi, %"),
    ("KONV_2_BONUS", 1_440_000, "Konversiya 2-bosqich bonusi"),
    ("KONV_3_CHEG", 35, "Konversiya 3-bosqich chegarasi, %"),
    ("KONV_3_BONUS", 1_800_000, "Konversiya 3-bosqich bonusi"),
    ("ULAN_1_CHEG", 150, "Kunlik qo'ng'iroq 1-bosqich, ta"),
    ("ULAN_1_BONUS", 600_000, "Kunlik qo'ng'iroq 1-bosqich bonusi"),
    ("ULAN_2_CHEG", 200, "Kunlik qo'ng'iroq 2-bosqich, ta"),
    ("ULAN_2_BONUS", 960_000, "Kunlik qo'ng'iroq 2-bosqich bonusi"),
    ("ULAN_3_CHEG", 250, "Kunlik qo'ng'iroq 3-bosqich, ta"),
    ("ULAN_3_BONUS", 1_200_000, "Kunlik qo'ng'iroq 3-bosqich bonusi"),
    ("CHEK_1_CHEG", 450_000, "O'rtacha chek 1-bosqich, so'm"),
    ("CHEK_1_BONUS", 450_000, "O'rtacha chek 1-bosqich bonusi"),
    ("CHEK_2_CHEG", 525_000, "O'rtacha chek 2-bosqich, so'm"),
    ("CHEK_2_BONUS", 720_000, "O'rtacha chek 2-bosqich bonusi"),
    ("CHEK_3_CHEG", 600_000, "O'rtacha chek 3-bosqich, so'm"),
    ("CHEK_3_BONUS", 900_000, "O'rtacha chek 3-bosqich bonusi"),
    ("SIFAT_1_CHEG", 70, "Sifat 1-bosqich, %"),
    ("SIFAT_1_BONUS", 360_000, "Sifat 1-bosqich bonusi"),
    ("SIFAT_2_CHEG", 85, "Sifat 2-bosqich, %"),
    ("SIFAT_2_BONUS", 510_000, "Sifat 2-bosqich bonusi"),
    ("SIFAT_3_CHEG", 95, "Sifat 3-bosqich, %"),
    ("SIFAT_3_BONUS", 600_000, "Sifat 3-bosqich bonusi"),
    ("GAPL_1_CHEG", 110, "O'rtacha gaplashish 1-bosqich, sek"),
    ("GAPL_1_BONUS", 300_000, "O'rtacha gaplashish 1-bosqich bonusi"),
    ("GAPL_2_CHEG", 130, "O'rtacha gaplashish 2-bosqich, sek"),
    ("GAPL_2_BONUS", 480_000, "O'rtacha gaplashish 2-bosqich bonusi"),
    ("GAPL_3_CHEG", 150, "O'rtacha gaplashish 3-bosqich, sek"),
    ("GAPL_3_BONUS", 600_000, "O'rtacha gaplashish 3-bosqich bonusi"),
    ("DAV_SOAT", 240, "Davomat bonusi uchun oylik ish soati (min)"),
    ("DAV_BONUS_0", 900_000, "Davomat bonusi: kechikish 0"),
    ("DAV_BONUS_1", 720_000, "Davomat bonusi: kechikish 1..DAV_MAX_KECH"),
    ("DAV_MAX_KECH", 2, "Kichik davomat bonusi uchun ruxsat etilgan kechikishlar soni"),
    ("NORMA_ULANISH", 150, "Kunlik qo'ng'iroq normasi, ta"),
    ("NORMA_GAPLASHISH_DAQ", 180, "Kunlik gaplashish normasi, daqiqa (3 soat)"),
    ("NORMA_SIFAT", 70, "Sifat normasi, %"),
    ("NORMA_MAQSAD_DAQ", 200, "Kunlik gaplashish maqsadi, daqiqa (3:20)"),
    ("SARIQ_FOIZ", 90, "Sariq holat: chegaraning shu foizidan yuqori"),
    ("MAX_CHORA", 2, "Bir operatorga kuniga beriladigan choralar soni"),
    ("MALUMOT_YOQ_KUN", 2, "Necha ish kuni ma'lumot bo'lmasa chora beriladi"),
    ("REJA_CHEK", 400_000, "Reja: mijozlar sonini hisoblash uchun o'rtacha chek"),
    ("REJA_ISH_KUNLARI", 26, "Reja: kunlik reja = oylik / shu son"),
    ("REJA_HAFTALAR", 4, "Reja: haftalik reja = oylik / shu son"),
]

# Bayramlar varag'i bo'sh bo'lsa, setup shu sanalarni qo'yadi (tekshirib, hayitlarni qo'shing)
DEFAULT_HOLIDAYS = [
    ("2026-01-01", "Yangi yil"), ("2026-03-08", "Xotin-qizlar kuni"),
    ("2026-03-21", "Navro'z"), ("2026-05-09", "Xotira va qadrlash kuni"),
    ("2026-09-01", "Mustaqillik kuni"), ("2026-10-01", "O'qituvchi va murabbiylar kuni"),
    ("2026-12-08", "Konstitutsiya kuni"),
]


class Settings:
    """Kalit → qiymat. Yo'q kalitlar standart qiymatdan olinadi."""

    def __init__(self, values: dict[str, object] | None = None):
        self._values: dict[str, float] = {}
        for key, default, _ in DEFAULT_SETTINGS:
            if isinstance(default, (int, float)):
                self._values[key] = float(default)
        for key, value in (values or {}).items():
            num = _as_float(value)
            if num is not None:
                self._values[str(key).strip().upper()] = num

    def get(self, key: str) -> float:
        return self._values[key]

    def int(self, key: str) -> int:
        return int(round(self._values[key]))

    def tiers(self, prefix: str) -> list[tuple[float, float]]:
        """[(chegara, bonus), ...] o'sish tartibida."""
        out = []
        level = 1
        while f"{prefix}_{level}_CHEG" in self._values:
            out.append((self._values[f"{prefix}_{level}_CHEG"],
                        self._values.get(f"{prefix}_{level}_BONUS", 0.0)))
            level += 1
        return sorted(out)

    def as_dict(self) -> dict[str, float]:
        return dict(self._values)


def _as_float(value: object) -> float | None:
    from .parsing import to_number
    return to_number(value)
