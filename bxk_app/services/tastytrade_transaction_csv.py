"""Read user-supplied Tastytrade Transactions exports for one Performance review."""
import csv
import io
import re
from collections import defaultdict
from decimal import Decimal

from bxk_app.services.broker_performance_reconciliation import decimal_value, valid_timestamp

MAX_CSV_BYTES = 2 * 1024 * 1024
COLUMNS = {
    "Date", "Type", "Action", "Symbol", "Instrument Type", "Value", "Quantity",
    "Commissions", "Fees", "Multiplier", "Order #", "Total", "Currency",
}
CASH = re.compile(r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?")


def _cash(text):
    text = text.strip()
    if len(text) <= 24 and CASH.fullmatch(text):
        return Decimal(text.replace(",", ""))
    return None


def read_transactions_csv(data):
    """Group option trade rows by broker order ID without treating them as API data."""
    grouped = defaultdict(list)
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
                or not COLUMNS.issubset(reader.fieldnames)):
            raise ValueError("Choose a Tastytrade Transactions CSV with commissions and fees.")
        for row in reader:
            if None in row or any(row[key] is None for key in COLUMNS):
                raise ValueError("The Transactions CSV contains an incomplete row.")
            if row["Type"].strip().casefold() != "trade":
                continue
            if row["Instrument Type"].strip().casefold() != "equity option":
                continue
            order_id = row["Order #"].strip()
            if not re.fullmatch(r"[0-9]{1,24}", order_id):
                raise ValueError("An option trade row is missing a valid order number.")
            quantity = decimal_value(row["Quantity"].strip())
            timestamp = valid_timestamp(row["Date"])
            gross, commission, fee, net = map(_cash, (row[key] for key in (
                "Value", "Commissions", "Fees", "Total",
            )))
            if (row["Currency"].strip() != "USD" or row["Multiplier"].strip() != "100"
                    or quantity is None or not 0 < quantity <= 100000
                    or quantity != quantity.to_integral_value() or timestamp is None
                    or None in (gross, commission, fee, net)
                    or gross + commission + fee != net):
                grouped[order_id].append(None)
                continue
            grouped[order_id].append({
                "symbol": row["Symbol"], "action": row["Action"].strip().replace("_", " ").upper(),
                "quantity": int(quantity), "time": timestamp, "gross": gross, "net": net,
            })
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("The Transactions CSV could not be read.") from exc
    if not grouped:
        raise ValueError("The Transactions CSV contains no option trade rows.")
    return grouped
