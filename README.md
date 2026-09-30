# KPI-hisobla — Call-markaz KPI platformasi

Operatorlarning kunlik ko'rsatkichlari bitta Google Sheets faylga yig'iladi.
Tizim KPI bonuslari va oylik maoshni avtomatik hisoblaydi, har kuni orqada
qolgan operatorlar uchun choralar rejasini tuzadi va Telegram'ga yuboradi.

Asos: "Call-markaz KPI platformasi — texnik topshiriq" hujjati.

## Tarkib

| Modul | Vazifasi | TZ bo'limi |
|---|---|---|
| `kpi/config.py` | 5 ta KPI, bosqichlar, bonuslar, Fixa, normalar (standart "Sozlamalar") | 3, 5 |
| `kpi/models.py`, `kpi/parsing.py` | Varaqlarni o'qish: son, `daq:son` / `soat:daqiqa`, sana | 4 |
| `kpi/calc.py` | O'rtachalar, konversiya, chek, bosqichlar, davomat, proporsional Fixa, jami oylik | 5, 8 |
| `kpi/formulas.py` | `Hisob_kunlik` va `Hisob_oylik` uchun jonli Sheets formulalari | 3, 5, 8 |
| `kpi/analysis.py` | Holat belgisi, chegaragacha masofa, prognoz, choralar (ko'pi bilan 2 ta), namuna | 6 |
| `kpi/report.py`, `kpi/telegram.py` | Kunlik, haftalik va oylik Telegram hisobotlari | 7 |
| `kpi/sheets.py` | Varaqlar, validatsiya, nomlangan diapazonlar, Tahlil, Arxiv, himoya | 3, 4, 8 |
| `kpi/local.py` | Excel eksporti va offlayn sinov uchun `.xlsx` o'qish | 8 |

## Google Sheets tuzilmasi

`python -m kpi setup` quyidagi varaqlarni yaratadi. Mavjud ma'lumotga tegmaydi,
shuning uchun uni qayta ishga tushirish xavfsiz.

| Varaq | Ustunlar / vazifasi |
|---|---|
| **Sozlamalar** | `Kalit · Qiymat · Izoh`. Har bir kalit `S_<KALIT>` nomli diapazonga aylanadi, formulalar shularni o'qiydi. Masalan, `FIXA` ni 3 000 000 ga o'zgartirsangiz, hisob darhol yangilanadi. |
| **Operatorlar** | Ism · Ishga kirgan sana · Fixa · Holat (faol/sinov/ketgan) · Turi (operator/yangi) · Telegram ID |
| **Kunlik_kiritish** | Sana · Operator · Holat · Ulanish · Kunlik gaplashish (`3:25`) · Sifat (`76,64`) · O'rtacha qo'ng'iroq (`1:43`) · Umumiy lead · Sifatli lead · Sotuv soni · Sotuv summasi |
| **Kunlik_sotuv** | Sana · Operator · Summa · Lead turi. Kunlik_kiritish bilan solishtiriladi, farq bo'lsa hisobotda ko'rsatiladi. |
| **Davomat** | Sana · Operator · Holat (keldi/kelmadi/dam) · Kechikish (daq) · Ish soati |
| **Direktor_bonus** | Oy · Operator · Summa · Izoh. *TZ'dagi ro'yxatga qo'shimcha:* direktor bonusi qo'lda kiritiladigan joy. |
| **Hisob_kunlik** | Formulalar: kunlik va oy boshidan konversiya, chek va o'rtachalar |
| **Hisob_oylik** | Formulalar: 5 ta KPI, bonuslar, Fixa, davomat, jami oylik, "Fixa X bo'lsa" ssenariysi. Boshqa oyni ko'rish uchun B1 ga sana yozing. |
| **Tahlil** | Har kuni har bir operator × KPI uchun: holat, chegaragacha masofa, so'mdagi ta'siri, kerakli kunlik qiymat, chora |
| **Arxiv** | Oy yopilganda maosh jadvali shu yerga yoziladi va himoyalanadi |

Kiritish qoidalari validatsiya orqali o'rnatiladi: sana, ro'yxatlar,
sifat 0–100, ulanish 0–400, o'rtacha qo'ng'iroq 0:00–10:00. Qoidaga mos
kelmagan katak qizil rangga bo'yaladi. Vaqt ustunlari matn formatida,
shuning uchun `1:43` "1 soat 43 daqiqa" deb talqin qilinmaydi.

## Hisob-kitob qoidalari (qisqacha)

- Ulanish, sifat, o'rtacha qo'ng'iroq va kunlik gaplashish faqat `ishladi`
  kunlari bo'yicha o'rtacha olinadi. Bo'sh kataklar hisobga kirmaydi.
- Konversiya = sotuv soni ÷ sifatli lead × 100. O'rtacha chek = sotuv summasi ÷ sotuv soni.
- Har bir KPI uchun eng yuqori mos kelgan bosqich olinadi. Chegaradan past bo'lsa, bonus 0.
- Davomat bonusi: ish soati ≥ 240 va kechikish bo'lmasa — 900 000; 1–2 marta
  kechikkan bo'lsa — 720 000. Davomat ma'lumoti bo'lmasa, bonus 0.
- Fixa: oy o'rtasida ishga kirganlar uchun `Fixa ÷ 26 × ishlagan ish kunlari`.
  Yakshanbalar hisobga kirmaydi, kelmagan kunlar ayriladi. Ishlagan kunlar
  Davomat varag'idan olinadi, u bo'sh bo'lsa kalendardan hisoblanadi.
  `FIXA_PROPORSIONAL=1` qilinsa, qoida hamma uchun qo'llanadi.
- `Turi = yangi` bo'lgan xodim faqat Fixa oladi.
- Jami oylik = Fixa + 5 ta KPI bonusi + davomat bonusi + direktor bonusi.

Python hisobi (`calc.py`) va Sheets formulalari bir xil qoidalar asosida
yozilgan. `python -m kpi tekshir` ikkalasini so'mgacha solishtiradi.

## O'rnatish

1. Python 3.10+ o'rnating, so'ng: `pip install -r requirements.txt`
2. Google Cloud'da service account yarating va JSON kalitini yuklab oling.
   Sheets faylini service account email'iga **Editor** huquqi bilan ulashing.
3. `.env.example` faylini `.env` deb nusxalang yoki o'zgaruvchilarni muhitga
   o'rnating: `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE` (yoki `..._JSON`),
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_DIRECTOR_CHAT_ID`.
4. `python -m kpi setup` buyrug'i varaqlar, validatsiya va formulalarni yaratadi.
5. Operatorlar varag'ini to'ldiring va kunlik ma'lumot kiritishni boshlang.

## Buyruqlar

```bash
python -m kpi setup                       # Sheets tuzilmasi
python -m kpi ogohlantirish               # 12:00: kechagi kun kiritilmaganlar
python -m kpi kunlik [--sana 2026-09-17]  # Tahlil varag'i + Telegram
python -m kpi haftalik                    # dushanba: hafta bo'yicha o'sish/pasayish, choralar natijasi
python -m kpi oylik [--oy 2026-09]        # Arxiv + Excel + Telegram (direktorga)
python -m kpi tasdiqlash --oy 2026-09     # direktor tasdig'idan keyin
python -m kpi tekshir                     # Sheets formulalari = Python hisobi?
python -m kpi shablon                     # offlayn sinov uchun .xlsx shablon
```

`--yuborma` bayrog'i bilan hisobot Telegram'ga yuborilmaydi va Sheets'ga
yozilmaydi, faqat ekranga chiqadi. `--xlsx fayl.xlsx` bilan ma'lumot Sheets
o'rniga Excel fayldan o'qiladi, masalan:
`python -m kpi kunlik --xlsx sentabr.xlsx --yuborma`.

## Jadval (avtomatik ishga tushirish)

`.github/workflows/kpi-schedule.yml` quyidagi vaqtlarda ishlaydi (Toshkent vaqti):
12:00 ogohlantirish, 12:30 kunlik hisobot, dushanba 12:45 haftalik hisobot,
har oyning 1-sanasi 12:50 oylik maosh. Ishlashi uchun repo sozlamalarida
Secrets qo'shilishi kerak (ro'yxat fayl boshida). Secrets bo'lmasa, workflow
hech narsa qilmasdan tugaydi. Serverda ishlatmoqchi bo'lsangiz, xuddi shu
buyruqlarni cron'ga qo'yish kifoya.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest -q
```

Testlar qabul mezonlarini tekshiradi. Aziza sentabr natijasi bo'yicha
4 820 000 olishi kerak. Mashhura (21 kun) 1 615 385, Behzod (25 kun)
1 923 077 olishi kerak. Dam olish kunlari va bo'sh kataklar o'rtachaga
kirmasligi, Sozlamalar o'zgarganda hisob yangilanishi va hisobotdagi
masofa matni ham tekshiriladi, masalan:
"sifat 67,9% → 70% ga 2,1 punkt kerak = +360 000 so'm".

## Holat

- [x] 1-bosqich: Sheets tuzilmasi, validatsiya, Sozlamalar, kunlik va oylik formulalar
- [x] 2-bosqich: kunlik, haftalik va oylik Telegram hisobot, holat belgilari, prognoz, choralar
- [x] 3-bosqich (qisman): oy yopish → Arxiv, himoya, tasdiqlash, Excel eksporti, ssenariy ustuni
- [ ] PDF eksporti
- [ ] Mavjud `lead_report.py` / `extra_report.py` skriptlarini ulash (ular repoda yo'q)
- [ ] Sentabr ma'lumotlarini "SENTABR KPI" varag'idan ko'chirish va 6 operator bo'yicha solishtirish
- [ ] 4-bosqich: CRM va telefoniyadan import, shaxsiy hisobotlar, AI tahlil, dashboard
