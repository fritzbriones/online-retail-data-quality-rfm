"""EDA charts on the CLEANED Online Retail data (run clean.py first).

Every revenue figure is NET of cancellations (GBP). December 2011 is excluded
from the monthly trend because the data stops on 9 Dec 2011.
"""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DARK, ACCENT, GREY, LIGHT = "#264653", "#e76f51", "#8d99ae", "#cfd8dc"
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlelocation": "left", "axes.titleweight": "bold", "font.size": 10})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(ROOT / f"{name}.png")
    plt.close(fig)


df = pd.read_csv(DATA / "retail_clean.csv", parse_dates=["InvoiceDate"],
                 dtype={"CustomerID": "Int64", "InvoiceNo": str, "StockCode": str})
report = json.loads((ROOT / "cleaning_report.json").read_text())
sales = df[~df.is_cancellation]

# ---------- 1. Monthly net revenue + cancellation rate (full months only) ----------
full = df[df.InvoiceDate < "2011-12-01"]
m = full.groupby(full.InvoiceDate.dt.to_period("M")).agg(
    net=("Revenue", "sum"),
    gross=("Revenue", lambda r: r[r > 0].sum()),
    canc=("Revenue", lambda r: -r[r < 0].sum()))
m["canc_rate"] = m.canc / m.gross * 100
labels = m.index.strftime("%b\n%y")
peak = m.net.idxmax()
spring = m.loc["2011-02":"2011-04", "net"].mean()
q4_share = m.loc["2011-09":"2011-11", "net"].sum() / m.net.sum() * 100

fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
cols = [ACCENT if p >= pd.Period("2011-09", "M") else DARK for p in m.index]
a1.bar(labels, m.net / 1e3, color=cols)
a1.set_ylabel("Net revenue (£K)")
a1.set_title(f"Sep–Nov 2011 brought {q4_share:.0f}% of the year's net revenue; "
             f"{peak.strftime('%b')} peak was {m.net.max() / spring:.1f}x the Feb–Apr average")
a2.plot(labels, m.canc_rate, "o-", color=GREY)
a2.set_ylabel("Cancelled\n(% of gross)")
a2.set_ylim(0, max(10, m.canc_rate.max() * 1.2))
a2.text(0.99, 0.85, "Dec 2011 excluded (data ends 9 Dec)", transform=a2.transAxes,
        ha="right", fontsize=8, color=GREY)
save(fig, "1_monthly_revenue")

# ---------- 2. Top 10 products by NET revenue ----------
prod_net = df.groupby("Description").Revenue.sum()
prod_gross = sales.groupby("Description").Revenue.sum()
top = prod_net.nlargest(10).iloc[::-1] / 1e3
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.barh(top.index, top.values, color=DARK)
for y, v in enumerate(top.values):
    ax.text(v + 1, y, f"£{v:,.0f}K", va="center", fontsize=8)
ax.set_xlabel("Net revenue (£ thousands, after cancellations)")
ax.set_title("Top 10 products by net revenue (after cancellations)")
gross_only = prod_gross.nlargest(10).index.difference(prod_net.nlargest(10).index)
if len(gross_only):
    ax.text(0.99, 0.02, "Not shown: " + "; ".join(s.title() for s in gross_only)
            + "\n(huge orders cancelled the same day: gross ranks them top 10, net does not)",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=GREY)
save(fig, "2_top_products")

# ---------- 3. Country share of net revenue ----------
ctry = df.groupby("Country").Revenue.sum().sort_values(ascending=False)
share = ctry / ctry.sum() * 100
top9 = share.head(9)
plot = pd.concat([top9, pd.Series({f"Other {len(share) - 9} countries": share.iloc[9:].sum()})]).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.barh(plot.index, plot.values, color=[ACCENT if i == "United Kingdom" else DARK for i in plot.index])
for y, v in enumerate(plot.values):
    ax.text(v + 0.5, y, f"{v:.1f}%", va="center", fontsize=8)
ax.xaxis.set_major_formatter(mtick.PercentFormatter())
ax.set_xlabel("Share of net revenue")
ax.set_title(f"UK = {share['United Kingdom']:.0f}% of revenue; all exports combined = "
             f"{100 - share['United Kingdom']:.0f}% across {len(share) - 1} countries")
save(fig, "3_revenue_by_country")

# ---------- 4. Cleaning audit: what was wrong, what we did ----------
log = report["cleaning_log"]
raw_rows = report["raw_rows"]
issues = pd.DataFrame([
    ("Missing CustomerID", log["7_keep_missing_customer_id"]["rows_missing_customer_id"], "Kept (NA)"),
    ("Cancellation lines", log["2_flag_cancellations"]["cancellation_lines_flagged"], "Kept + flagged"),
    ("Exact duplicates", log["1_dedupe_exact"]["exact_duplicates_removed"], "Dropped"),
    ("Non-product codes (POST, fees...)", log["5_drop_nonproduct_codes"]["removed"], "Dropped"),
    ("Zero-price lines (write-offs)", log["4_drop_nonpositive_price"]["removed"], "Dropped"),
], columns=["issue", "rows", "action"]).iloc[::-1]
colors = {"Dropped": ACCENT, "Kept + flagged": GREY, "Kept (NA)": DARK}
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.barh(issues.issue, issues.rows, color=[colors[a] for a in issues.action], log=True)
for y, (r, a) in enumerate(zip(issues.rows, issues.action)):
    ax.text(r * 1.1, y, f"{r:,} ({r / raw_rows * 100:.1f}%) - {a}", va="center", fontsize=8)
ax.set_xlim(1e3, 2e6)
ax.set_xlabel("Rows affected (log scale; % = share of 541,909 raw rows)")
dropped = raw_rows - report["clean_rows"]
ax.set_title(f"Only {dropped:,} rows ({dropped / raw_rows * 100:.1f}%) were deleted;\n"
             "the biggest issues were kept and handled, not dropped")
save(fig, "4_cleaning_audit")

kpi = {
    "currency": "GBP",
    "net_revenue_gbp_m": round(df.Revenue.sum() / 1e6, 2),
    "uk_share_of_net_revenue_pct": round(float(share["United Kingdom"]), 1),
    "sep_nov_share_of_full_months_pct": round(float(q4_share), 1),
    "peak_month": str(peak),
    "peak_vs_feb_apr_avg": round(float(m.net.max() / spring), 2),
    "avg_cancellation_rate_pct": round(float(m.canc.sum() / m.gross.sum() * 100), 2),
    "top_product_net": prod_net.idxmax(),
    "gross_top10_but_cancelled": list(gross_only),
}
(ROOT / "eda_kpi.json").write_text(json.dumps(kpi, indent=2))
top.iloc[::-1].mul(1e3).round(2).to_frame("net_revenue_gbp").to_csv(ROOT / "top_products.csv")
pd.DataFrame({"net_revenue_gbp": ctry.round(2), "share_pct": share.round(2)}).to_csv(ROOT / "by_country.csv")
m.round(2).to_csv(ROOT / "monthly.csv")
print(json.dumps(kpi, indent=2))
