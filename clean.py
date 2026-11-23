"""Real-world data cleaning: UCI Online Retail (541,909 transaction lines).

Real dataset -> real problems: duplicates, missing customer IDs, cancellation
invoices, unpriced stock adjustments, non-product fee lines.
Every decision is recorded and justified; nothing is dropped silently.

Input : data/Online Retail.xlsx   (UCI original)  or
        data/online-retail.csv    (same 541,909 rows as CSV, e.g. the copy in
                                   databricks/Spark-The-Definitive-Guide)
Output: data/retail_clean.csv, cleaning_report.json

All money values are in GBP (the retailer is UK-based).
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def load_raw():
    xlsx, csv = DATA / "Online Retail.xlsx", DATA / "online-retail.csv"
    if xlsx.exists():
        df = pd.read_excel(xlsx, dtype={"InvoiceNo": str, "StockCode": str})
    elif csv.exists():
        df = pd.read_csv(csv, dtype={"InvoiceNo": str, "StockCode": str}, encoding="latin-1")
        df["InvoiceDate"] = pd.to_datetime(df.InvoiceDate, format="%m/%d/%Y %H:%M")
    else:
        raise FileNotFoundError("Put 'Online Retail.xlsx' (or online-retail.csv) in data/ - see README")
    df["InvoiceNo"] = df.InvoiceNo.astype(str)
    df["StockCode"] = df.StockCode.astype(str)
    return df


LOG = {}


def log(step, kept, detail):
    LOG[step] = {"rows_kept": int(kept), **detail}
    print(f"{step:<34} kept {kept:>7,} | {detail}")


if __name__ == "__main__":
    df = load_raw()
    n_raw = len(df)
    missing_desc_raw = int(df.Description.isna().sum())
    log("0_raw", n_raw, {"missing_description": missing_desc_raw})

    # Step 1: exact duplicate lines (same invoice, product, qty, time, price, customer)
    dups = int(df.duplicated().sum())
    df = df.drop_duplicates()
    log("1_dedupe_exact", len(df), {"exact_duplicates_removed": dups})

    # Step 2: cancellations - keep and flag, they are real lost revenue
    df["is_cancellation"] = df.InvoiceNo.str.startswith("C")
    log("2_flag_cancellations", len(df), {"cancellation_lines_flagged": int(df.is_cancellation.sum())})

    # Step 3: negative quantity on a normal invoice = stock write-off, not a sale
    adj = (df.Quantity < 0) & ~df.is_cancellation
    log("3_find_stock_adjustments", len(df), {
        "negative_qty_without_C_invoice": int(adj.sum()),
        "of_which_unit_price_zero": int((adj & (df.UnitPrice <= 0)).sum()),
        "note": "all carry a zero price, so step 4 removes them"})

    # Step 4: zero/negative price lines
    bad_price = df.UnitPrice <= 0
    removed = df[bad_price]
    df = df[~bad_price]
    log("4_drop_nonpositive_price", len(df), {
        "removed": int(len(removed)),
        "of_which_no_customer_id": int(removed.CustomerID.isna().sum()),
        "of_which_stock_writeoffs": int((removed.Quantity < 0).sum()),
        "why": "unpriced lines are stock adjustments/write-offs and free samples with no "
               "revenue; mostly without a customer. Not sales.",
        "top_stockcodes": removed.StockCode.value_counts().head(5).to_dict()})

    # Step 5: non-product stock codes (postage, manual entries, bank charges, Amazon fees ...)
    nonprod_mask = df.StockCode.str.match(r"^[A-Za-z]")
    nonprod = df[nonprod_mask]
    df = df[~nonprod_mask]
    log("5_drop_nonproduct_codes", len(df), {
        "removed": int(len(nonprod)),
        "net_value_removed_gbp": round(float((nonprod.Quantity * nonprod.UnitPrice).sum()), 2),
        "codes": nonprod.StockCode.value_counts().head(6).to_dict(),
        "max_unit_price_remaining": float(df.UnitPrice.max())})

    # Step 6: missing Description (none should remain - they were all unpriced lines)
    n_desc = int(df.Description.isna().sum())
    df["Description"] = df.Description.fillna("Unknown").str.strip()
    log("6_missing_description", len(df), {"filled_unknown": n_desc,
                                             "missing_in_raw": missing_desc_raw})

    # Step 7: missing CustomerID - keep as NA
    df["CustomerID"] = df.CustomerID.astype("Int64")
    df["Revenue"] = (df.Quantity * df.UnitPrice).round(2)
    no_id = df.CustomerID.isna()
    sales_mask = ~df.is_cancellation
    log("7_keep_missing_customer_id", len(df), {
        "rows_missing_customer_id": int(no_id.sum()),
        "share_of_rows_pct": round(float(no_id.mean() * 100), 1),
        "share_of_gross_sales_pct": round(float(df.loc[no_id & sales_mask, "Revenue"].sum()
                                                / df.loc[sales_mask, "Revenue"].sum() * 100), 1),
        "why": "Dropping them would delete ~15% of sales. Revenue analyses use all rows; "
               "customer analyses (RFM) use identified customers only."})

    df["InvoiceMonth"] = df.InvoiceDate.dt.to_period("M").astype(str)

    sales, canc = df[sales_mask], df[df.is_cancellation]
    last = df.InvoiceDate.max()
    report = {
        "currency": "GBP",
        "cleaning_log": LOG,
        "raw_rows": n_raw,
        "clean_rows": int(len(df)),
        "gross_sales_gbp": round(float(sales.Revenue.sum()), 2),
        "cancellations_gbp": round(float(canc.Revenue.sum()), 2),
        "net_revenue_gbp": round(float(df.Revenue.sum()), 2),
        "cancellation_rate_pct": round(float(-canc.Revenue.sum() / sales.Revenue.sum() * 100), 2),
        "sales_invoices": int(sales.InvoiceNo.nunique()),
        "cancellation_invoices": int(canc.InvoiceNo.nunique()),
        "avg_order_value_gbp": round(float(sales.Revenue.sum() / sales.InvoiceNo.nunique()), 2),
        "products": int(df.StockCode.nunique()),
        "identified_customers": int(df.CustomerID.nunique()),
        "countries": int(df.Country.nunique()),
        "date_range": [str(df.InvoiceDate.min()), str(last)],
        "note_partial_last_month": f"{last:%Y-%m} only covers up to {last:%d %b}; "
                                   "excluded from monthly trend charts",
    }
    (ROOT / "cleaning_report.json").write_text(json.dumps(report, indent=2))
    df.to_csv(DATA / "retail_clean.csv", index=False)
    print(json.dumps({k: v for k, v in report.items() if k != "cleaning_log"}, indent=2))
