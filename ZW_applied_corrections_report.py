#!/usr/bin/env python3
"""Generate an audit CSV of changes between the original validation report and the applied workbook.

Writes: output/applied_corrections_audit.csv
Columns: excel_row, df_index, column, old_value, new_value
"""
from pathlib import Path
import pandas as pd

report = Path("output") / "CLFS_contextually_wrong_answers_validation_report.xlsx"
applied = Path("output") / "CLFS_contextually_wrong_answers_validation_applied.xlsx"
out_csv = Path("output") / "applied_corrections_audit.csv"

if not report.exists():
    raise SystemExit(f"Report not found: {report}")
if not applied.exists():
    raise SystemExit(f"Applied workbook not found: {applied}")

# Read Complete Dataset sheets as object dtype to preserve values
orig = pd.read_excel(report, sheet_name='Complete Dataset', dtype=object)
new = pd.read_excel(applied, sheet_name='Complete Dataset', dtype=object)

# Align columns: use intersection to avoid reporting unrelated columns
cols = list(sorted(set(orig.columns).union(set(new.columns)), key=lambda x: str(x)))

max_rows = max(len(orig), len(new))

changes = []
for i in range(max_rows):
    for col in cols:
        try:
            old = orig.at[i, col] if col in orig.columns and i in orig.index else None
        except Exception:
            old = None
        try:
            cur = new.at[i, col] if col in new.columns and i in new.index else None
        except Exception:
            cur = None
        # Normalize NaN -> None for comparison
        if pd.isna(old):
            old_val = None
        else:
            old_val = old
        if pd.isna(cur):
            new_val = None
        else:
            new_val = cur
        if (old_val is None and new_val is None):
            continue
        # Compare string representations to capture e.g., int vs '1'
        if (None if old_val is None else str(old_val)) != (None if new_val is None else str(new_val)):
            changes.append({
                'excel_row': i + 2,  # header row is 1
                'df_index': i,
                'column': col,
                'old_value': old_val,
                'new_value': new_val,
            })

out_csv.parent.mkdir(parents=True, exist_ok=True)
if changes:
    audit_df = pd.DataFrame(changes)
    audit_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
    print(f"Wrote audit CSV with {len(changes)} changes to: {out_csv}")
else:
    # write empty csv with headers
    pd.DataFrame(columns=['excel_row','df_index','column','old_value','new_value']).to_csv(out_csv, index=False, encoding='utf-8-sig')
    print("No differences found between sheets. Wrote empty audit CSV to:", out_csv)

print("Done.")
