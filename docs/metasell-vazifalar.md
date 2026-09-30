# Metasell AI xulosalaridan vazifalar tayyorlash

Bu topshiriq kompyuterdagi Claude Desktop sessiyasi uchun. Faqat u yerda
brauzer paneli Metasell'ga kira oladi. Quyidagi matnni sessiyaga to'liq
nusxalab bering.

---

KPI-hisobla repozitoriysida ishlaymiz (`sevarausmanova1204-gif/KPI-hisobla`,
branch `claude/intelligent-franklin-t0e67b`).

1. Brauzer panelida https://console.metasell.ai/dashboards/home ni och. Agar
   kirish so'ralsa, men o'zim kiraman. Metasell'da hech narsani o'zgartirma,
   faqat o'qi.
2. Oktabr 2026 bo'yicha (hali yo'q bo'lsa, oxirgi 30 kun) har bir operator
   uchun Metasell AI xulosalarini yig':
   - sifat bahosi (%);
   - skriptdan chetga chiqishlar;
   - eng ko'p uchraydigan xatolar: salomlashish, ehtiyojni aniqlash, taqdimot,
     e'tirozlar bilan ishlash, yakunlash;
   - AI tavsiyalari;
   - misol qo'ng'iroqlar (sana va havola).
3. Operator ismlarini `rejalar/2026-10.csv` dagi ismlarga moslashtir. Bir
   odamning turli yozilishi bitta xodim: Bekzod = Behzod, Mashxura = Mashhura,
   Shobonoy = Shabonoy. Ruxshona va Ruhshona esa ikki xil odam. Zuhra, Javohir
   va Ruxsora endi ishlamaydi.
4. Har operatorga ko'pi bilan 3 ta aniq vazifa tuz:
   - eng ko'p pul ta'siri bor zaif joy birinchi o'rinda;
   - har bir vazifada: nima qilinadi, mas'ul, muddat va o'lchanadigan maqsad
     (masalan, "e'tiroz bosqichi bahosi 55% → 70%, 1 hafta");
   - vazifa `kpi/config.py` dagi KPI'lar (sifat, konversiya, o'rtacha chek,
     gaplashish, qo'ng'iroq) yoki oktabr rejasiga (`rejalar/2026-10.csv`)
     bog'lansin;
   - Metasell misol qo'ng'iroqlarini dalil sifatida ko'rsat.
5. Natijani `rejalar/vazifalar_2026-10.csv` ga yoz. Ustunlar:
   `Operator,Muammo (Metasell),Dalil,Vazifa,Maqsad (o'lchov),Mas'ul,Muddat,Bog'liq KPI`
6. Jamoa bo'yicha umumiy xulosani ham yoz: eng ko'p takrorlanadigan 3 ta xato
   va jamoaviy trening mavzusi. Keyin commit qilib, branchga push qil.
