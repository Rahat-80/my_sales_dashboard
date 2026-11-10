import re
import sqlite3
from datetime import datetime
import pdfplumber

# ---------- সেটিংস (এখানে বদলালেই হবে) ----------
MY_GROUP = "HORMON"          # মূল গ্রুপ
EXTRA_CODES = ["081849"]     # অন্য গ্রুপে থাকা বাড়তি প্রোডাক্ট (Fezotan 45 Tab 1x10s)
# --------------------------------------------------

ROW = re.compile(r"^(\d{6})\s+([A-Za-z].*?)\s+((?:-?[\d,]+(?:\.\d+)?\s*){14})$")
DATE = re.compile(r"Period From .* to (\d{2}-[A-Za-z]{3}-\d{2})")

found = {}
report_date = None
group = ""

with pdfplumber.open("BSMMU.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if report_date is None:
            d = DATE.search(text)
            if d:
                report_date = datetime.strptime(d.group(1), "%d-%b-%y").strftime("%Y-%m-%d")
        if "DHAKA-1" not in text:
            continue
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Group "):
                group = line[6:].strip()
                continue
            m = ROW.match(line)
            if not m:
                continue
            code = m.group(1)
            if group == MY_GROUP:
                kind = 1
            elif code in EXTRA_CODES:
                kind = 2
            else:
                continue
            nums = [float(x.replace(",", "")) for x in m.group(3).split()]
            # ১৪টা সংখ্যাই রাখছি: প্রথম ৭টা Quantity, পরের ৭টা Value
            found[code] = (report_date, code, m.group(2), kind, *nums)

rows = list(found.values())

db = sqlite3.connect("sales.db")
db.execute("""
    CREATE TABLE IF NOT EXISTS daily_sales (
        report_date TEXT,
        code TEXT,
        name TEXT,
        kind INTEGER,
        qty_target REAL, qty_prev_cr REAL, qty_cur_total REAL, qty_total REAL,
        qty_adv_cr REAL, qty_sold REAL, qty_intransit REAL,
        val_target REAL, val_prev_cr REAL, val_cur_total REAL, val_total REAL,
        val_adv_cr REAL, val_sold REAL, val_intransit REAL,
        PRIMARY KEY (report_date, code)
    )
""")
db.executemany("INSERT OR REPLACE INTO daily_sales VALUES (" + ",".join(["?"] * 18) + ")", rows)
db.commit()

print("Report date:", report_date, "| Saved rows:", len(rows))
for r in db.execute("SELECT * FROM daily_sales WHERE report_date = ? ORDER BY kind, code", (report_date,)):
    print(r)
db.close()