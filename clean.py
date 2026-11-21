"""Real-world data cleaning: UCI Online Retail (541,909 transactions).

Real dataset -> real problems: duplicates, 25% missing customer IDs,
cancellation orders, negative quantities, impossible prices.
Every decision is recorded and justified; nothing is dropped silently.

Outputs: data/retail_clean.csv, outputs/cleaning_report.json
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

LOG = {}


def log(step, kept, detail):
    LOG[step] = {"rows_kept": int(kept), **detail}
    print(f"{step:<38} kept {kept:>7,} | {detail}")


# ---------- Load ----------
df = pd.read_excel(DATA / "Online Retail.xlsx")
log("raw", len(df), {})

# ---------- Step 1: drop exact duplicates ----------
dups = df.duplicated().sum()
df = df.drop_duplicates()
log("1_dedupe_exact", len(df), {"exact_duplicates_removed": int(dups)})

# ---------- Step 2: separate cancellations (keep them, but flag) ----------
df["is_cancellation"] = df.InvoiceNo.astype(str).str.startswith("C")
n_cancel = int(df.is_cancellation.sum())
log("2_flag_cancellations", len(df), {"cancellation_rows_flagged": n_cancel})

# ---------- Step 3: negative quantities outside cancellations ----------
neg_no_flag = df[(df.Quantity < 0) & ~df.is_cancellation]
log("3_neg_qty_no_invoice", len(df), {"negative_qty_without_C_invoice": int(len(neg_no_flag))})
# Treat as damaged/lost stock adjustments: keep but flag, do NOT delete (they are real events).
df["is_adjustment"] = (df.Quantity < 0) & ~df.is_cancellation

# ---------- Step 4: zero/negative price rows ----------
free_price = df[df.UnitPrice <= 0]
df = df[df.UnitPrice > 0]
log("4_drop_nonpositive_price", len(df),
    {"removed": int(len(free_price)),
     "why": "adjustment lines (e.g., POST, M, BANK CHARGES) carry 0 price; not real sales",
     "stockcodes_removed": free_price.StockCode.value_counts().head(5).to_dict()})

# ---------- Step 5: impossible unit prices ----------
# Explore first: extreme prices cluster on non-product stock codes (M=manual, POST=shipping...)
non_product = df[df.StockCode.astype(str).str.match(r"^[A-Za-z]")]
df = df[~df.StockCode.astype(str).str.match(r"^[A-Za-z]")]
df = df[df.UnitPrice < 1000]  #Products top out far below the 38970 manual entry
log("5_drop_nonproduct_and_outlier_price", len(df),
    {"non_product_codes_removed": int(len(non_product)),
     "price_outliers_removed_above_1000": int((df.UnitPrice >= 1000).sum()),
     "examples_non_product": non_product.StockCode.value_counts().head(5).to_dict()})

# ---------- Step 6: missing Description ----------
df["Description"] = df["Description"].fillna("Unknown")
log("6_fill_missing_description", len(df), {"filled_unknown": int(df.Description.eq("Unknown").sum())})

# ---------- Step 7: missing CustomerID ----------
n_missing_id = int(df.CustomerID.isna().sum())
df["CustomerID"] = df.CustomerID.astype("Int64")   # nullable int, keep NAs honestly
log("7_keep_missing_customer_id", len(df),
    {"missing_customer_id": n_missing_id,
     "why": "25% of sales have no customer ID; dropping them would erase a quarter of revenue. "
            "Keep as NA; customer-level analyses will use the non-null subset, "
            "revenue analyses use all rows."})

# ---------- Step 8: derive analytical fields ----------
df["Revenue"] = (df.Quantity * df.UnitPrice).round(2)
df["InvoiceMonth"] = df.InvoiceDate.dt.to_period("M")
df["InvoiceNo"] = df.InvoiceNo.astype(str)
df["StockCode"] = df.StockCode.astype(str)

# ---------- Report ----------
sales = df[~df.is_cancellation & ~df.is_adjustment]
report = {
    "cleaning_log": LOG,
    "raw_rows": 541909,
    "clean_rows": int(len(df)),
    "net_revenue_all_lines": round(float(df.Revenue.sum()), 2),
    "gross_revenue_sales_only": round(float((df[~df.is_cancellation & ~df.is_adjustment].Revenue).sum()), 2),
    "cancellation_impact": round(float(df[df.is_cancellation].Revenue.sum()), 2),
    "order_count": int(df.InvoiceNo.nunique()),
    "product_count": int(df.StockCode.nunique()),
    "customer_count_known": int(df.CustomerID.nunique()),
    "countries": int(df.Country.nunique()),
    "date_range": [str(df.InvoiceDate.min()), str(df.InvoiceDate.max())],
}
(OUT / "cleaning_report.json").write_text(json.dumps(report, indent=2, default=float))
df.to_csv(DATA / "retail_clean.csv", index=False)

print(json.dumps(report, indent=2, default=float))
