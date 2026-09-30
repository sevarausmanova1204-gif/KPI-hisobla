"""Google Sheets formulalari: "Hisob_kunlik" va "Hisob_oylik" varaqlari.

Formulalar "Sozlamalar" varag'idagi nomlangan diapazonlarga (S_<KALIT>)
tayanadi, shuning uchun Sozlamalarda qiymat o'zgarsa hisob darhol yangilanadi.
Mantiq `calc.py` bilan bir xil; `python -m kpi tekshir` ikkalasini solishtiradi.
"""
from __future__ import annotations

from . import config as C

K = C.SH_DAILY
HK = C.SH_CALC_DAILY
OPS = C.SH_OPERATORS
DAV = C.SH_ATTENDANCE
DIR = C.SH_DIRECTOR

MONTHLY_FIRST_ROW = 5
MONTHLY_ROWS = 100


def named(key: str) -> str:
    return f"S_{key}"


def _dur(x: str) -> str:
    """'A:B' matn yoki Sheets vaqti → A*60+B (parsing.to_duration_units bilan bir xil)."""
    t = f"TO_TEXT({x})"
    return (f'IF(ISNUMBER({x}),IF({x}<1,{x}*1440,{x}),'
            f'IFERROR(VALUE(REGEXEXTRACT({t},"^(\\d+):"))*60'
            f'+VALUE(REGEXEXTRACT({t},"^\\d+:(\\d+)"))'
            f'+IFERROR(VALUE(REGEXEXTRACT({t},"^\\d+:\\d+:(\\d+)"))/60,0)))')


# ---- Hisob_kunlik ---------------------------------------------------------

DAILY_CALC_HEADERS = [
    "Sana", "Operator", "Holat", "Ulanish", "Kunlik gaplashish (daq)", "Sifat %",
    "O'rtacha qo'ng'iroq (sek)", "Sifatli lead", "Sotuv soni", "Sotuv summasi",
    "Konversiya (kun) %", "Chek (kun)", "Konversiya (oy boshidan) %", "Chek (oy boshidan)",
    "Ulanish o'rt. (oy boshidan)", "Sifat o'rt. (oy boshidan)", "Qo'ng'iroq o'rt. sek (oy boshidan)",
]


def daily_calc_formulas() -> list[str]:
    """2-qator uchun ARRAYFORMULA'lar (A..Q). Har biri butun ustunni to'ldiradi."""
    def k(col: str) -> str:
        return f"{K}!{col}2:{col}"

    has = f'({k("B")}<>"")'
    worked = f'({k("C")}="{C.WORKED}")'

    def num(col: str) -> str:
        return f"=ARRAYFORMULA(IF({has}*{worked}*ISNUMBER({k(col)}),{k(col)},))"

    def dur(col: str) -> str:
        return f'=ARRAYFORMULA(IF({has}*{worked}*({k(col)}<>""),{_dur(k(col))},))'

    mtd = ('B2:B,B2:B,A2:A,">="&(EOMONTH(A2:A,-1)+1),A2:A,"<="&A2:A')

    def mtd_avg(col: str) -> str:
        return (f'=ARRAYFORMULA(IF(A2:A="",,IFERROR(SUMIFS({col}2:{col},{mtd})'
                f'/COUNTIFS({col}2:{col},">=0",{mtd}))))')

    return [
        f"=ARRAYFORMULA(IF({has},{k('A')},))",
        f"=ARRAYFORMULA(IF({has},{k('B')},))",
        f"=ARRAYFORMULA(IF({has},{k('C')},))",
        num("D"),
        dur("E"),
        num("F"),
        dur("G"),
        num("I"),
        num("J"),
        num("K"),
        "=ARRAYFORMULA(IF(H2:H>0,I2:I/H2:H*100,))",
        "=ARRAYFORMULA(IF(I2:I>0,J2:J/I2:I,))",
        f'=ARRAYFORMULA(IF(A2:A="",,IFERROR(SUMIFS(I2:I,{mtd})/SUMIFS(H2:H,{mtd})*100)))',
        f'=ARRAYFORMULA(IF(A2:A="",,IFERROR(SUMIFS(J2:J,{mtd})/SUMIFS(I2:I,{mtd}))))',
        mtd_avg("D"),
        mtd_avg("F"),
        mtd_avg("G"),
    ]


