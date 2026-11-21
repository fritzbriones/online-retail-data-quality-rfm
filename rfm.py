"""RFM customer segmentation on the CLEANED Online Retail data.

Recency, Frequency, Monetary scoring + segment naming (qualitative quadrants).
Run src/clean.py first. Outputs: CSV table, segmentation chart, segment KPIs.
"""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"

df = pd.read_csv(DATA / "retail_clean.csv", parse_dates=["InvoiceDate"],
                 dtype={"CustomerID": "Int64", "InvoiceNo": str})
sales = df[~df.is_cancellation & ~df.is_adjustment & df.CustomerID.notna()].copy()

SNAPSHOT = sales.InvoiceDate.max() + pd.Timedelta(days=1)   # day after last order

# ---------- RFM per customer ----------
rfm = sales.groupby("CustomerID").agg(
    last_purchase=("InvoiceDate", "max"),
    frequency=("InvoiceNo", "nunique"),
    monetary=("Revenue", "sum"),
    tenure=("InvoiceDate", "min"),
)
rfm["recency_days"] = (SNAPSHOT - rfm.last_purchase).dt.days

# ---------- Scores: 1-5, 5 = best ----------
rfm["R"] = pd.qcut(rfm.recency_days, 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F"] = pd.qcut(rfm.frequency.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M"] = pd.qcut(rfm.monetary, 5, labels=[1, 2, 3, 4, 5]).astype(int)

# ---------- Qualitative segments (standard RFM map) ----------
def segment(row):
    r, f, m = row.R, row.F, row.M
    if r >= 4 and f >= 4 and m >= 4: return "Champions"
    if r >= 3 and f >= 3 and m >= 3: return "Loyal customers"
    if 2 <= r <= 4 and f <= 2: return "Promising / new"
    if r <= 2 and f >= 3: return "At risk (was loyal)"
    if r <= 2 and f <= 2: return "Hibernating"
    return "Potential loyalists"
rfm["segment"] = rfm.apply(segment, axis=1)

# ---------- Pivot to segment KPIs ----------
seg = rfm.groupby("segment").agg(
    customers=("R", "size"),
    revenue=("monetary", "sum"),
    recency_median=("recency_days", "median"),
    frequency_median=("frequency", "median"),
).sort_values("revenue", ascending=False)
seg["revenue_share_%"] = (seg.revenue / seg.revenue.sum() * 100).round(1)
seg["customer_share_%"] = (seg.customers / seg.customers.sum() * 100).round(1)
seg.round(1).to_csv(OUT / "rfm_segments.csv")
rfm.reset_index().to_csv(OUT / "rfm_customers.csv", index=False)

# ---------- Chart: revenue vs customer share by segment ----------
fig, ax = plt.subplots(figsize=(10, 4.5))
x = seg.index
ax.bar(x, seg.revenue / 1e6, color="#264653", label="Revenue ($M)")
ax2 = ax.twinx()
ax2.plot(x, seg["customer_share_%"], "o-", color="#e76f51", label="Customers (%)")
ax.set_title("A small champion core drives a large revenue share")
ax.set_ylabel("Revenue ($M)"); ax2.set_ylabel("Share of customers (%)")
ax.tick_params(axis="x", rotation=20)
l1, lb1 = ax.get_legend_handles_labels(); l2, lb2 = ax2.get_legend_handles_labels()
ax.legend(l1 + l2, lb1 + lb2)
fig.tight_layout(); fig.savefig(OUT / "5_rfm_segments.png"); fig.savefig(OUT / "5_rfm_segments.svg"); plt.close(fig)

# ---------- Summary ----------
champ = seg.loc["Champions"] if "Champions" in seg.index else None
kpi = {
    "identified_customers": int(len(rfm)),
    "snapshot_date": str(SNAPSHOT.date()),
    "champions": {"customers": int(champ.customers), "revenue_musd": round(champ.revenue / 1e6, 2),
                  "revenue_share_pct": float(champ["revenue_share_%"])} if champ is not None else None,
    "top_segment_by_revenue": seg.index[0],
    "at_risk_revenue_musd": round(seg.loc["At risk (was loyal)", "revenue"] / 1e6, 2)
        if "At risk (was loyal)" in seg.index else None,
}
(OUT / "rfm_kpi.json").write_text(json.dumps(kpi, indent=2))
print(seg.round(1).to_string())
print(json.dumps(kpi, indent=2))
