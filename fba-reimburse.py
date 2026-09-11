#!/usr/bin/env python3
"""Cross-check Amazon FBA CSVs for lost/damaged events with no matching reimbursement row.

This is the fulfillment copy of the browser checker. Run it when a seller emails
their three Seller Central exports; it never claims Amazon will pay, it only flags
rows that look unpaid in the files they handed us.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Amazon ledger reason codes that represent a loss Amazon may owe for, from Seller
# Central's inventory-adjustment table (misplaced, FC-damaged, disposed).
CLAIMABLE_REASON_CODES = {
    "M": "Inventory misplaced",
    "5": "Inventory misplaced",
    "E": "Damaged at Amazon fulfillment center",
    "6": "Damaged at Amazon fulfillment center",
    "7": "Damaged at Amazon fulfillment center",
    "H": "Damaged at Amazon fulfillment center",
    "K": "Damaged at Amazon fulfillment center",
    "U": "Damaged at Amazon fulfillment center",
    "D": "Inventory disposed of",
}

# Reason codes that are found-units, disposition flips, or already-reimbursed
# corrections, so they should not be treated as an unpaid loss.
SKIP_REASON_CODES = {"F", "N", "P", "Q", "O", "G"}

# Customer-return dispositions where Amazon or the carrier is on the hook.
CLAIMABLE_RETURN_DISPOSITIONS = {"DAMAGED", "CARRIER_DAMAGED"}

# Match a reimbursement to an event if it lands within this many days of the event.
MATCH_WINDOW_DAYS = 90

HEADER_ALIASES = {
    "fnsku": ("fnsku", "fulfillment network sku", "fnsku/asin"),
    "asin": ("asin",),
    "sku": ("sku", "msku", "merchant sku", "seller sku"),
    "qty": ("quantity", "qty", "quantity-reimbursed", "unreconciled quantity"),
    "date": (
        "date",
        "approval-date",
        "return-date",
        "event date",
        "date and time",
        "snapshot-date",
    ),
    "reason": ("reason", "reason code", "adjustment reason"),
    "reason_code": ("reason code", "code"),
    "event_type": ("event type", "event-type", "type"),
    "disposition": ("detailed-disposition", "disposition", "detailed disposition"),
    "order_id": ("amazon-order-id", "order-id", "order id", "amazon order id"),
    "amount": ("amount-total", "amount total", "reimbursed amount"),
}


def _norm_header(name: str) -> str:
    """Collapse a CSV header to lowercase letters so Amazon's hyphen vs space labels match."""
    return re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower()).strip()


def _pick(row: dict[str, str], *logical: str) -> str:
    """Return the first non-empty cell whose header aliases match a logical field name."""
    keys = {_norm_header(k): v for k, v in row.items()}
    wanted: list[str] = []
    for name in logical:
        wanted.extend(HEADER_ALIASES.get(name, (name,)))
        wanted.append(name)
    for alias in wanted:
        val = keys.get(_norm_header(alias))
        if val not in (None, ""):
            return str(val).strip()
    return ""


def _parse_date(raw: str) -> datetime | None:
    """Parse the date stamps Amazon actually emits, ignoring time-of-day when present."""
    s = (raw or "").strip()
    if not s:
        return None
    s = s.replace("T", " ").split(".")[0]
    candidates = [s[:19] if " " in s and len(s) >= 19 else s[:10]]
    for piece in candidates:
        for fmt in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(piece, fmt)
            except ValueError:
                continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d")
    return None


def _qty(raw: str) -> float:
    """Read quantity as a positive count even when the ledger stores losses as negatives."""
    try:
        return abs(float(str(raw).replace(",", "").strip() or 0))
    except ValueError:
        return 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    """Load a Seller Central CSV, skipping Amazon's preamble rows until a real header appears."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines[:30]):
        low = line.lower()
        if "fnsku" in low or "asin" in low or "reimbursement" in low:
            start = i
            break
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return [dict(r) for r in reader if any((v or "").strip() for v in r.values())]


def ledger_events(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Keep only ledger rows whose reason code or reason text looks like an Amazon-caused loss."""
    out: list[dict[str, Any]] = []
    for row in rows:
        event_type = _pick(row, "event_type").lower()
        if event_type and "adjust" not in event_type:
            continue
        code = _pick(row, "reason_code").upper()
        if not code:
            reason = _pick(row, "reason")
            token = reason.strip().split()[0].upper() if reason else ""
            code = token if len(token) <= 2 else ""
        if code in SKIP_REASON_CODES:
            continue
        reason_text = _pick(row, "reason").lower()
        claimable = code in CLAIMABLE_REASON_CODES
        if not claimable:
            claimable = any(
                needle in reason_text
                for needle in ("misplaced", "damaged at amazon", "inventory disposed", "disposed of")
            )
        if not claimable:
            continue
        fnsku = _pick(row, "fnsku")
        if not fnsku:
            continue
        out.append(
            {
                "kind": "ledger",
                "fnsku": fnsku,
                "asin": _pick(row, "asin"),
                "sku": _pick(row, "sku"),
                "qty": _qty(_pick(row, "qty")),
                "date": _parse_date(_pick(row, "date")),
                "reason": CLAIMABLE_REASON_CODES.get(code) or _pick(row, "reason") or code,
                "code": code,
                "order_id": _pick(row, "order_id"),
            }
        )
    return out