# ---- Hisob_oylik ----------------------------------------------------------

MONTHLY_HEADERS = [
    "Xodim", "Turi", "Ishga kirgan", "Ishlagan ish kuni", "Fixa (to'liq)", "Fixa",
    "Konversiya %", "Konversiya bonusi", "Kunlik qo'ng'iroq", "Qo'ng'iroq bonusi",
    "O'rtacha chek", "Chek bonusi", "Sifat %", "Sifat bonusi",
    "O'rt. gaplashish (sek)", "Gaplashish bonusi", "KPI jami",
    "Kechikishlar", "Ish soati", "Davomat bonusi", "Direktor bonusi", "Jami oylik",
    "Ssenariy: Fixa X bo'lsa",
]
MONEY_COLS = "EFHJKLNPQTUVW"


def monthly_header_formulas() -> dict[str, str]:
    first = MONTHLY_FIRST_ROW
    return {
        "A1": "Oy (1-sana):",
        "B1": f"={named('JORIY_OY')}",
        "C1": "← boshqa oyni ko'rish uchun sanani yozing",
        "A2": "Hisob sanasi:",
        "B2": "=MIN(TODAY()-1,EOMONTH(B1,0))",
        f"A{first}": (
            f'=IFERROR(FILTER({OPS}!A2:A,{OPS}!A2:A<>"",'
            f'IF(ISNUMBER({OPS}!B2:B),{OPS}!B2:B,0)<=EOMONTH($B$1,0),'
            f'({OPS}!D2:D<>"ketgan")+(COUNTIFS({K}!B2:B,{OPS}!A2:A,{K}!A2:A,">="&$B$1,'
            f'{K}!A2:A,"<="&EOMONTH($B$1,0))>0)),"")'),
    }


def _bonus(value: str, prefix: str, r: int) -> str:
    def lvl(i: int, inner: str) -> str:
        return (f"IF({value}>={named(f'{prefix}_{i}_CHEG')}-1E-9,"
                f"{named(f'{prefix}_{i}_BONUS')},{inner})")
    expr = lvl(3, lvl(2, lvl(1, "0")))
    return f'=IF(OR($A{r}="",{value}="",$B{r}<>"operator"),0,{expr})'


