# TransformingEmme

Turns the EMME `.in` demand matrices of the Tel Aviv model (v4.33) into plain
CSV matrices whose rows and columns are the `TAZV41` zones of `TAZ_v41.shp`.

Three scenarios — 2018, 2050_BU and 2050_SP — with nine matrices each: total
auto trips, Park & Ride + Kiss & Ride demand, and total transit trips, for the
AM, off-peak and PM periods.

**The CSV files are already built and committed**, under
`TLV_Model_v433/Matrices/<scenario>/CSV/`.

👉 **[TLV_Model_v433/Matrices/README.md](TLV_Model_v433/Matrices/README.md)**
explains the file layout, how to run the conversion and the checks
step by step, and what the QA output means.

```bash
pip install numpy                          # once
python3 scripts/convert_emme_to_csv.py     # build the CSVs   (~45 s)
python3 scripts/validate_matrices.py       # check them       (~50 s)
```
