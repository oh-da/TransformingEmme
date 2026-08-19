# EMME `.in` -> CSV conversion: validation report

Zone system: `TAZ_v41.shp` / `TAZV41` -- **1310 zones** (1101..8451), used as both the CSV index and the CSV header.

Scenarios: 2018, 2050_BU, 2050_HS

## Test summary

| test group | checks | failures |
|---|---:|---:|
| zone index | 27 | 0 |
| raw total | 27 | 0 |
| reconciliation | 27 | 0 |
| round-trip | 81 | 0 |
| row/col sums | 27 | 0 |
| sanity | 27 | 0 |
| comparison | 18 | 0 |

**234 checks, 0 failures.**

## Trips per matrix (inside the TAZ_v41 zone system)

| scenario | matrix | AM | Offpeak | PM | daily (a+o+p) |
|---|---|---:|---:|---:|---:|
| 2018 | AUTOTOT | 493,917 | 269,770 | 434,239 | 1,197,926 |
| 2018 | PRKRTotDemand | 10,405 | 2,357 | 684 | 13,446 |
| 2018 | TransitTotDemand | 95,179 | 60,410 | 72,016 | 227,605 |
| 2050_BU | AUTOTOT | 572,469 | 337,426 | 529,048 | 1,438,943 |
| 2050_BU | PRKRTotDemand | 34,608 | 11,597 | 3,939 | 50,144 |
| 2050_BU | TransitTotDemand | 291,570 | 157,365 | 189,616 | 638,552 |
| 2050_HS | AUTOTOT | 578,659 | 340,301 | 536,320 | 1,455,281 |
| 2050_HS | PRKRTotDemand | 35,307 | 11,508 | 3,995 | 50,810 |
| 2050_HS | TransitTotDemand | 299,939 | 159,847 | 194,311 | 654,097 |

## Mode shares (daily, inside the TAZ layer)

| scenario | AUTOTOT | PRKRTotDemand | TransitTotDemand | total |
|---|---|---|---|---|
| 2018 | 1,197,926 (83.2%) | 13,446 (0.9%) | 227,605 (15.8%) | 1,438,977 |
| 2050_BU | 1,438,943 (67.6%) | 50,144 (2.4%) | 638,552 (30.0%) | 2,127,639 |
| 2050_HS | 1,455,281 (67.4%) | 50,810 (2.4%) | 654,097 (30.3%) | 2,160,187 |

## Growth vs 2018 (daily totals inside the TAZ layer)

| matrix | 2018 | 2050_BU | 2050_HS |
|---|---|---|---|
| Auto total trips | 1,197,926 (x1.00) | 1,438,943 (x1.20) | 1,455,281 (x1.21) |
| Park & Ride + Kiss & Ride total demand | 13,446 (x1.00) | 50,144 (x3.73) | 50,810 (x3.78) |
| Transit total trips | 227,605 (x1.00) | 638,552 (x2.81) | 654,097 (x2.87) |

## Trips outside the TAZ_v41 zone system

The `.in` files also carry zones that do not exist in `TAZ_v41` -- external/cordon zones (ids below 1000) and the P&R / K&R station zones (ids 9xxx). Those rows and columns cannot be placed in a `TAZV41`-indexed matrix, so they are excluded from the CSVs and reported here instead; `CSV total + off-TAZ total` always equals the `.in` total (test group *reconciliation*).

| scenario | matrix | period | .in total | CSV total | off-TAZ | % kept |
|---|---|---|---:|---:|---:|---:|
| 2018 | AUTOTOT | AM | 556,994.6 | 493,916.5 | 63,078.1 | 88.68% |
| 2018 | AUTOTOT | Offpeak | 312,647.6 | 269,770.2 | 42,877.4 | 86.29% |
| 2018 | AUTOTOT | PM | 482,670.5 | 434,238.9 | 48,431.6 | 89.97% |
| 2018 | PRKRTotDemand | AM | 12,082.9 | 10,405.4 | 1,677.5 | 86.12% |
| 2018 | PRKRTotDemand | Offpeak | 2,357.2 | 2,357.2 | 0.0 | 100.00% |
| 2018 | PRKRTotDemand | PM | 683.9 | 683.9 | 0.0 | 100.00% |
| 2018 | TransitTotDemand | AM | 116,740.6 | 95,179.1 | 21,561.5 | 81.53% |
| 2018 | TransitTotDemand | Offpeak | 71,793.6 | 60,410.2 | 11,383.4 | 84.14% |
| 2018 | TransitTotDemand | PM | 87,507.0 | 72,015.5 | 15,491.5 | 82.30% |
| 2050_BU | AUTOTOT | AM | 718,378.8 | 572,469.2 | 145,909.6 | 79.69% |
| 2050_BU | AUTOTOT | Offpeak | 433,653.5 | 337,425.6 | 96,227.9 | 77.81% |
| 2050_BU | AUTOTOT | PM | 637,896.7 | 529,048.3 | 108,848.4 | 82.94% |
| 2050_BU | PRKRTotDemand | AM | 41,320.2 | 34,608.2 | 6,712.0 | 83.76% |
| 2050_BU | PRKRTotDemand | Offpeak | 11,596.6 | 11,596.6 | 0.0 | 100.00% |
| 2050_BU | PRKRTotDemand | PM | 3,939.3 | 3,939.3 | 0.0 | 100.00% |
| 2050_BU | TransitTotDemand | AM | 392,254.5 | 291,570.3 | 100,684.2 | 74.33% |
| 2050_BU | TransitTotDemand | Offpeak | 200,088.0 | 157,365.3 | 42,722.7 | 78.65% |
| 2050_BU | TransitTotDemand | PM | 251,884.9 | 189,616.0 | 62,269.0 | 75.28% |
| 2050_HS | AUTOTOT | AM | 726,172.1 | 578,658.8 | 147,513.3 | 79.69% |
| 2050_HS | AUTOTOT | Offpeak | 443,529.9 | 340,301.4 | 103,228.5 | 76.73% |
| 2050_HS | AUTOTOT | PM | 647,805.5 | 536,320.3 | 111,485.2 | 82.79% |
| 2050_HS | PRKRTotDemand | AM | 40,825.4 | 35,306.6 | 5,518.8 | 86.48% |
| 2050_HS | PRKRTotDemand | Offpeak | 11,508.1 | 11,508.1 | 0.0 | 100.00% |
| 2050_HS | PRKRTotDemand | PM | 3,995.2 | 3,995.2 | 0.0 | 100.00% |
| 2050_HS | TransitTotDemand | AM | 410,393.2 | 299,938.7 | 110,454.5 | 73.09% |
| 2050_HS | TransitTotDemand | Offpeak | 211,989.4 | 159,847.2 | 52,142.1 | 75.40% |
| 2050_HS | TransitTotDemand | PM | 257,115.5 | 194,310.7 | 62,804.8 | 75.57% |
