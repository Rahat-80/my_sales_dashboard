import sqlite3
db = sqlite3.connect("sales.db")
q = "SELECT report_date, COUNT(*), SUM(qty_sold), ROUND(SUM(val_sold), 2) FROM daily_sales GROUP BY report_date ORDER BY report_date"
for r in db.execute(q):
    print(r)