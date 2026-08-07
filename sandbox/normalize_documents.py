#!/usr/bin/env python3
"""Map real receipt/invoice datasets (CORD, SROIE) into the AI Accounting Runtime
`document` schema — the same shape the ERPNext generator emits — so real document
IMAGES can drive the extraction front-end and align with the generated treatment pairs.

CORD  = Indonesian receipts (IDR): line items (menu), tax, total. No vendor field.
SROIE = Malaysian receipts (MYR): vendor (company), date, total. No line items.
Together they cover both the vendor-field and line-item aspects the generator's synthetic
documents assert.

Out: data/documents/normalized/{cord,sroie}.jsonl  (+ a few sample PNGs).
Image bytes are NOT duplicated — each record references its parquet + row. Run: python3 normalize_documents.py
"""
import pyarrow.parquet as pq
import glob, json, os, re, io

BASE = "/mnt/backup/projects/accounting-runtime/data/documents"
OUT = os.path.join(BASE, "normalized")
os.makedirs(os.path.join(OUT, "samples"), exist_ok=True)


def num_idr(s):
    """IDR uses '.' as thousands sep, rarely decimals: '60.000' -> 60000."""
    if s is None:
        return None
    s = re.sub(r"[^\d.,-]", "", str(s))
    if not s:
        return None
    s = s.replace(".", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def num_myr(s):
    """MYR uses '.' as decimal: '9.00' -> 9.0."""
    if s is None:
        return None
    s = re.sub(r"[^\d.,-]", "", str(s)).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def split_of(path):
    for s in ("train", "validation", "val", "test", "dev"):
        if f"/{s}" in path or f"-{s}" in path or f"_{s}" in path:
            return "validation" if s == "val" else s
    return "unknown"


def norm_cord():
    files = sorted(glob.glob(f"{BASE}/cord-v2/**/*.parquet", recursive=True))
    out = open(os.path.join(OUT, "cord.jsonl"), "w")
    n = 0
    saved = 0
    for f in files:
        split = split_of(f)
        t = pq.ParquetFile(f).read()
        gts = t.column("ground_truth").to_pylist()
        imgs = t.column("image").to_pylist()
        for i, gts_raw in enumerate(gts):
            gp = json.loads(gts_raw).get("gt_parse", {})
            menu = gp.get("menu", [])
            if isinstance(menu, dict):
                menu = [menu]
            lines = []
            for m in menu:
                amt = num_idr(m.get("price") or m.get("itemsubtotal"))
                qty = num_myr(m.get("cnt")) or 1
                lines.append({"description": m.get("nm"), "qty": qty,
                              "unit_price": round(amt / qty, 2) if amt and qty else None,
                              "amount": amt})
            sub = gp.get("sub_total", {})
            tot = gp.get("total", {})
            if isinstance(sub, list):
                sub = sub[0] if sub else {}
            if isinstance(tot, list):
                tot = tot[0] if tot else {}
            taxes = []
            if sub.get("tax_price") is not None:
                taxes = [{"kind": "tax", "amount": num_idr(sub.get("tax_price"))}]
            rec = {"source": "cord-v2", "split": split, "index": i,
                   "doc_id": f"cord-{split}-{i:04d}",
                   "image_ref": {"parquet": os.path.relpath(f, BASE), "row": i,
                                 "path": (imgs[i] or {}).get("path")},
                   "document": {"supplier_name": None, "bill_no": None,
                                "invoice_date": None, "currency": "IDR",
                                "lines": lines, "taxes": taxes,
                                "declared_total": num_idr(tot.get("total_price"))},
                   "labels_present": ["line_items", "tax", "total"]}
            out.write(json.dumps(rec) + "\n")
            n += 1
            if saved < 3 and imgs[i] and imgs[i].get("bytes"):
                open(os.path.join(OUT, "samples", f"cord_{split}_{i}.png"), "wb").write(imgs[i]["bytes"])
                saved += 1
    out.close()
    return n


def norm_sroie():
    files = sorted(glob.glob(f"{BASE}/sroie-2019/**/*.parquet", recursive=True))
    out = open(os.path.join(OUT, "sroie.jsonl"), "w")
    n = 0
    saved = 0
    for f in files:
        split = split_of(f)
        t = pq.ParquetFile(f).read()
        ents = t.column("entities").to_pylist()
        keys = t.column("key").to_pylist() if "key" in t.column_names else [None] * len(ents)
        imgs = t.column("image").to_pylist()
        for i, e in enumerate(ents):
            rec = {"source": "sroie-2019", "split": split, "index": i,
                   "doc_id": f"sroie-{split}-{keys[i] or i}",
                   "image_ref": {"parquet": os.path.relpath(f, BASE), "row": i,
                                 "path": (imgs[i] or {}).get("path")},
                   "document": {"supplier_name": (e or {}).get("company"),
                                "bill_no": None,
                                "invoice_date": (e or {}).get("date"),
                                "currency": "MYR", "lines": [], "taxes": [],
                                "declared_total": num_myr((e or {}).get("total"))},
                   "labels_present": ["supplier", "date", "total"]}
            out.write(json.dumps(rec) + "\n")
            n += 1
            if saved < 3 and imgs[i] and imgs[i].get("bytes"):
                open(os.path.join(OUT, "samples", f"sroie_{split}_{i}.png"), "wb").write(imgs[i]["bytes"])
                saved += 1
    out.close()
    return n


if __name__ == "__main__":
    c = norm_cord()
    s = norm_sroie()
    print(f"NORM_OK cord={c} sroie={s} out={OUT}")
