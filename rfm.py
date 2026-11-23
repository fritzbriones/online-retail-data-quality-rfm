"""RFM customer segmentation on the CLEANED Online Retail data (run clean.py first).

- Monetary = NET spend (sales minus that customer's cancellations), in GBP.
  Using gross spend would credit customers for orders they cancelled.
- Frequency = number of distinct (non-cancelled) invoices.
- Recency  = days from last purchase to the snapshot (day after the last invoice).
- Customers whose net spend is <= 0 (everything cancelled/returned) are excluded
  from scoring and reported separately.
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
DARK, ACCENT, GREY = "#264653", "#e76f51", "#8d99ae"
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlelocation": "left", "axes.titleweight": "bold", "font.size": 10})

df = pd.read_csv(DATA / "retail_clean.csv", parse_dates=["InvoiceDate"],
                 dtype={"CustomerID": "Int64", "InvoiceNo": str})
known = df[df.CustomerID.notna()]
sales = known[~known.is_cancellation]
SNAPSHOT = df.InvoiceDate.max().normalize() + pd.Timedelta(days=1)

rfm = sales.groupby("CustomerID").agg(
    last_purchase=("InvoiceDate", "max"),
    first_purchase=("InvoiceDate", "min"),
    frequency=("InvoiceNo", "nunique"),
    gross_spend=("Revenue", "sum"))
rfm["monetary"] = known.groupby("CustomerID").Revenue.sum().reindex(rfm.index)   # net
rfm["recency_days"] = (SNAPSHOT - rfm.last_purchase).dt.days

excluded = rfm[rfm.monetary <= 0]
rfm = rfm[rfm.monetary > 0].copy()

# Scores 1-5, 5 = best. rank() breaks ties so every quintile has ~20% of customers.
rfm["R"] = pd.qcut(rfm.recency_days.rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F"] = pd.qcut(rfm.frequency.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M"] = pd.qcut(rfm.monetary.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def segment(r, f, m):
    """Exhaustive, non-overlapping rules on R and F (M breaks out Champions)."""
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal"
    if r <= 2 and f >= 3:
        return "At risk (lapsed regulars)"
    if r >= 4:
        return "New / recent one-offs"
    if r == 3:
        return "Needs attention"
    return "Hibernating"


rfm["segment"] = [segment(*x) for x in rfm[["R", "F", "M"]].itertuples(index=False)]

ORDER = ["Champions", "Loyal", "At risk (lapsed regulars)", "New / recent one-offs",
         "Needs attention", "Hibernating"]
seg = rfm.groupby("segment").agg(
    customers=("R", "size"),
    net_revenue_gbp=("monetary", "sum"),
    median_recency_days=("recency_days", "median"),
    median_orders=("frequency", "median"),
    median_spend_gbp=("monetary", "median")).reindex(ORDER)
seg["revenue_share_pct"] = seg.net_revenue_gbp / seg.net_revenue_gbp.sum() * 100
seg["customer_share_pct"] = seg.customers / seg.customers.sum() * 100
seg.round(1).to_csv(ROOT / "rfm_segments.csv")
rfm.reset_index().round({"monetary": 2, "gross_spend": 2}).to_csv(ROOT / "rfm_customers.csv", index=False)

# ---------- Chart: customer share vs revenue share, same % axis ----------
plot = seg.iloc[::-1]
y = range(len(plot))
fig, ax = plt.subplots(figsize=(9.5, 4.8))
ax.barh([i + 0.2 for i in y], plot.customer_share_pct, height=0.4, color=GREY, label="% of customers")
ax.barh([i - 0.2 for i in y], plot.revenue_share_pct, height=0.4, color=DARK, label="% of net revenue")
for i, (c, r) in enumerate(zip(plot.customer_share_pct, plot.revenue_share_pct)):
    ax.text(c + 0.6, i + 0.2, f"{c:.0f}%", va="center", fontsize=8, color=GREY)
    ax.text(r + 0.6, i - 0.2, f"{r:.0f}%", va="center", fontsize=8, color=DARK)
ax.set_yticks(list(y), plot.index)
ax.xaxis.set_major_formatter(mtick.PercentFormatter())
ax.legend(frameon=False, loc="lower right")
ch = seg.loc["Champions"]
ax.set_title(f"{ch.customer_share_pct:.0f}% of customers (Champions) bring "
             f"{ch.revenue_share_pct:.0f}% of net revenue")
fig.tight_layout()
fig.savefig(ROOT / "5_rfm_segments.png")
plt.close(fig)

# ---------- Business sizing: what is the at-risk pool worth? ----------
ar = seg.loc["At risk (lapsed regulars)"]
# Conservative sizing: a won-back customer is assumed to repeat their median
# historical spend (13 months of data), nothing more.
n10 = round(ar.customers * 0.10)
win_back_10 = n10 * float(ar.median_spend_gbp)
kpi = {
    "currency": "GBP",
    "snapshot_date": str(SNAPSHOT.date()),
    "scored_customers": int(len(rfm)),
    "excluded_net_spend_le_0": int(len(excluded)),
    "gross_vs_net_spend_gbp": [round(float(rfm.gross_spend.sum()), 2), round(float(rfm.monetary.sum()), 2)],
    "champions": {"customers": int(ch.customers), "customer_share_pct": round(float(ch.customer_share_pct), 1),
                  "revenue_share_pct": round(float(ch.revenue_share_pct), 1),
                  "net_revenue_gbp": round(float(ch.net_revenue_gbp), 2)},
    "at_risk": {"customers": int(ar.customers), "net_revenue_last_13m_gbp": round(float(ar.net_revenue_gbp), 2),
                "median_days_since_last_order": float(ar.median_recency_days),
                "median_spend_gbp": round(float(ar.median_spend_gbp), 2),
                "win_back_1_in_10_customers": int(n10),
                "win_back_1_in_10_value_gbp": round(win_back_10, 0)},
}
(ROOT / "rfm_kpi.json").write_text(json.dumps(kpi, indent=2))
print(seg.round(1).to_string())
print(json.dumps(kpi, indent=2))
