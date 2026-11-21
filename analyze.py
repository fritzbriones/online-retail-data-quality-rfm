"""Week 1 EDA: charts on the CLEANED Online Retail data.

Run src/clean.py first (writes data/retail_clean.csv).
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"
plt.rcParams.update({"figure.dpi": 150, "axes.grid": True, "grid.alpha": 0.3})

df = pd.read_csv(DATA / "retail_clean.csv",
                 parse_dates=["InvoiceDate"],
                 dtype={"CustomerID": "Int64", "InvoiceNo": str, "StockCode": str})
sales = df[~df.is_cancellation & ~df.is_adjustment].copy()

# --- 1. Monthly revenue trend (+ cancellations) ---
monthly = df.groupby(df.InvoiceDate.dt.to_period("M")).Revenue.sum() / 1e6
cancel = df[df.is_cancellation].groupby(df[df.is_cancellation].InvoiceDate.dt.to_period("M")).Revenue.sum() / 1e6
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(monthly.index.to_timestamp(), monthly, color="#264653", marker=".", label="Net revenue ($M)")
ax.bar(cancel.index.to_timestamp(), cancel.abs(), color="#e76f51", alpha=0.5, label="Cancelled value ($M)")
ax.set_title("Monthly net revenue grows; cancellation value follows sales")
ax.set_ylabel("$ millions"); ax.legend(); ax.set_xlabel("Month")
fig.tight_layout(); fig.savefig(OUT / "1_monthly_revenue.png"); fig.savefig(OUT / "1_monthly_revenue.svg"); plt.close(fig)

# --- 2. Top 10 products by revenue ---
top_prod = (sales.groupby("Description").Revenue.sum().nlargest(10)).iloc[::-1] / 1e3
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.barh(top_prod.index.str.slice(0, 42), top_prod.values, color="#2a9d8f")
ax.set_title("Top 10 products by revenue (clean data, 2010-12 to 2011-12)")
ax.set_xlabel("Revenue ($ thousands)")
fig.tight_layout(); fig.savefig(OUT / "2_top_products.png"); fig.savefig(OUT / "2_top_products.svg"); plt.close(fig)

# --- 3. Revenue by country (log scale, UK dominates 91%) ---
by_country = sales.groupby("Country").Revenue.sum().sort_values(ascending=False).head(10) / 1e6
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(by_country.index, by_country.values, log=True, color="#e9c46a")
ax.set_title("Revenue by country, log scale: UK dominates (85%), Netherlands #2")
ax.set_ylabel("$ millions (log)"); ax.tick_params(axis="x", rotation=30)
fig.tight_layout(); fig.savefig(OUT / "3_revenue_by_country.png"); fig.savefig(OUT / "3_revenue_by_country.svg"); plt.close(fig)

# --- 4. What cleaning changed: raw vs clean monthly revenue ---
raw = pd.read_excel(DATA / "Online Retail.xlsx")
raw_rev = raw.assign(Revenue=raw.Quantity * raw.UnitPrice).groupby(raw.InvoiceDate.dt.to_period("M")).Revenue.sum() / 1e6
clean_rev = df.groupby(df.InvoiceDate.dt.to_period("M")).Revenue.sum() / 1e6
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(raw_rev.index.to_timestamp(), raw_rev.values, "--", color="#e76f51", label="Raw data (with duplicates & fees)")
ax.plot(clean_rev.index.to_timestamp(), clean_rev.values, color="#264653", label="Cleaned data")
ax.set_title("Effect of cleaning: raw vs cleaned monthly net revenue"); ax.set_ylabel("$ millions")
ax.legend(); ax.set_xlabel("Month")
fig.tight_layout(); fig.savefig(OUT / "4_raw_vs_clean.png"); fig.savefig(OUT / "4_raw_vs_clean.svg"); plt.close(fig)

for name, tbl in [("top_products", top_prod), ("by_country", by_country)]:
    tbl.to_frame("value").to_csv(OUT / f"{name}.csv")

kpi = {"net_revenue_musd": round(df.Revenue.sum() / 1e6, 2),
       "uk_share_pct": round(sales[sales.Country == "United Kingdom"].Revenue.sum() / sales.Revenue.sum() * 100, 1),
       "orders": int(df.InvoiceNo.nunique()),
       "revenue_per_order": round(df.Revenue.sum() / df.InvoiceNo.nunique(), 1)}
import json as _json
(OUT / "eda_kpi.json").write_text(_json.dumps({"kpi": kpi}, indent=2))
print("Charts written:", [p.name for p in OUT.glob("*.png")])
print("KPIs:", kpi)
