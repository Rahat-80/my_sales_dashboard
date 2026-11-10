import re
import sqlite3
from datetime import datetime
import pdfplumber

# ---------- সেটিংস (এখানে বদলালেই হবে) ----------
RSM_NAME = "DHAKA-1"         # তোমার RSM কোড
MY_GROUP = "HORMON"          # মূল গ্রুপ
EXTRA_CODES = ["081849"]     # অন্য গ্রুপে থাকা বাড়তি প্রোডাক্ট (Fezotan 45 Tab 1x10s)
DB_FILE = "sales.db"
# --------------------------------------------------

ROW = re.compile(r"^(\d{6})\s+([A-Za-z].*?)\s+((?:-?[\d,]+(?:\.\d+)?\s*){14})$")
DATE = re.compile(r"Period From\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+to\s+(\d{2}-[A-Za-z]{3}-\d{2})")


def to_iso(text):
    return datetime.strptime(text, "%d-%b-%y").strftime("%Y-%m-%d")


def read_pdf(file):
    """PDF পড়ে (রিপোর্টের তারিখ, সারির তালিকা) ফেরত দেয়।"""
    found = {}
    report_date = None
    period_start = None
    group = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if report_date is None:
                d = DATE.search(text)
                if d:
                    period_start = to_iso(d.group(1))   # রিপোর্ট কবে থেকে শুরু
                    report_date = to_iso(d.group(2))    # রিপোর্ট কবে পর্যন্ত
            if report_date is None or RSM_NAME not in text:
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
                found[code] = (report_date, code, m.group(2), kind, *nums, period_start)

    if report_date is None:
        return None, []
    return report_date, list(found.values())


def init_db():
    db = sqlite3.connect(DB_FILE)
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
            period_start TEXT,
            PRIMARY KEY (report_date, code)
        )
    """)
    # পুরনো ডাটাবেসে period_start কলাম না থাকলে যোগ করা
    cols = [r[1] for r in db.execute("PRAGMA table_info(daily_sales)")]
    if "period_start" not in cols:
        db.execute("ALTER TABLE daily_sales ADD COLUMN period_start TEXT")
    db.commit()
    db.close()


def save_rows(rows):
    init_db()
    db = sqlite3.connect(DB_FILE)
    db.executemany("INSERT OR REPLACE INTO daily_sales VALUES (" + ",".join(["?"] * 19) + ")", rows)
    db.commit()
    db.close()