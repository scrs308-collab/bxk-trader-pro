"""Certification-only tastytrade order reader. GET only; never uses live secrets.

Supply certification credentials explicitly. Not wired to staging's live-account
credentials or any public route. Wire/schema checks still need certification.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import re
import time

import requests
from staging_reconciliation import Snapshot, canonical

CERT = "https://api.cert.tastyworks.com"


class CertificationOrderReader:
    def __init__(self, account, user_id, headers, session=None, clock=time.time, max_pages=20):
        if not re.fullmatch(r"[A-Za-z0-9-]{4,40}", account):
            raise ValueError("Invalid certification account")
        self.account, self.headers = account, headers
        self.session, self.clock, self.max_pages = session or requests.Session(), clock, max_pages
        identity = hashlib.sha256((str(user_id)+":"+account).encode()).hexdigest()
        self.scope = "simulation:cert:"+identity

    def _get(self, suffix, params):
        response = self.session.get(CERT+"/accounts/"+self.account+"/orders"+suffix,
                                    params=params, headers=self.headers(), timeout=15, allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError("Certification order read unavailable")
        return response.json()

    def _pages(self, suffix, params):
        items, seen = [], set()
        for page in range(self.max_pages):
            body = self._get(suffix, dict(params, **{"page-offset": page, "per-page": 100}))
            batch, metadata = body["data"]["items"], body.get("pagination", {})
            if not isinstance(batch, list) or metadata.get("page-offset") != page:
                return items, False
            signature = tuple((str(x.get("id")), str(x.get("updated-at")), str(x.get("status"))) for x in batch)
            if signature and signature in seen:
                return items, False
            seen.add(signature)
            items.extend(batch)
            pages = metadata.get("total-pages")
            if not isinstance(pages, int) or isinstance(pages, bool) or pages < 0:
                return items, False
            if page+1 >= pages:
                return items, True
        return items, False

    def _normalise(self, item):
        basic = {"id": str(item.get("id") or ""), "scope": self.scope if item.get("account-number") == self.account else "INVALID_ACCOUNT",
                 "external-identifier": item.get("external-identifier"), "status": item.get("status"),
                 "filled-quantity": None}
        try:
            order = canonical(item)
            filled = []
            for leg in item["legs"]:
                fills = leg["fills"]
                if not isinstance(fills, list):
                    return basic
                quantities = [Decimal(str(fill["quantity"])) for fill in fills]
                if any(not number.is_finite() or number <= 0 for number in quantities):
                    return basic
                executed = sum(quantities, Decimal(0))
                # Cancelled remaining quantity is not evidence of an execution.
                if item.get("status") not in {"Cancelled", "Expired", "Rejected"}:
                    remaining = Decimal(str(leg["remaining-quantity"]))
                    if not remaining.is_finite() or remaining < 0 or executed+remaining != Decimal(str(leg["quantity"])):
                        return basic
                filled.append(executed)
            if len(set(filled)) != 1 or any(not x.is_finite() or x < 0 for x in filled):
                return basic  # Imbalanced or malformed fills require manual review.
            return {**order, **basic, "filled-quantity": str(filled[0])}
        except (KeyError, ValueError, TypeError, ArithmeticError):
            return basic

    def read(self, row):
        if row["scope"] != self.scope:
            raise ValueError("Certification account scope mismatch")
        stamp = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
        # Overlap the attempt and retain an absolute UTC window across midnight.
        history, complete = self._pages("", {"start-at": stamp(row["attempt_at"]-300),
                                             "end-at": stamp(self.clock()), "sort": "Asc"})
        today, today_complete = self._pages("/live", {})
        items = history+today
        if row["broker_id"]:
            data = self._get("/"+row["broker_id"], {})["data"]
            items.append(data)
        relevant = [self._normalise(x) for x in items
                    if x.get("external-identifier") == row["correlation"]
                    or (row["broker_id"] and str(x.get("id")) == row["broker_id"])]
        return Snapshot(self.scope, relevant, complete and today_complete)