def return_events(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Keep FBA customer returns Amazon or the carrier damaged, which should have a reimbursement."""
    out: list[dict[str, Any]] = []
    for row in rows:
        disp = _pick(row, "disposition").upper().replace(" ", "_")
        if disp not in CLAIMABLE_RETURN_DISPOSITIONS:
            continue
        fnsku = _pick(row, "fnsku") or _pick(row, "asin")
        if not fnsku:
            continue
        out.append(
            {
                "kind": "return",
                "fnsku": fnsku,
                "asin": _pick(row, "asin"),
                "sku": _pick(row, "sku"),
                "qty": _qty(_pick(row, "qty") or "1"),
                "date": _parse_date(_pick(row, "date")),
                "reason": disp,
                "code": disp,
                "order_id": _pick(row, "order_id"),
            }
        )
    return out


def reimbursements(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Index already-paid reimbursement rows so we can subtract them from the loss list."""
    out: list[dict[str, Any]] = []
    for row in rows:
        fnsku = _pick(row, "fnsku") or _pick(row, "asin")
        if not fnsku:
            continue
        out.append(
            {
                "fnsku": fnsku,
                "asin": _pick(row, "asin"),
                "sku": _pick(row, "sku"),
                "qty": _qty(_pick(row, "qty") or "1"),
                "date": _parse_date(_pick(row, "date")),
                "order_id": _pick(row, "order_id"),
                "amount": _pick(row, "amount"),
            }
        )
    return out


def unpaid(events: list[dict[str, Any]], paid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag loss events that have no reimbursement on the same FNSKU or order id inside the match window."""
    remaining = [dict(p) for p in paid]
    flags: list[dict[str, Any]] = []
    window = timedelta(days=MATCH_WINDOW_DAYS)
    for ev in events:
        match_i = None
        for i, p in enumerate(remaining):
            same_id = p["fnsku"] == ev["fnsku"] or (
                bool(ev["order_id"]) and bool(p["order_id"]) and p["order_id"] == ev["order_id"]
            )
            if not same_id:
                continue
            if ev["date"] and p["date"] and not (ev["date"] - window <= p["date"] <= ev["date"] + window):
                continue
            match_i = i
            break
        if match_i is None:
            flags.append(ev)
        else:
            remaining.pop(match_i)
    return flags


def audit(ledger_path: Path | None, returns_path: Path | None, reimb_path: Path | None) -> dict[str, Any]:
    """Run the three-file cross-check and return counts plus the unpaid flag rows."""
    events: list[dict[str, Any]] = []
    if ledger_path:
        events.extend(ledger_events(read_csv(ledger_path)))
    if returns_path:
        events.extend(return_events(read_csv(returns_path)))
    paid = reimbursements(read_csv(reimb_path)) if reimb_path else []
    flags = unpaid(events, paid)
    return {
        "events": len(events),
        "reimbursements": len(paid),
        "unpaid": flags,
    }


def _self_test() -> None:
    """Prove a lost unit with no reimbursement flags, and the same unit with a payout does not."""
    tmp = Path("/tmp/fba-reimburse-fixtures")
    tmp.mkdir(exist_ok=True)
    (tmp / "ledger.csv").write_text(
        "Date,FNSKU,ASIN,Quantity,Event Type,Reason,Reason Code\n"
        "2026-07-01,X001LOST,B00LOST, -2,Adjustment,Inventory misplaced,M\n"
        "2026-07-02,X001FOUND,B00FOUND,1,Adjustment,Inventory found,F\n"
    )
    (tmp / "returns.csv").write_text(
        "return-date,fnsku,asin,quantity,detailed-disposition,order-id\n"
        "2026-07-10,X001RET,B00RET,1,DAMAGED,111-2222222-3333333\n"
    )
    (tmp / "paid.csv").write_text(
        "approval-date,fnsku,asin,quantity-reimbursed,amazon-order-id,amount-total\n"
        "2026-07-12,X001RET,B00RET,1,111-2222222-3333333,14.50\n"
    )
    empty = audit(tmp / "ledger.csv", tmp / "returns.csv", tmp / "paid.csv")
    unpaid_fnskus = {r["fnsku"] for r in empty["unpaid"]}
    assert "X001LOST" in unpaid_fnskus, unpaid_fnskus
    assert "X001FOUND" not in unpaid_fnskus, unpaid_fnskus
    assert "X001RET" not in unpaid_fnskus, unpaid_fnskus
    none_paid = audit(tmp / "ledger.csv", tmp / "returns.csv", None)
    assert {r["fnsku"] for r in none_paid["unpaid"]} == {"X001LOST", "X001RET"}
    print("self-test ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        _self_test()
        sys.exit(0)
    if len(sys.argv) < 2:
        print("usage: fba-reimburse.py --self-test | <ledger.csv> [returns.csv] [reimbursements.csv]")
        sys.exit(2)
    ledger = Path(sys.argv[1])
    returns = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    reimb = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    result = audit(ledger, returns, reimb)
    serializable = []
    for row in result["unpaid"]:
        item = dict(row)
        item["date"] = row["date"].date().isoformat() if row["date"] else ""
        serializable.append(item)
    print(json.dumps({"events": result["events"], "reimbursements": result["reimbursements"], "unpaid": serializable}, indent=2))
