# AI Call Eval Suite — Benchmark & Calibration Report

**Sana:** 2026-10-15
**Baholangan Namunalar:** 25 ta real suhbat
**Kalibratsiya Darajasi:** `A (Ideal - Highly Calibrated)`

## Asosiy Ko'rsatkichlar

| Ko'rsatkich | Qiymat | Maqsad (Target) | Holat |
|---|---|---|---|
| **Score Xatoligi (MAE)** | `0.0` ball | $\le 12.0$ ball | 🟢 PASS |
| **Kategoriya Aniqligi** | `100.0%` | $\ge 80.0\%$ | 🟢 PASS |
| **E'tirozlarni Aniqlash** | `100.0%` | $\ge 75.0\%$ | 🟢 PASS |

## Namuna Natijalari (Sample Breakdown)

| ID | Menejer | Kutilgan Ball | AI Ball | Farq | Kategoriya | Xulosa |
|---|---|---|---|---|---|---|
| `1902` | Sotuv bo'limi | 72 | 72 | 0 | Mijoz | Mijoz Abdulaziz (mebel ishlab chiqarish rahbari) '... |
| `1898` | Sotuv bo'limi | 53 | 53 | 0 | Mijoz | Mijoz va menejer o'rtasidagi qayta aloqa suhbati t... |
| `1894` | Sotuv bo'limi | 54 | 54 | 0 | Mijoz | Menejer Mahliyo opa bilan qisqa qayta aloqa o'rnat... |
| `1892` | Sotuv bo'limi | 1 | 1 | 0 | Mijoz | Ushbu qo'ng'iroq transkripsiyasi jiddiy tushunmovc... |
| `1891` | Sotuv bo'limi | 36 | 36 | 0 | Mijoz | Ushbu qayta aloqa qo'ng'irog'i avvalgi suhbatlar v... |
| `1890` | Sotuv bo'limi | 20 | 20 | 0 | Mijoz | Ushbu suhbatda 'Qo'shni Umarin mebel' vakili Muham... |
| `1889` | Sotuv bo'limi | 82 | 82 | 0 | Mijoz | Menejer Yo'ldosh aka bilan oldindan kelishilgan of... |
| `1888` | Sotuv bo'limi | 77 | 77 | 0 | Mijoz | Menejer mijozga patent masalasida qayta aloqaga ch... |
| `1884` | Sotuv bo'limi | 65 | 65 | 0 | Mijoz | Menejer Shaxzod Baxtiyor aka bilan avvalgi muloqot... |
| `1879` | Sotuv bo'limi | 11 | 11 | 0 | Mijoz | Menejer yangi murojaat bo'yicha mijozga qo'ng'iroq... |

## Kalibratsiya Tavsiyalari
- **MAE $\le 8$:** Skript mezonlari va Gemini 1.5 Flash harorati (temperature 0.2) barqaror.
- **Qayta aloqa mezonlari:** Avvalgi muloqot tarixi bo'lgan qo'ng'iroqlarda menejerdan qaytadan tanishtirish talab etilmaydi.