def monthly_row_formulas(r: int) -> list[str]:
    """r-qator uchun B..W formulalari (A ustuni FILTER bilan to'ladi)."""
    a = f"$A{r}"
    blank = f'{a}=""'
    crit = f'{HK}!$B$2:$B,{a},{HK}!$A$2:$A,">="&$B$1,{HK}!$A$2:$A,"<="&$B$2'
    dav_crit = f'{DAV}!$B$2:$B,{a},{DAV}!$A$2:$A,">="&$B$1,{DAV}!$A$2:$A,"<="&EOMONTH($B$1,0)'

    def avg(col: str) -> str:
        return (f'=IF({blank},"",IFERROR(SUMIFS({HK}!${col}$2:${col},{crit})'
                f'/COUNTIFS({HK}!${col}$2:${col},">=0",{crit}),""))')

    prorated = f"OR({named('FIXA_PROPORSIONAL')}=1,AND(ISNUMBER($C{r}),$C{r}>$B$1))"
    days = (
        f'=IF({blank},"",LET(h,$C{r},s,IF(AND(ISNUMBER(h),h>$B$1),h,$B$1),e,EOMONTH($B$1,0),'
        f'dav,COUNTIFS({dav_crit}),'
        f'keldi,SUMPRODUCT(({DAV}!$B$2:$B={a})*({DAV}!$A$2:$A>=s)*({DAV}!$A$2:$A<=e)'
        f'*({DAV}!$C$2:$C="keldi")*(WEEKDAY({DAV}!$A$2:$A)<>1)),'
        f'kelmadi,SUMPRODUCT(({K}!$B$2:$B={a})*({K}!$A$2:$A>=s)*({K}!$A$2:$A<=e)'
        f'*({K}!$C$2:$C="kelmadi")*(WEEKDAY({K}!$A$2:$A)<>1)),'
        f'MIN({named("ISH_KUNLARI")},IF(dav>0,keldi,NETWORKDAYS.INTL(s,e,"0000001")-kelmadi))))')
    extras = f"$Q{r}+$T{r}+$U{r}"
    return [
        # B Turi
        f'=IF({blank},"",LET(t,IFERROR(VLOOKUP({a},{OPS}!$A$2:$E,5,FALSE),""),IF(t="","operator",LOWER(t))))',
        # C Ishga kirgan
        f'=IF({blank},"",LET(h,IFERROR(VLOOKUP({a},{OPS}!$A$2:$B,2,FALSE),""),IF(ISNUMBER(h),h,"")))',
        # D Ishlagan ish kuni
        days,
        # E Fixa (to'liq)
        f'=IF({blank},"",LET(f,IFERROR(VLOOKUP({a},{OPS}!$A$2:$C,3,FALSE),""),IF(ISNUMBER(f),f,{named("FIXA")})))',
        # F Fixa
        f'=IF({blank},"",IF({prorated},ROUND($E{r}/{named("ISH_KUNLARI")}*$D{r},0),$E{r}))',
        # G Konversiya
        f'=IF({blank},"",IFERROR(SUMIFS({HK}!$I$2:$I,{crit})/SUMIFS({HK}!$H$2:$H,{crit})*100,""))',
        _bonus(f"$G{r}", "KONV", r),
        # I Kunlik qo'ng'iroq
        avg("D"),
        _bonus(f"$I{r}", "ULAN", r),
        # K O'rtacha chek
        f'=IF({blank},"",IFERROR(SUMIFS({HK}!$J$2:$J,{crit})/SUMIFS({HK}!$I$2:$I,{crit}),""))',
        _bonus(f"$K{r}", "CHEK", r),
        # M Sifat
        avg("F"),
        _bonus(f"$M{r}", "SIFAT", r),
        # O O'rt. gaplashish
        avg("G"),
        _bonus(f"$O{r}", "GAPL", r),
        # Q KPI jami
        f'=IF({blank},"",$H{r}+$J{r}+$L{r}+$N{r}+$P{r})',
        # R Kechikishlar
        f'=IF({blank},"",COUNTIFS({dav_crit},{DAV}!$D$2:$D,">0"))',
        # S Ish soati
        f'=IF({blank},"",SUMIFS({DAV}!$E$2:$E,{dav_crit}))',
        # T Davomat bonusi
        (f'=IF({blank},"",IF(OR($B{r}<>"operator",COUNTIFS({dav_crit})=0),0,'
         f'IF($S{r}>={named("DAV_SOAT")}-1E-9,IF($R{r}=0,{named("DAV_BONUS_0")},'
         f'IF($R{r}<={named("DAV_MAX_KECH")},{named("DAV_BONUS_1")},0)),0)))'),
        # U Direktor bonusi
        (f'=IF({blank},"",SUMIFS({DIR}!$C$2:$C,{DIR}!$B$2:$B,{a},{DIR}!$A$2:$A,">="&$B$1,'
         f'{DIR}!$A$2:$A,"<="&EOMONTH($B$1,0)))'),
        # V Jami oylik
        f'=IF({blank},"",$F{r}+{extras})',
        # W Ssenariy
        (f'=IF({blank},"",IF($B{r}="operator",IF({prorated},'
         f'ROUND({named("FIXA_SSENARIY")}/{named("ISH_KUNLARI")}*$D{r},0),{named("FIXA_SSENARIY")})'
         f'+{extras},$V{r}))'),
    ]


