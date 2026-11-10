import sqlite3
db = sqlite3.connect("sales.db")
full = {r[0]: r[1] for r in db.execute("SELECT code, name FROM daily_sales WHERE report_date = '2026-11-05'")}
for d in ["2026-11-03", "2026-11-04"]:
    have = {r[0] for r in db.execute("SELECT code FROM daily_sales WHERE report_date = ?", (d,))}
    print(d, "নেই:", [full[c] for c in full if c not in have])