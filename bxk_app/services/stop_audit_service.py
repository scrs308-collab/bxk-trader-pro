"""Read-only market observations of explicitly confirmed stopped-out SPXW condors.

This module never constructs broker positions or calls an order mutation. An audit
is an immutable copy of the actual trade plus independently sampled estimates.
"""
import asyncio
import hashlib
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas_market_calendars as market_calendars
from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import IntegrityError

from bxk_app.database import database_configured, get_session_factory
from bxk_app.db_models.stop_audit import StopAudit, StopAuditSample
from bxk_app.db_models.trade_journal import TradeJournal
from bxk_app.db_models.user import User
from bxk_app.position_monitor import assess_quote_quality, parse_option_symbol
from bxk_app.services.trade_journal_service import (
    _closing_exit_debit, _opening_fill_credit,
)

UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")
SAMPLE_INTERVAL_SECONDS = 60
MAX_QUOTE_AGE_SECONDS = 90
MAX_QUOTE_SKEW_SECONDS = 30
logger = logging.getLogger(__name__)


def stop_audit_enabled():
    return os.getenv("BXK_STOP_AUDIT_ENABLED", "true").strip().lower() not in {"false", "0", "off", "no"}


def _utc(value):
    """Database-only normalization: SQLite drops the stored UTC offset."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _now(value=None):
    if value is not None and value.tzinfo is None:
        raise ValueError("An aware observation time is required.")
    return _utc(value or datetime.now(UTC))


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _identity(context):
    context = context or {}
    role = getattr(context.get("role"), "value", context.get("role"))
    if str(role).upper() not in {"OWNER", "BETA"}:
        raise PermissionError("An authenticated trading account is required.")
    try:
        return uuid.UUID(str(context.get("user_id")))
    except (TypeError, ValueError, AttributeError):
        raise PermissionError("A database-backed user is required.") from None


def _factory(factory):
    if factory is not None:
        return factory
    if not database_configured():
        raise ValueError("Stop Audit requires the application database.")
    return get_session_factory()


@lru_cache(maxsize=1024)
def _session_bounds(day):
    """Cboe calendar includes holidays and half days; no weekday-only fallback."""
    schedule = market_calendars.get_calendar("CBOE_Index_Options").schedule(
        start_date=day, end_date=day,
    )
    equity_schedule = market_calendars.get_calendar("NYSE").schedule(start_date=day, end_date=day)
    if schedule.empty or equity_schedule.empty:
        return None
    row, equity_row = schedule.iloc[0], equity_schedule.iloc[0]
    # The Cboe calendar package omits some Christmas-Eve early closes.
    # Conservatively cap it using the cash-market half-day calendar too.
    # Verified against Cboe's published 2026 Nov 27 / Dec 24 schedule.
    opened = max(row.market_open.to_pydatetime(), equity_row.market_open.to_pydatetime())
    closed = min(row.market_close.to_pydatetime(), equity_row.market_close.to_pydatetime() + timedelta(minutes=15))
    return opened, closed


def expiry_cutoff(expiration):
    bounds = _session_bounds(expiration)
    if not bounds:
        raise ValueError("Expiration is not a known Cboe trading session.")
    # Expiring SPXW stops at 16:00 ET (13:00 on half days), while this
    # index-option calendar closes at 16:15 (13:15). Never use AM SPX.
    return bounds[1] - timedelta(minutes=15)


def _session_open(now):
    bounds = _session_bounds(now.astimezone(EASTERN).date())
    return bool(bounds and bounds[0] <= now < bounds[1])


def _trade_snapshot(journal, now):
    if journal.status != "CLOSED" or not journal.closing_broker_order_id:
        raise ValueError("A confirmed filled closing order is required.")
    if journal.closed_at is None or _utc(journal.closed_at) > now:
        raise ValueError("The actual close time is unavailable or invalid.")
    if not journal.expiration:
        raise ValueError("Expiration is unavailable.")
    cutoff = expiry_cutoff(journal.expiration)
    if now >= cutoff:
        raise ValueError("Forward tracking must start before expiration.")
    if str(journal.underlying).upper() not in {"SPX", "SPXW"}:
        raise ValueError("This version supports SPXW PM-settled condors only.")
    quantity = _number(journal.quantity)
    credit = _number(journal.entry_fill_credit)
    exit_debit = _number(journal.exit_debit)
    realized = _number(journal.realized_pnl)
    if quantity is None or quantity <= 0 or not quantity.is_integer() or credit is None or credit <= 0 or exit_debit is None or realized is None:
        raise ValueError("Complete actual entry, exit, quantity and realized P/L are required.")
    if abs(realized - (credit - exit_debit) * 100 * quantity) > 0.02:
        raise ValueError("Actual journal cash flows do not reconcile.")
    entry = journal.entry_snapshot
    if not isinstance(entry, dict) or not isinstance(entry.get("order"), dict):
        raise ValueError("Original trade details are unavailable.")
    source_legs = entry["order"].get("legs")
    if not isinstance(source_legs, list) or len(source_legs) != 4 or any(not isinstance(leg, dict) for leg in source_legs):
        raise ValueError("Exactly four original option legs are required.")
    legs = []
    seen = set()
    ratios = []
    for leg in source_legs:
        symbol = str(leg.get("symbol") or "").strip()
        try:
            parsed = parse_option_symbol(symbol)
        except (TypeError, ValueError):
            parsed = None
        action = str(leg.get("action") or "").upper()
        if not parsed or parsed["root"] != "SPXW" or parsed["expiration"] != journal.expiration.isoformat() or action not in {"BUY", "SELL"} or symbol in seen:
            raise ValueError("Original SPXW symbols, expiration and actions must be unambiguous.")
        seen.add(symbol)
        ratio = _number(leg.get("quantity", 1))
        if ratio is None or ratio <= 0:
            raise ValueError("Invalid original leg quantity.")
        ratios.append(ratio)
        legs.append({"symbol": symbol, "action": action, "option_type": parsed["option_type"], "strike": parsed["strike"]})
    if len(set(ratios)) != 1:
        raise ValueError("Only 1:1 iron condors are supported.")
    by_key = {(leg["option_type"], leg["action"]): leg["strike"] for leg in legs}
    if len(by_key) != 4 or set(by_key) != {("P", "BUY"), ("P", "SELL"), ("C", "BUY"), ("C", "SELL")}:
        raise ValueError("The original legs are not an iron condor.")
    lp, sp, sc, lc = [by_key[key] for key in [("P", "BUY"), ("P", "SELL"), ("C", "SELL"), ("C", "BUY")]]
    if not lp < sp < sc < lc:
        raise ValueError("The original legs are not a credit iron condor.")
    return {
        "legs": legs, "quantity": int(quantity), "entry_fill_credit": credit,
        "exit_debit": exit_debit, "broker_order_id": journal.broker_order_id,
        "closing_broker_order_id": journal.closing_broker_order_id,
        "maximum_debit": max(sp - lp, lc - sc), "multiplier": 100,
    }, cutoff


def _broker_identity(broker, user_id):
    if str(getattr(broker, "broker_name", "")).lower() != "tastytrade":
        raise ValueError("This version requires a Tastytrade quote connection.")
    account = str(broker.get_default_account_number() or "").strip()
    if not account:
        raise ValueError("The selected broker account is unavailable.")
    fingerprint = hashlib.sha256(f"{user_id}|tastytrade|{account}".encode()).hexdigest()
    return account, fingerprint


def _verify_order(order, order_id, trade, *, opening, account):
    if not isinstance(order, dict) or str(order.get("id")) != str(order_id) or str(order.get("status")).upper() != "FILLED":
        raise ValueError("The account's filled order could not be verified.")
    reported_account = order.get("account-number", order.get("account_number"))
    if reported_account is not None and str(reported_account).strip() != account:
        raise ValueError("The returned order belongs to a different account.")
    expected = {}
    for leg in trade["legs"]:
        action = leg["action"] if opening else ("BUY" if leg["action"] == "SELL" else "SELL")
        expected[leg["symbol"]] = f"{action} TO {'OPEN' if opening else 'CLOSE'}"
    actual = {}
    source_legs = order.get("legs")
    if not isinstance(source_legs, list) or len(source_legs) != 4 or any(not isinstance(leg, dict) for leg in source_legs):
        raise ValueError("The broker order's original legs could not be verified.")
    for leg in source_legs:
        symbol = str(leg.get("symbol") or "").strip()
        action = " ".join(str(leg.get("action") or "").replace("-", " ").upper().split())
        if symbol in actual or _number(leg.get("quantity")) != trade["quantity"]:
            raise ValueError("The broker order's exact quantity could not be verified.")
        fills = leg.get("fills") or []
        if not isinstance(fills, list) or any(not isinstance(fill, dict) for fill in fills):
            raise ValueError("Invalid fill evidence.")
        if fills:
            quantities = [_number(fill.get("quantity")) for fill in fills]
            if any(q is None or q <= 0 for q in quantities) or sum(quantities) != trade["quantity"]:
                raise ValueError("Exact filled quantities could not be verified.")
        actual[symbol] = action
    if actual != expected:
        raise ValueError("The broker order does not match this journal's original legs.")
    price = (_opening_fill_credit if opening else _closing_exit_debit)(order)
    expected_price = trade["entry_fill_credit" if opening else "exit_debit"]
    # Only a terminal/fill timestamp proves execution time. Receipt, creation,
    # or a generic update timestamp is not a substitute for an actual fill.
    raw_times = [fill.get("filled-at") for leg in source_legs for fill in (leg.get("fills") or [])]
    if not raw_times:
        raw_times = [order.get("terminal-at")]
    try:
        times = [datetime.fromisoformat(str(value).replace("Z", "+00:00")) for value in raw_times]
        if any(value.tzinfo is None for value in times):
            raise ValueError()
        timestamp = max(times)
    except (ValueError, TypeError):
        raise ValueError("An aware actual fill timestamp is required.") from None
    if _number(price) is None or abs(price - expected_price) > 0.005 or timestamp is None:
        raise ValueError("The broker order's actual fill value/time could not be verified.")
    return _utc(timestamp)


def _row(audit, now):
    fields = [
        "status", "underlying", "expiration", "closed_at", "tracking_started_at", "actual_gross_pnl", "actual_net_pnl",
        "entry_costs", "actual_exit_costs", "hypothetical_exit_costs", "cost_basis", "latest_hypothetical_net_pnl",
        "latest_conservative_net_pnl", "best_hypothetical_net_pnl", "worst_hypothetical_net_pnl", "first_breakeven_at",
        "first_profit_at", "valid_samples", "attempted_samples", "last_attempt_at", "last_observed_at", "last_reason",
        "max_observation_gap_seconds", "settlement_status", "expiration_hypothetical_net_pnl",
    ]
    result = {"id": str(audit.id), "journal_id": str(audit.journal_id), "attribution": audit.attribution}
    for field in fields:
        value = getattr(audit, field)
        result[field] = (_utc(value).isoformat() if isinstance(value, datetime) else value.isoformat()) if hasattr(value, "isoformat") else value
    observation_end = min(now, _utc(audit.expires_at))
    latest = _utc(audit.last_observed_at or audit.tracking_started_at)
    result["current_observation_gap_seconds"] = max(0, int((observation_end - latest).total_seconds()))
    result["unobserved_before_tracking_seconds"] = max(0, int((_utc(audit.tracking_started_at) - _utc(audit.closed_at)).total_seconds()))
    result["sample_interval_seconds"] = SAMPLE_INTERVAL_SECONDS
    result["scope"] = "RTH_ONLY_SAMPLED_MIDPOINTS"
    return result


def enroll_stop_audit(*, journal_id, user_context, broker_client, confirm_stop_out, entry_costs, actual_exit_costs, hypothetical_exit_costs, session_factory=None, now=None):
    if not stop_audit_enabled():
        raise ValueError("Stop Audit collection is disabled.")
    if confirm_stop_out is not True:
        raise ValueError("Explicit stop-out confirmation is required.")
    user_id = _identity(user_context)
    now = _now(now)
    costs = [_number(value) for value in (entry_costs, actual_exit_costs, hypothetical_exit_costs)]
    if any(value is None or value < 0 or value > 1_000_000 for value in costs):
        raise ValueError("Enter each estimated cost as a finite, nonnegative dollar total.")
    try:
        journal_id = uuid.UUID(str(journal_id))
    except ValueError:
        raise ValueError("Trade unavailable.") from None
    with _factory(session_factory)() as session:
        journal = session.scalar(select(TradeJournal).where(TradeJournal.id == journal_id, TradeJournal.user_id == user_id).with_for_update())
        if journal is None:
            raise PermissionError("Trade unavailable.")
        existing = session.scalar(select(StopAudit).where(StopAudit.journal_id == journal_id, StopAudit.user_id == user_id))
        if existing:
            return _row(existing, now)
        trade, cutoff = _trade_snapshot(journal, now)
        account, fingerprint = _broker_identity(broker_client, user_id)
        opening = broker_client.get_order(trade["broker_order_id"], account_number=account)
        closing = broker_client.get_order(trade["closing_broker_order_id"], account_number=account)
        opened_at = _verify_order(opening, trade["broker_order_id"], trade, opening=True, account=account)
        closed_at = _verify_order(closing, trade["closing_broker_order_id"], trade, opening=False, account=account)
        if opened_at > closed_at or closed_at > now or abs((closed_at - _utc(journal.closed_at)).total_seconds()) > 1:
            raise ValueError("Actual opening/closing timestamps do not reconcile.")
        audit = StopAudit(
            journal_id=journal.id, user_id=user_id, broker_name="tastytrade", account_fingerprint=fingerprint,
            underlying="SPXW", expiration=journal.expiration, expires_at=cutoff, closed_at=closed_at,
            tracking_started_at=now, original_trade=trade, actual_gross_pnl=journal.realized_pnl,
            actual_net_pnl=round(journal.realized_pnl - costs[0] - costs[1], 2),
            entry_costs=costs[0], actual_exit_costs=costs[1], hypothetical_exit_costs=costs[2],
            last_reason="AWAITING_FIRST_OBSERVATION",
        )
        session.add(audit)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # SQLite does not enforce SELECT FOR UPDATE. The database unique
            # key is the final arbiter for concurrent enrollment/retries.
            existing = session.scalar(select(StopAudit).where(StopAudit.journal_id == journal_id, StopAudit.user_id == user_id))
            if existing is None:
                raise
            return _row(existing, now)
        return _row(audit, now)


def get_stop_audits(*, user_context, session_factory=None, now=None):
    user_id = _identity(user_context)
    now = _now(now)
    with _factory(session_factory)() as session:
        audits = session.scalars(select(StopAudit).where(StopAudit.user_id == user_id).order_by(StopAudit.tracking_started_at.desc()).limit(100)).all()
        enrolled = select(StopAudit.journal_id).where(StopAudit.user_id == user_id)
        journals = session.scalars(select(TradeJournal).where(
            TradeJournal.user_id == user_id, TradeJournal.status == "CLOSED", TradeJournal.id.not_in(enrolled),
            TradeJournal.expiration >= now.astimezone(EASTERN).date(),
        ).order_by(TradeJournal.closed_at.desc()).limit(100)).all()
        candidates = []
        for journal in journals:
            try:
                _trade_snapshot(journal, now)
                eligible, reason = True, "Confirm whether this was a stop-out; broker/account verification follows."
            except ValueError as exc:
                eligible, reason = False, str(exc)
            candidates.append({
                "journal_id": str(journal.id), "underlying": journal.underlying,
                "expiration": journal.expiration.isoformat(), "closed_at": _utc(journal.closed_at).isoformat() if journal.closed_at else None,
                "realized_pnl": journal.realized_pnl, "entry_fill_credit": journal.entry_fill_credit,
                "exit_debit": journal.exit_debit, "quantity": journal.quantity, "eligible": eligible, "reason": reason,
            })
        return {"enabled": stop_audit_enabled(), "audits": [_row(audit, now) for audit in audits], "candidates": candidates}


def evaluate_quotes(audit, quotes, now):
    """No receipt-time substitute, stale close fallback, or missing-as-zero marks."""
    now = _now(now)
    invalid = lambda reason: {"status": "UNAVAILABLE", "reason": reason}
    if not isinstance(quotes, list):
        return invalid("QUOTES_UNAVAILABLE")
    by_symbol = {}
    for quote in quotes:
        if not isinstance(quote, dict):
            return invalid("INVALID_QUOTE_PAYLOAD")
        symbol = str(quote.get("symbol") or quote.get("instrument-symbol") or "").strip()
        if symbol in by_symbol:
            return invalid("DUPLICATE_QUOTE_SYMBOL")
        by_symbol[symbol] = quote
    midpoint = conservative = 0.0
    timestamps, evidence = [], []
    for leg in audit.original_trade["legs"]:
        quote = by_symbol.get(leg["symbol"])
        if not quote:
            return invalid("MISSING_LEG_QUOTE")
        halt_keys = ("is-trading-halted", "trading-halted", "tradingHalted", "isTradingHalted", "halted", "halt")
        if any(str(quote[key]).lower() not in {"false", "0", "none", ""} for key in halt_keys if key in quote):
            return invalid("TRADING_HALTED")
        raw_time = quote.get("updated-at")
        try:
            stamp = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                return invalid("QUOTE_TIMESTAMP_MISSING")
            stamp = stamp.astimezone(UTC)
        except (TypeError, ValueError):
            return invalid("QUOTE_TIMESTAMP_MISSING")
        if stamp >= _utc(audit.expires_at):
            return invalid("QUOTE_AFTER_EXPIRATION")
        age = (now - stamp).total_seconds()
        if age < -5 or age > MAX_QUOTE_AGE_SECONDS or stamp < _utc(audit.tracking_started_at):
            return invalid("QUOTE_STALE_OR_OUTSIDE_TRACKING")
        bid, ask = _number(quote.get("bid")), _number(quote.get("ask"))
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            return invalid("INVALID_BID_ASK")
        mid = (bid + ask) / 2
        if not assess_quote_quality(bid, ask, mid)["quote_reliable"]:
            return invalid("WIDE_OR_ONE_SIDED_QUOTE")
        sign = 1 if leg["action"] == "SELL" else -1
        midpoint += sign * mid
        conservative += ask if sign == 1 else -bid
        timestamps.append(stamp)
        evidence.append({"symbol": leg["symbol"], "bid": bid, "ask": ask, "updated_at": stamp.isoformat()})
    if (max(timestamps) - min(timestamps)).total_seconds() > MAX_QUOTE_SKEW_SECONDS:
        return invalid("ASYNCHRONOUS_LEG_QUOTES")
    if midpoint < 0 or midpoint > audit.original_trade["maximum_debit"]:
        return invalid("INCONSISTENT_COMBO_MARK")
    def net(debit):
        return round((audit.original_trade["entry_fill_credit"] - debit) * 100 * audit.original_trade["quantity"] - audit.entry_costs - audit.hypothetical_exit_costs, 2)
    return {
        "status": "VALID", "reason": "SAMPLED_MIDPOINT_ESTIMATE", "quote_start_at": min(timestamps), "quote_end_at": max(timestamps),
        "midpoint_debit": round(midpoint, 6), "conservative_debit": round(conservative, 6),
        "hypothetical_net_pnl": net(midpoint), "conservative_net_pnl": net(conservative), "quote_evidence": evidence,
    }


def sample_stop_audit(*, audit_id, broker_client, session_factory=None, now=None):
    fixed_now = now is not None
    now = _now(now)
    factory = _factory(session_factory)
    bucket = int(now.timestamp()) // SAMPLE_INTERVAL_SECONDS
    with factory() as session:
        audit = session.scalar(select(StopAudit).where(StopAudit.id == uuid.UUID(str(audit_id))).with_for_update())
        if audit is None or audit.status != "TRACKING":
            return {"sampled": False, "reason": "NOT_TRACKING"}
        if now >= _utc(audit.expires_at):
            audit.status = "AWAITING_SETTLEMENT"
            audit.settlement_status = "UNAVAILABLE_VERIFIED_SOURCE_REQUIRED"
            audit.last_reason = "EXPIRED_NO_VERIFIED_SETTLEMENT"
            session.commit()
            return {"sampled": False, "reason": audit.last_reason}
        if not _session_open(now):
            return {"sampled": False, "reason": "OUTSIDE_REGULAR_SESSION"}
        if session.scalar(select(StopAuditSample.id).where(StopAuditSample.audit_id == audit.id, StopAuditSample.minute_bucket == bucket)):
            return {"sampled": False, "reason": "ALREADY_SAMPLED_MINUTE"}
        sample = StopAuditSample(audit_id=audit.id, minute_bucket=bucket, attempted_at=now, status="UNAVAILABLE", reason="ATTEMPT_INTERRUPTED")
        session.add(sample)
        gap = max(0, int((now - _utc(audit.last_observed_at or audit.tracking_started_at)).total_seconds()))
        latest_attempt = or_(StopAudit.last_attempt_at.is_(None), StopAudit.last_attempt_at <= now)
        try:
            session.execute(update(StopAudit).where(StopAudit.id == audit.id).values(
                attempted_samples=StopAudit.attempted_samples + 1,
                last_attempt_at=case((latest_attempt, now), else_=StopAudit.last_attempt_at),
                last_reason=case((latest_attempt, "ATTEMPT_IN_PROGRESS"), else_=StopAudit.last_reason),
                max_observation_gap_seconds=case((StopAudit.max_observation_gap_seconds < gap, gap), else_=StopAudit.max_observation_gap_seconds),
            ).execution_options(synchronize_session=False))
            session.commit()
        except IntegrityError:
            session.rollback()
            return {"sampled": False, "reason": "ALREADY_SAMPLED_MINUTE"}
        sample_id = sample.id
        # The attempt is durable before any network request. A crash is a gap,
        # never a zero quote. One unique UTC-minute row prevents duplicate marks.
        try:
            if broker_client is None:
                result = {"status": "UNAVAILABLE", "reason": "BROKER_CONNECTION_UNAVAILABLE"}
            else:
                _, fingerprint = _broker_identity(broker_client, audit.user_id)
                if fingerprint != audit.account_fingerprint:
                    result = {"status": "UNAVAILABLE", "reason": "BROKER_ACCOUNT_CHANGED"}
                else:
                    quotes = broker_client.get_option_quotes([leg["symbol"] for leg in audit.original_trade["legs"]])
                    received_at = now if fixed_now else _now()
                    if received_at >= _utc(audit.expires_at):
                        result = {"status": "UNAVAILABLE", "reason": "RESPONSE_AFTER_EXPIRATION"}
                    else:
                        result = evaluate_quotes(audit, quotes, received_at)
                    now = received_at
        except Exception:
            result = {"status": "UNAVAILABLE", "reason": "QUOTE_COLLECTION_FAILED"}
    with factory() as session:
        audit = session.scalar(select(StopAudit).where(StopAudit.id == uuid.UUID(str(audit_id))).with_for_update())
        sample = session.get(StopAuditSample, sample_id)
        for key, value in result.items():
            setattr(sample, key, value)
        # Use atomic SQL expressions as well as row locks: SQLite ignores
        # FOR UPDATE, and overlapping different-minute samples must not lose
        # counters/extrema or rewind the latest mark on any supported database.
        updates = {}
        if result["status"] == "VALID":
            value = result["hypothetical_net_pnl"]
            latest_observation = or_(StopAudit.last_observed_at.is_(None), StopAudit.last_observed_at < now)
            updates.update(
                valid_samples=StopAudit.valid_samples + 1,
                best_hypothetical_net_pnl=case((or_(StopAudit.best_hypothetical_net_pnl.is_(None), StopAudit.best_hypothetical_net_pnl < value), value), else_=StopAudit.best_hypothetical_net_pnl),
                worst_hypothetical_net_pnl=case((or_(StopAudit.worst_hypothetical_net_pnl.is_(None), StopAudit.worst_hypothetical_net_pnl > value), value), else_=StopAudit.worst_hypothetical_net_pnl),
                latest_hypothetical_net_pnl=case((latest_observation, value), else_=StopAudit.latest_hypothetical_net_pnl),
                latest_conservative_net_pnl=case((latest_observation, result["conservative_net_pnl"]), else_=StopAudit.latest_conservative_net_pnl),
                last_observed_at=case((latest_observation, now), else_=StopAudit.last_observed_at),
            )
            if value >= 0:
                updates["first_breakeven_at"] = case((or_(StopAudit.first_breakeven_at.is_(None), StopAudit.first_breakeven_at > now), now), else_=StopAudit.first_breakeven_at)
            if value > 0:
                updates["first_profit_at"] = case((or_(StopAudit.first_profit_at.is_(None), StopAudit.first_profit_at > now), now), else_=StopAudit.first_profit_at)
        if now >= _utc(audit.expires_at):
            updates["status"] = "AWAITING_SETTLEMENT"
            updates["settlement_status"] = "UNAVAILABLE_VERIFIED_SOURCE_REQUIRED"
        updates["last_reason"] = case((StopAudit.last_attempt_at <= now, result["reason"]), else_=StopAudit.last_reason)
        session.execute(update(StopAudit).where(StopAudit.id == audit.id).values(**updates).execution_options(synchronize_session=False))
        session.commit()
        session.refresh(audit)
        return {"sampled": True, "reason": result["reason"], "audit": _row(audit, now)}



def run_stop_audit_check(*, session_factory=None, now=None, broker_resolver=None):
    if not stop_audit_enabled() or (session_factory is None and not database_configured()):
        return {"checked": 0, "reason": "DISABLED_OR_DATABASE_UNAVAILABLE"}
    factory = _factory(session_factory)
    fixed_now = now
    if broker_resolver is None:
        from bxk_app.services.broker_connection_service import resolve_broker
        broker_resolver = resolve_broker
    with factory() as session:
        audits = session.scalars(select(StopAudit).where(StopAudit.status == "TRACKING").order_by(StopAudit.last_attempt_at.asc().nullsfirst()).limit(100)).all()
        targets = [(audit.id, audit.user_id, audit.broker_name) for audit in audits]
    clients = {}
    checked = 0
    for audit_id, user_id, broker_name in targets:
        key = (user_id, broker_name)
        if key not in clients:
            clients[key] = None
            try:
                with factory() as session:
                    user = session.get(User, user_id)
                    role = getattr(user.role, "value", user.role) if user else None
                    if user and user.is_active and role in {"OWNER", "BETA"}:
                        clients[key] = broker_resolver(session, user_context={"user_id": str(user_id), "role": role}, broker_name=broker_name)
            except Exception:
                pass
        try:
            sample_stop_audit(audit_id=audit_id, broker_client=clients[key], session_factory=factory, now=fixed_now)
            checked += 1
        except Exception:
            logger.warning("Stop Audit observation unavailable for an enrolled trade.")
    return {"checked": checked}


async def run_stop_audit_monitor():
    """Restart-safe one-minute poller; requires no browser tab to remain open."""
    while True:
        try:
            if not os.getenv("PYTEST_CURRENT_TEST"):
                await asyncio.to_thread(run_stop_audit_check)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Stop Audit monitor temporarily unavailable.")
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
