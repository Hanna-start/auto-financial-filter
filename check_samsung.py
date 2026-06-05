import os
import glob
import pandas as pd

excel_files = glob.glob('재무건전성_필터링_결과_*.xlsx')
latest = max(excel_files, key=os.path.getctime)
print(f"Reading {latest}")

xls = pd.ExcelFile(latest)
print(f"Sheets: {xls.sheet_names}")

# Let's check where 005930 is
symbol = '005930'
name = 'Samsung Electronics'

for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    if 'Code' in df.columns:
        # Code might be int or string
        df['Code'] = df['Code'].astype(str).str.zfill(6)
        match = df[df['Code'] == symbol]
        if not match.empty:
            print(f"\n--- Found in {sheet} ---")
            for _, row in match.iterrows():
                print(row.to_dict())
