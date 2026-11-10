import math
import sqlite3
import pandas as pd
import streamlit as st
from reader import read_pdf, save_rows, init_db, DB_FILE, EXTRA_CODES
from report import make_pdf
from settings import TARGET_SHARE, PRODUCTS, GROUPS

# ---------- সেটিংস: কোন কলামের দৈনিক হিসাব চাই ----------
# আরও কলাম চাইলে এখানে নাম যোগ করো, যেমন "cur_total": "Cur Total"
DAILY = {"sold": "Sold", "total": "Total"}

# যে বারে PDF আসে না (০=সোম, ১=মঙ্গল, ২=বুধ, ৩=বৃহস্পতি, ৪=শুক্র, ৫=শনি, ৬=রবি)
HOLIDAY_WEEKDAYS = [4]
# --------------------------------------------------------

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("Sales Dashboard")

init_db()

# ১) PDF আপলোড
uploaded = st.file_uploader("PDF রিপোর্ট দাও", type="pdf")
if uploaded is not None:
    report_date, rows = read_pdf(uploaded)
    if not rows:
        st.error("এই PDF-এ তোমার ডাটা পাওয়া যায়নি। সঠিক রিপোর্ট দিয়েছ তো?")
    else:
        save_rows(rows)
        st.success(f"{report_date} তারিখের {len(rows)}টি প্রোডাক্ট সেভ হয়েছে")

# ২) ডাটাবেস থেকে সব ডাটা পড়া
db = sqlite3.connect(DB_FILE)
df = pd.read_sql("SELECT * FROM daily_sales", db)
db.close()

if df.empty:
    st.info("এখনো কোনো ডাটা নেই। উপরে PDF আপলোড করো।")
    st.stop()

# ৩) সময়কাল (period) ঠিক করা: রিপোর্ট কবে থেকে শুরু। ফাঁকা থাকলে মাসের ১ তারিখ ধরা
df = df.sort_values(["code", "report_date"]).reset_index(drop=True)
df["period"] = df["period_start"].fillna(df["report_date"].str[:7] + "-01")

# যেদিন কোনো প্রোডাক্ট PDF-এ ছিল না (সব সংখ্যা ০ হলে সারি বাদ যায়), সেদিন তার সব সংখ্যা ০ ধরা
num_cols = [c for c in df.columns if c.startswith(("qty_", "val_"))]
info = df.drop_duplicates("code").set_index("code")[["name", "kind"]]
parts = []
for period, g in df.groupby("period"):
    full = pd.MultiIndex.from_product(
        [sorted(g["code"].unique()), sorted(g["report_date"].unique())], names=["code", "report_date"])
    g = g.set_index(["code", "report_date"]).reindex(full).reset_index()
    g[num_cols] = g[num_cols].fillna(0)
    g["name"] = g["code"].map(info["name"])
    g["kind"] = g["code"].map(info["kind"])
    g["period"] = period
    parts.append(g)
df = pd.concat(parts, ignore_index=True).sort_values(["code", "report_date"]).reset_index(drop=True)

# ৪) দৈনিক হিসাব: আগের কাজের দিনের PDF-এর সাথে বিয়োগ (একই সময়কালের হলে)
def back_to_workday(ts):
    """তারিখটা ছুটির বার হলে আগের কাজের দিনে ফিরে যায়"""
    while ts.weekday() in HOLIDAY_WEEKDAYS:
        ts = ts - pd.Timedelta(days=1)
    return ts

def prev_workday(ts):
    """আগের কাজের দিন (ছুটির বার বাদ)"""
    return back_to_workday(ts - pd.Timedelta(days=1))

df["report_ts"] = pd.to_datetime(df["report_date"])
df["prev_ts"] = df["report_ts"].map(prev_workday)
prev = df[["code", "report_ts", "period"] + num_cols].rename(columns={"report_ts": "prev_ts"})
df = df.merge(prev, on=["code", "prev_ts"], how="left", suffixes=("", "_prev"))
first_day = df["period"] == df["report_date"]        # সময়কালের প্রথম দিন: জমানো সংখ্যাই দৈনিক
same_period = df["period"] == df["period_prev"]
for key in DAILY:
    for pre in ("qty", "val"):
        col = f"{pre}_{key}"
        df["day_" + col] = df[col].where(first_day, (df[col] - df[col + "_prev"]).where(same_period))