# ---- Validatsiya (Kunlik_kiritish, 2-qatordan) ---------------------------

def valid_clock(cell: str, max_units: int | None = None) -> str:
    t = f"TO_TEXT({cell})"
    ok = f'REGEXMATCH({t},"^\\d{{1,2}}:[0-5]\\d$")'
    if max_units is not None:
        ok = (f'AND({ok},VALUE(REGEXEXTRACT({t},"^(\\d+)"))*60'
              f'+VALUE(REGEXEXTRACT({t},":(\\d+)$"))<={max_units})')
    return f'OR({cell}="",{ok})'


def valid_between(cell: str, lo: float, hi: float) -> str:
    return f'OR({cell}="",AND(ISNUMBER({cell}),{cell}>={lo},{cell}<={hi}))'


def valid_nonneg(cell: str) -> str:
    return f'OR({cell}="",AND(ISNUMBER({cell}),{cell}>=0))'


# ---- Reja ----------------------------------------------------------------

PLAN_CALC_HEADERS = [
    "Kunlik reja (so'm)", "Haftalik reja (so'm)", "Mijoz oylik", "Mijoz haftalik",
    "Mijoz kunlik", "Kerakli sifatli lead (oy)", "Fakt summa", "Fakt mijoz",
    "Bajarilish %", "Qolgan ish kuni", "Kuniga kerak (so'm)",
]
PLAN_FIRST_CALC_COL = "G"


def plan_formulas() -> list[str]:
    """Reja!G2:Q2 — har biri MAP bilan butun ustunni to'ldiradi."""
    kk = f"{K}!$"
    fact = (lambda col: f'=MAP(A2:A,B2:B,LAMBDA(a,b,IF(b="","",SUMIFS({kk}{col}$2:${col},'
            f'{kk}B$2:$B,b,{kk}A$2:$A,">="&a,{kk}A$2:$A,"<="&EOMONTH(a,0),{kk}C$2:$C,"{C.WORKED}"))))')
    days, weeks, check = named("REJA_ISH_KUNLARI"), named("REJA_HAFTALAR"), named("REJA_CHEK")
    return [
        f'=MAP(C2:C,LAMBDA(c,IF(c="","",ROUND(c/{days},0))))',
        f'=MAP(C2:C,LAMBDA(c,IF(c="","",ROUND(c/{weeks},0))))',
        f'=MAP(C2:C,E2:E,LAMBDA(c,e,IF(c="","",ROUND(c/IF(e="",{check},e),1))))',
        f'=MAP(I2:I,LAMBDA(i,IF(i="","",ROUND(i/{weeks},1))))',
        f'=MAP(I2:I,LAMBDA(i,IF(i="","",ROUND(i/{days},1))))',
        '=MAP(I2:I,D2:D,LAMBDA(i,d,IF(OR(i="",d="",d=0),"",ROUND(i/(IF(d<=1,d*100,d)/100),0))))',
        fact("K"),
        fact("J"),
        '=MAP(C2:C,M2:M,LAMBDA(c,m,IF(c="","",ROUND(m/c*100,1))))',
        (f'=MAP(A2:A,C2:C,LAMBDA(a,c,IF(c="","",IF(TODAY()>EOMONTH(a,0),0,'
         f'NETWORKDAYS.INTL(MAX(TODAY(),a),EOMONTH(a,0),"0000001",{C.SH_HOLIDAYS}!$A$2:$A)))))'),
        '=MAP(C2:C,M2:M,P2:P,LAMBDA(c,m,p,IF(c="","",ROUND(MAX(0,c-m)/MAX(1,p),0))))',
    ]