# ৫) তারিখ বাছাই (নতুন তারিখ আগে)
all_dates = set(df["report_date"])
dates = sorted(all_dates, reverse=True)
selected = st.selectbox("রিপোর্টের তারিখ", dates)

# ৬) ওই তারিখের সারি: মূল তালিকা আগে, বাড়তি প্রোডাক্ট নিচে
day = df[df["report_date"] == selected].sort_values(["kind", "code"])

# ৭) দরকারি তারিখের PDF আছে কিনা
sel_ts = pd.Timestamp(selected)
prev_ts_sel = prev_workday(sel_ts)
prev_day = prev_ts_sel.strftime("%Y-%m-%d")
last_month_end = back_to_workday(sel_ts.replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
same_day_last_month = back_to_workday(sel_ts - pd.DateOffset(months=1)).strftime("%Y-%m-%d")

sel_period = day["period"].iloc[0]
if sel_period == selected:
    daily_state = "first"
elif prev_day not in all_dates:
    daily_state = "missing"
elif df.loc[df["report_date"] == prev_day, "period"].iloc[0] != sel_period:
    daily_state = "other_period"
else:
    daily_state = "ok"

MSG_PREV = f"পূর্ববর্তী দিনের ({prev_day}) PDF পাওয়া যায়নি।"
MSG_PERIOD = f"পূর্ববর্তী দিনের ({prev_day}) PDF-এর সময়কাল আলাদা, তাই বিয়োগ করা যাচ্ছে না।"
MSG_LM_END = f"গত মাসের শেষ দিনের ({last_month_end}) PDF পাওয়া যায়নি।"
MSG_LM_SAME = f"গত মাসের একই দিনের ({same_day_last_month}) PDF পাওয়া যায়নি।"
daily_msg = {"missing": MSG_PREV, "other_period": MSG_PERIOD}.get(daily_state)
has_lm_end = last_month_end in all_dates
has_lm_same = same_day_last_month in all_dates

# উপরে একসাথে সব সমস্যার বার্তা
problems = [daily_msg]
if not has_lm_end:
    problems.append(MSG_LM_END)
if not has_lm_same:
    problems.append(MSG_LM_SAME)
problems = [p for p in problems if p]

if problems:
    st.warning(f"**{selected} এর জন্য যা পাওয়া যায়নি:**\n\n" + "\n".join("- " + p for p in problems))

PARTS = ["target", "prev_cr", "cur_total", "total", "adv_cr", "sold", "intransit"]
HEADS = ["Target", "Prev. Cr", "Cur Total", "Total", "Adv. Cr", "Sold", "Intransit"]

def make_table(prefix):
    t = day[["code", "name"] + [f"{prefix}_{p}" for p in PARTS]].copy()
    t.columns = ["Code", "Product"] + HEADS
    sums = t[HEADS].sum()
    total_row = pd.DataFrame([["", "TOTAL"] + list(sums)], columns=t.columns)
    return pd.concat([t, total_row], ignore_index=True)

def show(prefix, fmt):
    config = {h: st.column_config.NumberColumn(h, format=fmt) for h in HEADS}
    st.dataframe(make_table(prefix), hide_index=True, column_config=config)

def date_matrix(col, fmt):
    """প্রোডাক্ট × তারিখ টেবিল (দৈনিক সংখ্যা)"""
    p = df.pivot_table(index=["kind", "code", "name"], columns="report_date", values=col)
    p = p.reset_index().drop(columns="kind")
    p.columns = ["Code", "Product"] + list(p.columns[2:])
    sums = p[list(p.columns[2:])].sum()
    total_row = pd.DataFrame([["", "TOTAL"] + list(sums)], columns=p.columns)
    p = pd.concat([p, total_row], ignore_index=True)
    config = {c: st.column_config.NumberColumn(c, format=fmt) for c in p.columns[2:]}
    st.dataframe(p, hide_index=True, column_config=config)

def make_daily_table():
    """দৈনিক টেবিল বানায়; আগের দিনের PDF না থাকলে None দেয়"""
    if daily_msg:
        return None
    cols, names = [], []
    for key, label in DAILY.items():
        cols += ["day_qty_" + key, "day_val_" + key]
        names += [f"{label} (পরিমাণ)", f"{label} (টাকা)"]
    t = day[["code", "name"] + cols].copy()
    t.columns = ["Code", "Product"] + names
    total_row = pd.DataFrame([["", "TOTAL"] + list(t[names].sum())], columns=t.columns)
    return pd.concat([t, total_row], ignore_index=True)

# ---------- প্রিন্টের জন্য PDF ----------
daily_table = make_daily_table()
pdf_note = {"missing": f"previous day's PDF ({prev_day}) not found.",
            "other_period": f"previous day's PDF ({prev_day}) covers a different period, cannot subtract."}.get(daily_state)
pdf_bytes = make_pdf(selected, make_table("qty"), make_table("val"), daily_table,
                     prev_day if daily_state == "ok" else selected, EXTRA_CODES, pdf_note)
st.download_button(
    "প্রিন্টের জন্য PDF ডাউনলোড",
    data=pdf_bytes,
    file_name=f"sales_report_{selected}.pdf",
    mime="application/pdf",
)

tab1, tab2, tab3, tab4 = st.tabs(["জমানো রিপোর্ট", "দৈনিক হিসাব", "তুলনা", "টার্গেট ও গ্রোথ"])

# ---------- ট্যাব ১: PDF-এর জমানো সংখ্যা ----------
with tab1:
    c1, c2 = st.columns(2)
    c1.metric("Sold (পরিমাণ)", f"{day['qty_sold'].sum():,.0f}")
    c2.metric("Sold (টাকা)", f"{day['val_sold'].sum():,.2f}")
    st.subheader("Quantity (পরিমাণ)")
    show("qty", "%d")
    st.subheader("Value (টাকা)")
    show("val", "%.2f")

# ---------- ট্যাব ২: দৈনিক হিসাব ----------
with tab2:
    if daily_msg:
        st.warning(daily_msg)
    else:
        if daily_state == "ok":
            extra = "" if (sel_ts - prev_ts_sel).days == 1 else " (মাঝের ছুটির দিন বাদ)"
            st.caption(f"{prev_day} এর পর থেকে {selected} পর্যন্ত{extra}")
        else:
            st.caption(f"{selected} এই সময়কালের প্রথম দিন, তাই জমানো সংখ্যাই দৈনিক সংখ্যা")

        # উপরে বড় সংখ্যা: প্রতিটা কলামের জন্য পরিমাণ ও টাকা
        for key, label in DAILY.items():
            c1, c2 = st.columns(2)
            c1.metric(f"দৈনিক {label} (পরিমাণ)", f"{day['day_qty_' + key].sum():,.0f}")
            c2.metric(f"দৈনিক {label} (টাকা)", f"{day['day_val_' + key].sum():,.2f}")

        # প্রোডাক্ট ধরে টেবিল
        names = [f"{label} ({unit})" for label in DAILY.values() for unit in ("পরিমাণ", "টাকা")]
        config = {n: st.column_config.NumberColumn(n, format="%d" if "পরিমাণ" in n else "%.2f") for n in names}
        st.dataframe(daily_table, hide_index=True, column_config=config)

        if (day["day_qty_" + list(DAILY)[0]] < 0).any():
            st.warning("কিছু প্রোডাক্টে দৈনিক সংখ্যা মাইনাস এসেছে। PDF-এর তারিখ বা সময়কাল ঠিক আছে কিনা দেখো।")

    # তারিখ-টেবিল: সব তারিখ একসাথে
    key = st.selectbox("তারিখ-টেবিলে কোন কলাম?", list(DAILY), format_func=lambda k: DAILY[k])
    label = DAILY[key]

    by_date = df.groupby("report_date")["day_qty_" + key].apply(lambda s: s.isna().all())
    no_daily = sorted(by_date[by_date].index)
    if no_daily:
        st.warning("এই তারিখগুলোর দৈনিক হিসাব নেই, কারণ পূর্ববর্তী দিনের PDF পাওয়া যায়নি (বা সময়কাল আলাদা): "
                   + ", ".join(no_daily))

    st.subheader(f"প্রোডাক্ট × তারিখ: {label} (পরিমাণ)")
    date_matrix("day_qty_" + key, "%d")
    st.subheader(f"প্রোডাক্ট × তারিখ: {label} (টাকা)")
    date_matrix("day_val_" + key, "%.2f")

# ---------- ট্যাব ৩: তুলনা ----------
with tab3:
    unit = st.radio("কী দেখবে?", ["পরিমাণ", "টাকা"], horizontal=True)
    pre, fmt = ("qty", "%d") if unit == "পরিমাণ" else ("val", "%.2f")
    cur = day.set_index("code")

    def snapshot(date_str):
        """ওই তারিখের PDF থেকে প্রতিটা প্রোডাক্টের সংখ্যা (প্রোডাক্ট না থাকলে ০)"""
        s = df[df["report_date"] == date_str].set_index("code").reindex(cur.index)
        return s[[f"{pre}_sold", f"{pre}_total"]].fillna(0)

    def compare_table(left_label, left, right_label, right):
        t = pd.DataFrame({"Code": cur.index, "Product": cur["name"].values,
                          left_label: left.values, right_label: right.values})
        total = pd.DataFrame([{"Code": "", "Product": "TOTAL",
                               left_label: t[left_label].sum(), right_label: t[right_label].sum()}])
        t = pd.concat([t, total], ignore_index=True)
        t["পার্থক্য"] = t[right_label] - t[left_label]
        config = {c: st.column_config.NumberColumn(format=fmt) for c in (left_label, right_label, "পার্থক্য")}
        st.dataframe(t, hide_index=True, column_config=config)

    st.caption("PDF-এর সংখ্যা মাসের শুরু থেকে জমানো। কোনো তারিখ ছুটির বারে (শুক্রবার) পড়লে আগের কাজের দিন ধরা হয়, আর টেবিলের শিরোনামে আসল তারিখ লেখা থাকে।")

    st.subheader("১) গত মাসের শেষ দিনের Sold বনাম নির্বাচিত দিনের Total")
    if has_lm_end:
        compare_table(f"গত মাসের শেষ দিনের Sold ({last_month_end})", snapshot(last_month_end)[f"{pre}_sold"],
                      f"নির্বাচিত দিনের Total ({selected})", cur[f"{pre}_total"])
    else:
        st.warning(MSG_LM_END)

    st.subheader("২) গত মাসের একই দিনের Total বনাম এই মাসের একই দিনের Total")
    if has_lm_same:
        compare_table(f"গত মাসের Total ({same_day_last_month})", snapshot(same_day_last_month)[f"{pre}_total"],
                      f"এই মাসের Total ({selected})", cur[f"{pre}_total"])
    else:
        st.warning(MSG_LM_SAME)
# ---------- ট্যাব ৪: টার্গেট ও গ্রোথ ----------
CRORE = 10_000_000

def product_setting(code):
    """(TP, টার্গেট কোটি-এভারেজ, শেয়ার %) ফেরত দেয়"""
    tp, cr, share = PRODUCTS.get(code, (None, None, None))
    return tp, cr, (share if share is not None else TARGET_SHARE)

group_of = {code: name for name, codes in GROUPS.items() for code in codes}

def combine(frame):
    """কোড ধরে সারিগুলোকে প্রোডাক্ট ধরে মেলায়: GROUPS-এর কোডগুলো একটা সম্মিলিত সারি হয়ে যায়"""
    f = frame[["code", "name", "qty_sold", "qty_total"]].copy()
    f["pkey"] = f["code"].map(group_of).fillna(f["code"])
    f["pname"] = f["name"].where(~f["pkey"].isin(list(GROUPS)), f["pkey"])
    return f.groupby("pkey", sort=False).agg(
        name=("pname", "first"), qty_sold=("qty_sold", "sum"), qty_total=("qty_total", "sum"))

def need_boxes(value, tp):
    """কত টাকায় কয় বক্স লাগে (পুরো বক্সে ওপরের দিকে)"""
    return math.ceil(round(value / tp, 6))

with tab4:
    basis_label = st.radio("কোন সংখ্যা ধরবে?", ["Sold", "Total"], horizontal=True, key="t4_basis")
    basis = basis_label.lower()
    cur4 = combine(day)

    # --- ক) টার্গেট শেয়ার অনুযায়ী লক্ষ্য ---
    st.subheader(f"টার্গেট শেয়ার: {selected} পর্যন্ত (মাসের শুরু থেকে জমানো {basis_label})")
    rows4 = []
    for code, r in cur4.iterrows():
        tp, cr, share = product_setting(code)
        b = r["qty_" + basis]
        row = {"Code": "" if code in GROUPS else code, "Product": r["name"], "TP": tp, "শেয়ার (%)": share,
               "টার্গেট কোটি-এভারেজ": cr, "বিক্রি (বক্স)": b}
        if tp:
            row["বিক্রি (টাকা)"] = b * tp
        if tp and cr:
            target_value = share * cr * CRORE / 100
            target_boxes = need_boxes(target_value, tp)
            row["টার্গেট (টাকা)"] = target_value
            row["টার্গেট (বক্স)"] = target_boxes
            row["বাকি (বক্স)"] = max(0, target_boxes - b)
            row["রান করছে (কোটি)"] = b * tp / (share * CRORE / 100)
        rows4.append(row)
    t4 = pd.DataFrame(rows4)
    order = ["Code", "Product", "TP", "শেয়ার (%)", "টার্গেট কোটি-এভারেজ", "টার্গেট (বক্স)", "টার্গেট (টাকা)",
             "বিক্রি (বক্স)", "বিক্রি (টাকা)", "বাকি (বক্স)", "রান করছে (কোটি)"]
    t4 = t4.reindex(columns=order)
    sum_cols = ["টার্গেট (বক্স)", "টার্গেট (টাকা)", "বিক্রি (বক্স)", "বিক্রি (টাকা)", "বাকি (বক্স)"]
    total4 = {c: None for c in order}
    total4.update({"Code": "", "Product": "TOTAL"})
    for c in sum_cols:
        total4[c] = t4[c].sum()
    t4 = pd.concat([t4, pd.DataFrame([total4])], ignore_index=True)
    cfg4 = {"TP": st.column_config.NumberColumn(format="%d"),
            "শেয়ার (%)": st.column_config.NumberColumn(format="%.2f"),
            "টার্গেট কোটি-এভারেজ": st.column_config.NumberColumn(format="%.2f"),
            "টার্গেট (বক্স)": st.column_config.NumberColumn(format="%d"),
            "টার্গেট (টাকা)": st.column_config.NumberColumn(format="%.0f"),
            "বিক্রি (বক্স)": st.column_config.NumberColumn(format="%d"),
            "বিক্রি (টাকা)": st.column_config.NumberColumn(format="%.0f"),
            "বাকি (বক্স)": st.column_config.NumberColumn(format="%d"),
            "রান করছে (কোটি)": st.column_config.NumberColumn(format="%.3f")}
    st.dataframe(t4, hide_index=True, column_config=cfg4)
    st.caption("টার্গেট (টাকা) = শেয়ার% × কোটি-এভারেজ × ১ কোটি। টার্গেট (বক্স) = টার্গেট (টাকা) ÷ TP। "
               "রান করছে (কোটি) = বিক্রি (টাকা) ÷ (শেয়ার% × ১ কোটি)। যে প্রোডাক্টের TP বা কোটি-এভারেজ settings.py তে নেই, তার টার্গেট আসবে না, আর TOTAL-এর টার্গেট ও বাকি শুধু টার্গেট থাকা প্রোডাক্টের।")

    # --- খ) হিসাব মেশিন (দুই দিকেই) ---
    st.subheader("হিসাব মেশিন")
    names4 = {k: (r["name"] if k in GROUPS else f"{r['name']} ({k})") for k, r in cur4.iterrows()}
    pick = st.selectbox("প্রোডাক্ট", list(names4), format_func=lambda c: names4[c], key="t4_pick")
    tp, cr, share = product_setting(pick)
    if not tp:
        st.warning("এই প্রোডাক্টের TP settings.py তে দেওয়া নেই।")
    else:
        m1, m2 = st.columns(2)
        with m1:
            n = st.number_input("কত বক্স বিক্রি করেছ?", min_value=0, value=0, step=1, key="t4_boxes")
            st.write(f"ভ্যালু: **{n * tp:,.0f} টাকা**")
            st.write(f"কোটি-এভারেজ: **{n * tp / (share * CRORE / 100):.3f}**")
        with m2:
            c = st.number_input("কত কোটি এভারেজে বিক্রি করতে চাও?", min_value=0.0,
                                value=float(cr or 1), step=0.25, key="t4_cr")
            value_needed = share * c * CRORE / 100
            st.write(f"ভ্যালু: **{value_needed:,.0f} টাকা**")
            st.write(f"বক্স: **{need_boxes(value_needed, tp)}**")
        st.caption(f"শেয়ার {share}%, TP {tp}")

    # --- গ) গ্রোথ: গত মাসের তুলনায় এ মাস ---
    st.subheader("গ্রোথ: গত মাসের তুলনায় এ মাস")
    base_opt = st.radio("গত মাসের কোন দিনের সাথে?",
                        ["গত মাসের একই তারিখ", "গত মাসের শেষ দিন (পুরো মাস)"], key="t4_base")
    if base_opt == "গত মাসের একই তারিখ":
        base_date, has_base, msg_base = same_day_last_month, has_lm_same, MSG_LM_SAME
    else:
        base_date, has_base, msg_base = last_month_end, has_lm_end, MSG_LM_END
        st.caption("মাস শেষ না হওয়া পর্যন্ত এ মাসের সংখ্যা পুরো মাসের চেয়ে কম দেখাবে, তাই গ্রোথ মাইনাস আসা স্বাভাবিক।")

    if not has_base:
        st.warning(msg_base)
    else:
        last_boxes = combine(df[df["report_date"] == base_date])["qty_" + basis].reindex(cur4.index).fillna(0)
        g = pd.DataFrame({"Code": ["" if k in GROUPS else k for k in cur4.index], "Product": cur4["name"].values,
                          "TP": [product_setting(c)[0] for c in cur4.index],
                          "গত মাস (বক্স)": last_boxes.values, "এ মাস (বক্স)": cur4["qty_" + basis].values})
        g["গত মাস (টাকা)"] = g["গত মাস (বক্স)"] * g["TP"]
        g["এ মাস (টাকা)"] = g["এ মাস (বক্স)"] * g["TP"]

        def growth(now, last):
            return (now - last) / last * 100 if last and last > 0 else None

        g["গ্রোথ (%)"] = [growth(a, b) for a, b in zip(g["এ মাস (বক্স)"], g["গত মাস (বক্স)"])]
        g["ভ্যালু গ্রোথ (%)"] = [growth(a, b) for a, b in zip(g["এ মাস (টাকা)"], g["গত মাস (টাকা)"])]
        tl, tn = g["গত মাস (বক্স)"].sum(), g["এ মাস (বক্স)"].sum()
        vl, vn = g["গত মাস (টাকা)"].sum(), g["এ মাস (টাকা)"].sum()
        total_g = {"Code": "", "Product": "TOTAL", "TP": None, "গত মাস (বক্স)": tl, "এ মাস (বক্স)": tn,
                   "গত মাস (টাকা)": vl, "এ মাস (টাকা)": vn,
                   "গ্রোথ (%)": growth(tn, tl), "ভ্যালু গ্রোথ (%)": growth(vn, vl)}
        g = pd.concat([g, pd.DataFrame([total_g])], ignore_index=True)
        g = g[["Code", "Product", "TP", "গত মাস (বক্স)", "এ মাস (বক্স)", "গ্রোথ (%)",
               "গত মাস (টাকা)", "এ মাস (টাকা)", "ভ্যালু গ্রোথ (%)"]]
        st.caption(f"গত মাস = {base_date}, এ মাস = {selected}। টাকা = বক্স × TP। "
                   "TP দেওয়া নেই এমন প্রোডাক্ট টাকার হিসাবে ধরা হয়নি।")
        cfgg = {"TP": st.column_config.NumberColumn(format="%d"),
                "গত মাস (বক্স)": st.column_config.NumberColumn(format="%d"),
                "এ মাস (বক্স)": st.column_config.NumberColumn(format="%d"),
                "গ্রোথ (%)": st.column_config.NumberColumn(format="%.1f"),
                "গত মাস (টাকা)": st.column_config.NumberColumn(format="%.0f"),
                "এ মাস (টাকা)": st.column_config.NumberColumn(format="%.0f"),
                "ভ্যালু গ্রোথ (%)": st.column_config.NumberColumn(format="%.1f")}
        st.dataframe(g, hide_index=True, column_config=cfgg)