"""Fail-closed tests for the observation-only stopped-trade audit."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app.database import Base
from bxk_app.db_models.stop_audit import StopAudit, StopAuditSample
from bxk_app.db_models.trade_journal import TradeJournal
from bxk_app.db_models.user import User, UserRole
import bxk_app.services.stop_audit_service as service


UTC = timezone.utc
OPENED = datetime(2026, 9, 29, 14, 0, tzinfo=UTC)
CLOSED = datetime(2026, 9, 29, 15, 59, tzinfo=UTC)
STARTED = datetime(2026, 9, 29, 16, 0, tzinfo=UTC)
OBSERVED = STARTED + timedelta(minutes=1)
EXPIRATION = date(2026, 9, 30)
ACCOUNT = "TEST-ACCOUNT-1"


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def option_symbol(kind, strike, expiration=EXPIRATION, root="SPXW"):
    return f"{root:<6}{expiration:%y%m%d}{kind}{strike * 1000:08d}"


def condor_order():
    return {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "quantity": 2,
        "limit_price": 3.0,
        "expiration": EXPIRATION.isoformat(),
        "dte": 1,
        "wing_width": 25,
        "legs": [
            {"action": "SELL", "option_type": "PUT", "strike": 6500,
             "symbol": option_symbol("P", 6500)},
            {"action": "BUY", "option_type": "PUT", "strike": 6475,
             "symbol": option_symbol("P", 6475)},
            {"action": "SELL", "option_type": "CALL", "strike": 6650,
             "symbol": option_symbol("C", 6650)},
            {"action": "BUY", "option_type": "CALL", "strike": 6675,
             "symbol": option_symbol("C", 6675)},
        ],
    }


def filled_order(*, closing=False):
    actions = ({"SELL": "Buy to Close", "BUY": "Sell to Close"}
               if closing else {"SELL": "Sell to Open", "BUY": "Buy to Open"})
    return {
        "id": "CLOSE-1" if closing else "OPEN-1",
        "account-number": ACCOUNT,
        "status": "Filled",
        "price-effect": "Debit" if closing else "Credit",
        "average-fill-price": "6.00" if closing else "3.00",
        "terminal-at": iso(CLOSED if closing else OPENED),
        "legs": [
            {"symbol": leg["symbol"], "action": actions[leg["action"]],
             "quantity": "2", "instrument-type": "Equity Option"}
            for leg in condor_order()["legs"]
        ],
    }


def good_quotes(at=OBSERVED):
    return [
        {"symbol": leg["symbol"],
         "bid": "1.00" if leg["action"] == "SELL" else "0.20",
         "ask": "1.20" if leg["action"] == "SELL" else "0.40",
         "updated-at": iso(at)}
        for leg in condor_order()["legs"]
    ]


class ReadOnlyBroker:
    """Only explicitly allowed observational broker methods exist."""

    broker_name = "tastytrade"

    def __init__(self):
        self.account_number = ACCOUNT
        self.orders = {"OPEN-1": filled_order(), "CLOSE-1": filled_order(closing=True)}
        self.quotes = good_quotes()
        self.order_reads = []
        self.quote_reads = []

    def get_first_account_number(self):
        return self.account_number

    def get_default_account_number(self):
        return self.account_number

    def get_order(self, order_id, account_number=None):
        self.order_reads.append((order_id, account_number))
        return deepcopy(self.orders.get(order_id))

    def get_option_quotes(self, symbols):
        self.quote_reads.append(list(symbols))
        return deepcopy(self.quotes)

    def __getattr__(self, name):
        if any(word in name for word in ("submit", "cancel", "replace", "preview", "dry_run")):
            raise AssertionError(f"Stop Audit must never access broker action {name}")
        raise AttributeError(name)


def make_factory(url="sqlite+pysqlite:///:memory:"):
    kwargs = {"connect_args": {"check_same_thread": False}}
    if url.endswith(":memory:"):
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def add_user(factory, username="audit_owner"):
    user_id = uuid.uuid4()
    with factory() as session:
        session.add(User(id=user_id, username=username, email=f"{username}@example.com",
                         password_hash="unused", role=UserRole.BETA, is_active=True))
        session.commit()
    return user_id


def add_journal(factory, user_id, **changes):
    values = {
        "id": uuid.uuid4(), "user_id": user_id, "broker_order_id": "OPEN-1",
        "closing_broker_order_id": "CLOSE-1", "status": "CLOSED",
        "broker_status": "Filled", "strategy": "SPX Iron Condor", "underlying": "SPX",
        "expiration": EXPIRATION, "quantity": 2, "wing_width": 25,
        "short_put": 6500, "long_put": 6475, "short_call": 6650, "long_call": 6675,
        "entry_fill_credit": 3.0, "exit_debit": 6.0, "realized_pnl": -600.0,
        "opened_at": OPENED, "closed_at": CLOSED,
        "entry_snapshot": {"order": condor_order()}, "close_snapshot": filled_order(closing=True),
    }
    values.update(changes)
    with factory() as session:
        session.add(TradeJournal(**values))
        session.commit()
    return values["id"]


@pytest.fixture
def setup(monkeypatch):
    factory = make_factory()
    user_id = add_user(factory)
    monkeypatch.setattr(service, "database_configured", lambda: True)
    return SimpleNamespace(factory=factory, user_id=user_id,
                           context={"user_id": str(user_id), "role": "BETA"},
                           journal_id=add_journal(factory, user_id), broker=ReadOnlyBroker())


def enroll(setup, **changes):
    args = dict(journal_id=str(setup.journal_id), user_context=setup.context,
                broker_client=setup.broker, confirm_stop_out=True, entry_costs=8.0,
                actual_exit_costs=4.0, hypothetical_exit_costs=6.0,
                session_factory=setup.factory, now=STARTED)
    args.update(changes)
    return service.enroll_stop_audit(**args)


def only_audit(setup):
    with setup.factory() as session:
        return session.execute(select(StopAudit)).scalar_one()


def samples(setup):
    with setup.factory() as session:
        return list(session.scalars(select(StopAuditSample).order_by(StopAuditSample.minute_bucket)))


def sample(setup, at=OBSERVED):
    return service.sample_stop_audit(audit_id=str(only_audit(setup).id),
                                    broker_client=setup.broker,
                                    session_factory=setup.factory, now=at)


def update_journal(setup, **changes):
    with setup.factory() as session:
        row = session.get(TradeJournal, setup.journal_id)
        for key, value in changes.items():
            setattr(row, key, value)
        session.commit()


def test_enrollment_preserves_real_loss_and_freezes_original_trade(setup):
    enroll(setup)
    row = only_audit(setup)
    assert row.user_id == setup.user_id
    assert row.journal_id == setup.journal_id
    assert row.status == "TRACKING"
    assert row.actual_gross_pnl == -600
    assert row.actual_net_pnl == -612
    assert row.latest_hypothetical_net_pnl is None
    assert row.first_profit_at is None
    assert row.valid_samples == row.attempted_samples == 0
    assert row.original_trade
    frozen = deepcopy(row.original_trade)
    update_journal(setup, entry_fill_credit=99, realized_pnl=9999)
    assert only_audit(setup).original_trade == frozen
    assert only_audit(setup).actual_net_pnl == -612
    assert set(setup.broker.order_reads) == {("OPEN-1", ACCOUNT), ("CLOSE-1", ACCOUNT)}


def test_duplicate_enrollment_is_idempotent_and_does_not_reset_history(setup):
    enroll(setup)
    sample(setup)
    before = only_audit(setup)
    enroll(setup, now=OBSERVED + timedelta(minutes=1), entry_costs=99)
    after = only_audit(setup)
    assert after.id == before.id
    assert after.entry_costs == before.entry_costs == 8
    assert after.tracking_started_at == before.tracking_started_at
    assert after.valid_samples == before.valid_samples == 1
    assert len(samples(setup)) == 1


def test_stop_confirmation_is_required(setup):
    with pytest.raises(ValueError):
        enroll(setup, confirm_stop_out=False)
    with setup.factory() as session:
        assert session.scalar(select(StopAudit)) is None


@pytest.mark.parametrize("field", ["entry_costs", "actual_exit_costs", "hypothetical_exit_costs"])
@pytest.mark.parametrize("value", [None, -0.01, float("nan"), float("inf"), float("-inf")])
def test_costs_must_be_explicit_finite_nonnegative_totals(setup, field, value):
    with pytest.raises(ValueError):
        enroll(setup, **{field: value})


@pytest.mark.parametrize("context", [{}, {"user_id": "not-a-uuid", "role": "OWNER"},
                                     {"user_id": str(uuid.UUID(int=42)), "role": "OWNER"}])
def test_unowned_or_other_users_journal_cannot_be_enrolled(setup, context):
    with pytest.raises(PermissionError):
        enroll(setup, user_context=context)
    assert setup.broker.order_reads == []


def test_legacy_null_owner_is_never_adopted_even_by_owner(setup):
    update_journal(setup, user_id=None)
    with pytest.raises(PermissionError):
        enroll(setup, user_context={"user_id": str(setup.user_id), "role": "OWNER"})
    with setup.factory() as session:
        assert session.get(TradeJournal, setup.journal_id).user_id is None
        assert session.scalar(select(StopAudit)) is None


@pytest.mark.parametrize("changes", [
    {"status": "OPEN"}, {"status": "SUBMITTED"}, {"status": "EXPIRED"},
    {"closed_at": None}, {"closing_broker_order_id": None},
    {"entry_fill_credit": None}, {"exit_debit": None}, {"realized_pnl": None},
    {"quantity": 0}, {"underlying": "SPY"},
    {"entry_snapshot": None},
])
def test_ineligible_journal_is_rejected(setup, changes):
    update_journal(setup, **changes)
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("order_id", ["OPEN-1", "CLOSE-1"])
@pytest.mark.parametrize("changes", [
    {"account-number": "SOMEONE-ELSE"}, {"status": "Partially Filled"},
    {"average-fill-price": None}, {"terminal-at": None}, {"id": "WRONG-ORDER"},
])
def test_broker_fill_evidence_must_match_exact_owned_orders(setup, order_id, changes):
    setup.broker.orders[order_id].update(changes)
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("order_id", ["OPEN-1", "CLOSE-1"])
@pytest.mark.parametrize("field,value", [("quantity", "1"), ("symbol", "WRONG-SYMBOL"),
                                          ("action", "Buy to Open")])
def test_partial_or_mismatched_fill_legs_are_rejected(setup, order_id, field, value):
    setup.broker.orders[order_id]["legs"][0][field] = value
    with pytest.raises(ValueError):
        enroll(setup)


def test_unsupported_broker_is_rejected(setup):
    setup.broker.broker_name = "other-broker"
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("mutation", ["vertical", "duplicate_leg", "am_settlement", "mixed_expiry",
                                       "reverse_wing", "unequal_ratio", "missing_symbol"])
def test_only_original_pm_settled_one_to_one_condors_are_eligible(setup, mutation):
    order = condor_order()
    if mutation == "vertical":
        order["legs"] = order["legs"][:2]
    elif mutation == "duplicate_leg":
        order["legs"][3] = deepcopy(order["legs"][2])
    elif mutation == "am_settlement":
        order["legs"][0]["symbol"] = option_symbol("P", 6500, root="SPX")
    elif mutation == "mixed_expiry":
        order["legs"][0]["symbol"] = option_symbol("P", 6500, expiration=date(2026, 10, 1))
    elif mutation == "reverse_wing":
        order["legs"][1]["symbol"] = option_symbol("P", 6550)
    elif mutation == "unequal_ratio":
        order["legs"][0]["quantity"] = 2
    elif mutation == "missing_symbol":
        order["legs"][0].pop("symbol")
    update_journal(setup, entry_snapshot={"order": order})
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("order_id", ["OPEN-1", "CLOSE-1"])
def test_broker_prices_must_reconcile_with_the_actual_journal(setup, order_id):
    setup.broker.orders[order_id]["average-fill-price"] = "9.99"
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("order_id", ["OPEN-1", "CLOSE-1"])
@pytest.mark.parametrize("field", ["received-at", "created-at"])
def test_order_creation_times_are_not_accepted_as_fill_times(setup, order_id, field):
    order = setup.broker.orders[order_id]
    order[field] = order.pop("terminal-at")
    with pytest.raises(ValueError):
        enroll(setup)


@pytest.mark.parametrize("order_id", ["OPEN-1", "CLOSE-1"])
def test_broker_fill_times_require_explicit_timezone(setup, order_id):
    order = setup.broker.orders[order_id]
    order["terminal-at"] = order["terminal-at"].removesuffix("Z")
    with pytest.raises(ValueError):
        enroll(setup)


def test_valid_midpoint_sample_accounts_for_quantity_and_costs(setup):
    enroll(setup)
    sample(setup)
    row = only_audit(setup)
    point = samples(setup)[0]
    assert point.status == "VALID"
    assert point.midpoint_debit == pytest.approx(1.6)
    assert point.conservative_debit == pytest.approx(2.0)
    assert point.hypothetical_net_pnl == pytest.approx(266)
    assert point.conservative_net_pnl == pytest.approx(186)
    assert row.latest_hypothetical_net_pnl == pytest.approx(266)
    assert row.actual_net_pnl == -612
    assert row.best_hypothetical_net_pnl == row.worst_hypothetical_net_pnl == 266
    assert row.valid_samples == row.attempted_samples == 1
    assert row.first_profit_at is not None
    with setup.factory() as session:
        journal = session.get(TradeJournal, setup.journal_id)
        assert journal.status == "CLOSED"
        assert journal.realized_pnl == -600
        assert journal.exit_debit == 6


def test_sampling_same_utc_minute_is_persistently_idempotent(setup):
    enroll(setup)
    sample(setup)
    sample(setup, at=OBSERVED + timedelta(seconds=59))
    assert len(samples(setup)) == 1
    assert only_audit(setup).attempted_samples == 1
    assert len(setup.broker.quote_reads) == 1


def test_process_restart_preserves_marks_and_minute_deduplication(setup, tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'stop-audit.sqlite'}"
    setup.factory = make_factory(url)
    setup.user_id = add_user(setup.factory)
    setup.context["user_id"] = str(setup.user_id)
    setup.journal_id = add_journal(setup.factory, setup.user_id)
    enroll(setup)
    sample(setup)
    audit_id = only_audit(setup).id
    setup.factory.kw["bind"].dispose()
    setup.factory = make_factory(url)
    setup.broker = ReadOnlyBroker()
    sample(setup, at=OBSERVED + timedelta(seconds=30))
    assert only_audit(setup).id == audit_id
    assert only_audit(setup).attempted_samples == 1
    assert only_audit(setup).latest_hypothetical_net_pnl == 266
    assert setup.broker.quote_reads == []
    later = OBSERVED + timedelta(minutes=1)
    setup.broker.quotes = good_quotes(later)
    sample(setup, at=later)
    assert only_audit(setup).attempted_samples == 2
    assert len(samples(setup)) == 2


def test_interrupted_attempt_is_durable_and_does_not_resample_the_minute(setup, monkeypatch):
    enroll(setup)
    def interrupted(symbols):
        raise SystemExit("Simulated process interruption, not a quote")
    monkeypatch.setattr(setup.broker, "get_option_quotes", interrupted)
    with pytest.raises(SystemExit):
        sample(setup)
    assert len(samples(setup)) == 1
    assert samples(setup)[0].reason == "ATTEMPT_INTERRUPTED"
    assert only_audit(setup).first_profit_at is None
    assert only_audit(setup).latest_hypothetical_net_pnl is None
    sample(setup, at=OBSERVED + timedelta(seconds=30))
    assert only_audit(setup).attempted_samples == 1


@pytest.mark.parametrize("mutation", [
    "missing_leg", "missing_bid", "missing_ask", "zero_bid", "crossed",
    "cheap_zero_bid", "negative_bid", "nan_bid", "infinite_ask", "missing_timestamp", "naive_timestamp",
    "old_timestamp", "future_timestamp", "before_tracking", "leg_skew", "halted",
])
def test_unreliable_quotes_never_create_zero_or_first_profit(setup, mutation):
    enroll(setup)
    quotes = setup.broker.quotes
    if mutation == "missing_leg":
        quotes.pop()
    elif mutation == "missing_bid":
        quotes[0].pop("bid")
    elif mutation == "missing_ask":
        quotes[0].pop("ask")
    elif mutation == "zero_bid":
        quotes[0]["bid"] = "0"
    elif mutation == "cheap_zero_bid":
        quotes[1].update(bid="0", ask="0.10")
    elif mutation == "crossed":
        quotes[0].update(bid="2", ask="1")
    elif mutation == "negative_bid":
        quotes[0]["bid"] = "-1"
    elif mutation == "nan_bid":
        quotes[0]["bid"] = "nan"
    elif mutation == "infinite_ask":
        quotes[0]["ask"] = "inf"
    elif mutation == "missing_timestamp":
        quotes[0].pop("updated-at")
    elif mutation == "naive_timestamp":
        quotes[0]["updated-at"] = OBSERVED.replace(tzinfo=None).isoformat()
    elif mutation == "old_timestamp":
        for quote in quotes:
            quote["updated-at"] = iso(OBSERVED - timedelta(seconds=91))
    elif mutation == "future_timestamp":
        for quote in quotes:
            quote["updated-at"] = iso(OBSERVED + timedelta(seconds=6))
    elif mutation == "before_tracking":
        for quote in quotes:
            quote["updated-at"] = iso(STARTED - timedelta(seconds=1))
    elif mutation == "leg_skew":
        quotes[0]["updated-at"] = iso(OBSERVED - timedelta(seconds=31))
    elif mutation == "halted":
        quotes[0]["halted"] = True
    sample(setup)
    row = only_audit(setup)
    point = samples(setup)[0]
    assert point.status != "VALID"
    assert point.reason
    assert point.hypothetical_net_pnl is None
    assert point.midpoint_debit is None
    assert row.latest_hypothetical_net_pnl is None
    assert row.first_profit_at is None
    assert row.first_breakeven_at is None
    assert row.valid_samples == 0
    assert row.attempted_samples == 1


def test_observation_gap_is_recorded_without_interpolating_profit(setup):
    enroll(setup)
    setup.broker.quotes = []
    sample(setup)
    later = OBSERVED + timedelta(minutes=10)
    setup.broker.quotes = good_quotes(later)
    sample(setup, at=later)
    row = only_audit(setup)
    assert row.attempted_samples == 2
    assert row.valid_samples == 1
    assert row.max_observation_gap_seconds >= 600
    assert row.first_profit_at.replace(tzinfo=UTC) == later


def test_expiry_stops_quote_reads_and_never_assumes_zero_settlement(setup):
    enroll(setup)
    cutoff = service.expiry_cutoff(EXPIRATION)
    sample(setup, at=cutoff)
    sample(setup, at=cutoff + timedelta(minutes=1))
    row = only_audit(setup)
    assert row.status == "AWAITING_SETTLEMENT"
    assert row.expiration_hypothetical_net_pnl is None
    assert row.first_profit_at is None
    assert setup.broker.quote_reads == []


@pytest.mark.parametrize("expiration,expected", [
    (date(2026, 9, 30), datetime(2026, 9, 30, 20, 0, tzinfo=UTC)),
    (date(2026, 11, 27), datetime(2026, 11, 27, 18, 0, tzinfo=UTC)),
    (date(2026, 12, 24), datetime(2026, 12, 24, 18, 0, tzinfo=UTC)),
])
def test_spxw_expiry_uses_actual_regular_or_early_close(expiration, expected):
    assert service.expiry_cutoff(expiration) == expected


@pytest.mark.parametrize("expiration", [date(2026, 9, 26), date(2026, 12, 25)])
def test_nontrading_expiration_is_rejected(expiration):
    with pytest.raises(ValueError):
        service.expiry_cutoff(expiration)


def test_list_is_strictly_user_scoped_without_legacy_adoption(setup):
    enroll(setup)
    another = add_user(setup.factory, "other_user")
    result = service.get_stop_audits(user_context={"user_id": str(another), "role": "OWNER"},
                                    session_factory=setup.factory, now=OBSERVED)
    assert result["audits"] == []
    assert result["candidates"] == []
    own = service.get_stop_audits(user_context=setup.context,
                                 session_factory=setup.factory, now=OBSERVED)
    assert len(own["audits"]) == 1


def test_changed_broker_account_never_collects_quotes_or_records_profit(setup):
    enroll(setup)
    setup.broker.account_number = "DIFFERENT-ACCOUNT"
    sample(setup)
    assert setup.broker.quote_reads == []
    assert samples(setup)[0].reason == "BROKER_ACCOUNT_CHANGED"
    assert only_audit(setup).valid_samples == 0
    assert only_audit(setup).first_profit_at is None


def test_missing_broker_is_persisted_as_missing_data(setup):
    enroll(setup)
    service.sample_stop_audit(audit_id=str(only_audit(setup).id), broker_client=None,
                             session_factory=setup.factory, now=OBSERVED)
    assert samples(setup)[0].reason == "BROKER_CONNECTION_UNAVAILABLE"
    assert samples(setup)[0].hypothetical_net_pnl is None
    assert only_audit(setup).first_profit_at is None


def test_regular_session_only_without_fabricated_overnight_samples(setup):
    enroll(setup)
    before_open = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    result = sample(setup, at=before_open)
    assert result["sampled"] is False
    assert result["reason"] == "OUTSIDE_REGULAR_SESSION"
    assert setup.broker.quote_reads == []
    assert samples(setup) == []


def test_exact_net_breakeven_is_not_first_profit(setup):
    enroll(setup)
    for quote, leg in zip(setup.broker.quotes, condor_order()["legs"]):
        if leg["action"] == "SELL":
            quote.update(bid="1.70", ask="1.83")
    sample(setup)
    row = only_audit(setup)
    assert row.latest_hypothetical_net_pnl == 0
    assert row.first_breakeven_at is not None
    assert row.first_profit_at is None


def test_background_sampler_resolves_the_enrolled_users_own_account(setup):
    enroll(setup)
    resolutions = []
    def resolve(session, *, user_context, broker_name):
        resolutions.append((user_context, broker_name))
        return setup.broker
    result = service.run_stop_audit_check(session_factory=setup.factory,
                                         broker_resolver=resolve, now=OBSERVED)
    assert result["checked"] == 1
    assert resolutions == [(setup.context, "tastytrade")]
    assert only_audit(setup).valid_samples == 1


def test_background_sampler_has_no_fallback_for_inactive_users(setup):
    enroll(setup)
    with setup.factory() as session:
        session.get(User, setup.user_id).is_active = False
        session.commit()
    resolutions = []
    def forbidden_resolver(*args, **kwargs):
        resolutions.append((args, kwargs))
        return setup.broker
    service.run_stop_audit_check(session_factory=setup.factory,
                                broker_resolver=forbidden_resolver, now=OBSERVED)
    assert setup.broker.quote_reads == []
    assert resolutions == []
    assert only_audit(setup).valid_samples == 0
    assert samples(setup)[0].hypothetical_net_pnl is None


def test_disabled_collection_does_not_resolve_brokers_or_mutate_audits(setup, monkeypatch):
    enroll(setup)
    monkeypatch.setenv("BXK_STOP_AUDIT_ENABLED", "false")
    def forbidden_resolver(*args, **kwargs):
        raise AssertionError("Disabled collection must not resolve brokers")
    result = service.run_stop_audit_check(session_factory=setup.factory,
                                         broker_resolver=forbidden_resolver, now=OBSERVED)
    assert result["checked"] == 0
    assert samples(setup) == []
    result = service.get_stop_audits(user_context=setup.context,
                                    session_factory=setup.factory, now=OBSERVED)
    assert result["enabled"] is False
    assert len(result["audits"]) == 1


@pytest.mark.parametrize("use_runner", [False, True])
def test_freshness_is_checked_at_response_time_including_background_runs(setup, monkeypatch, use_runner):
    enroll(setup)
    clock = [OBSERVED]
    monkeypatch.setattr(service, "_now", lambda value=None: value if value is not None else clock[0])
    def slow_response(symbols):
        clock[0] += timedelta(seconds=95)
        return good_quotes(OBSERVED)
    monkeypatch.setattr(setup.broker, "get_option_quotes", slow_response)
    if use_runner:
        service.run_stop_audit_check(session_factory=setup.factory,
                                    broker_resolver=lambda *args, **kwargs: setup.broker)
    else:
        service.sample_stop_audit(audit_id=str(only_audit(setup).id), broker_client=setup.broker,
                                 session_factory=setup.factory)
    assert only_audit(setup).valid_samples == 0
    assert only_audit(setup).first_profit_at is None
    assert samples(setup)[0].hypothetical_net_pnl is None
    assert samples(setup)[0].reason == "QUOTE_STALE_OR_OUTSIDE_TRACKING"


def test_quote_returned_after_expiry_is_never_used_for_a_profit_event(setup, monkeypatch):
    enroll(setup)
    cutoff = service.expiry_cutoff(EXPIRATION)
    requested = cutoff - timedelta(seconds=5)
    clock = [requested]
    monkeypatch.setattr(service, "_now", lambda value=None: value if value is not None else clock[0])
    def late_response(symbols):
        clock[0] = cutoff + timedelta(seconds=3)
        return good_quotes(requested)
    monkeypatch.setattr(setup.broker, "get_option_quotes", late_response)
    service.run_stop_audit_check(session_factory=setup.factory,
                                broker_resolver=lambda *args, **kwargs: setup.broker)
    assert samples(setup)[0].reason == "RESPONSE_AFTER_EXPIRATION"
    assert samples(setup)[0].hypothetical_net_pnl is None
    assert only_audit(setup).first_profit_at is None
    service.run_stop_audit_check(session_factory=setup.factory,
                                broker_resolver=lambda *args, **kwargs: setup.broker)
    assert only_audit(setup).status == "AWAITING_SETTLEMENT"
    assert only_audit(setup).expiration_hypothetical_net_pnl is None


def test_source_quote_at_expiry_is_rejected_even_inside_clock_skew_tolerance(setup):
    enroll(setup)
    cutoff = service.expiry_cutoff(EXPIRATION)
    setup.broker.quotes = good_quotes(cutoff)
    sample(setup, at=cutoff - timedelta(seconds=2))
    assert samples(setup)[0].reason == "QUOTE_AFTER_EXPIRATION"
    assert only_audit(setup).first_profit_at is None


def test_christmas_eve_expiring_contract_stops_at_1300_eastern(setup):
    enroll(setup)
    cutoff = service.expiry_cutoff(date(2026, 12, 24))
    with setup.factory() as session:
        row = session.get(StopAudit, only_audit(setup).id)
        row.expiration = date(2026, 12, 24)
        row.expires_at = cutoff
        session.commit()
    sample(setup, at=datetime(2026, 12, 24, 18, 0, tzinfo=UTC))
    assert only_audit(setup).status == "AWAITING_SETTLEMENT"
    assert setup.broker.quote_reads == []


def test_new_migration_upgrades_matching_schema_and_downgrades_without_touching_journal(monkeypatch):
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path("alembic/versions/a12b34c56d78_create_stop_audits.py")
    spec = importlib.util.spec_from_file_location("stop_audit_test_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "a12b34c56d78"
    assert migration.down_revision == "f7c2a91e4d38"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    parents = sa.MetaData()
    sa.Table("users", parents, sa.Column("id", sa.Uuid(), primary_key=True))
    journal = sa.Table("trade_journals", parents, sa.Column("id", sa.Uuid(), primary_key=True))
    parents.create_all(engine)
    journal_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(journal.insert().values(id=journal_id))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = sa.inspect(connection)
        for model in (StopAudit, StopAuditSample):
            actual = {column["name"]: column for column in inspector.get_columns(model.__tablename__)}
            assert set(actual) == set(model.__table__.columns.keys())
            for column in model.__table__.columns:
                assert actual[column.name]["nullable"] == column.nullable
        audit_uniques = inspector.get_unique_constraints("stop_audits")
        sample_uniques = inspector.get_unique_constraints("stop_audit_samples")
        assert any(item["column_names"] == ["journal_id"] for item in audit_uniques)
        assert any(item["column_names"] == ["audit_id", "minute_bucket"] for item in sample_uniques)
        assert {tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys("stop_audits")} == {
            ("journal_id",), ("user_id",),
        }
        assert inspector.get_foreign_keys("stop_audit_samples")[0]["referred_table"] == "stop_audits"
        migration.downgrade()
        assert set(sa.inspect(connection).get_table_names()) == {"users", "trade_journals"}
        assert connection.execute(select(journal.c.id)).scalar_one() == journal_id


def test_concurrent_enrollment_returns_one_persisted_audit(setup, tmp_path):
    setup.factory = make_factory(f"sqlite+pysqlite:///{tmp_path / 'concurrent.sqlite'}")
    setup.user_id = add_user(setup.factory)
    setup.context["user_id"] = str(setup.user_id)
    setup.journal_id = add_journal(setup.factory, setup.user_id)
    barrier = Barrier(2)
    class ConcurrentBroker(ReadOnlyBroker):
        def get_order(self, order_id, account_number=None):
            result = super().get_order(order_id, account_number=account_number)
            if order_id == "CLOSE-1":
                barrier.wait(timeout=10)
            return result
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(enroll, setup, broker_client=ConcurrentBroker()) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert results[0]["id"] == results[1]["id"] == str(only_audit(setup).id)
    assert only_audit(setup).attempted_samples == 0


@pytest.mark.parametrize("field", ["trading-halted", "tradingHalted", "is-trading-halted", "halted", "halt"])
def test_any_supported_trading_halt_flag_rejects_quote(setup, field):
    enroll(setup)
    setup.broker.quotes[0][field] = True
    sample(setup)
    assert samples(setup)[0].reason == "TRADING_HALTED"
    assert only_audit(setup).first_profit_at is None


@pytest.mark.parametrize("offset", [-90, 5])
def test_quote_freshness_boundary_is_inclusive_within_tracking_window(setup, offset):
    enroll(setup)
    observed = STARTED + timedelta(minutes=3)
    setup.broker.quotes = good_quotes(observed + timedelta(seconds=offset))
    sample(setup, at=observed)
    assert only_audit(setup).valid_samples == 1


def test_exact_thirty_second_quote_skew_remains_usable(setup):
    enroll(setup)
    setup.broker.quotes[0]["updated-at"] = iso(OBSERVED - timedelta(seconds=30))
    sample(setup)
    assert only_audit(setup).valid_samples == 1


def test_cannot_enroll_after_the_contracts_tracking_cutoff(setup):
    with pytest.raises(ValueError):
        enroll(setup, now=service.expiry_cutoff(EXPIRATION))


def test_overlapping_different_minute_samples_do_not_lose_persisted_counts(setup, tmp_path, monkeypatch):
    setup.factory = make_factory(f"sqlite+pysqlite:///{tmp_path / 'overlapping.sqlite'}")
    setup.user_id = add_user(setup.factory)
    setup.context["user_id"] = str(setup.user_id)
    setup.journal_id = add_journal(setup.factory, setup.user_id)
    enroll(setup)
    audit_id = only_audit(setup).id
    both_loaded = Barrier(2)
    both_requested = Barrier(2)
    original_session_open = service._session_open
    def synchronized_session_open(now):
        both_loaded.wait(timeout=10)
        return original_session_open(now)
    monkeypatch.setattr(service, "_session_open", synchronized_session_open)
    class ConcurrentBroker(ReadOnlyBroker):
        def get_option_quotes(self, symbols):
            both_requested.wait(timeout=10)
            return super().get_option_quotes(symbols)
    first_broker, second_broker = ConcurrentBroker(), ConcurrentBroker()
    second_at = OBSERVED + timedelta(minutes=1)
    second_broker.quotes = good_quotes(second_at)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(service.sample_stop_audit, audit_id=str(audit_id), broker_client=broker,
                           session_factory=setup.factory, now=at)
            for broker, at in ((first_broker, OBSERVED), (second_broker, second_at))
        ]
        results = [future.result(timeout=15) for future in futures]
    assert all(result["sampled"] for result in results)
    assert len(samples(setup)) == 2
    assert all(point.status == "VALID" for point in samples(setup))
    row = only_audit(setup)
    assert row.attempted_samples == 2
    assert row.valid_samples == 2
    assert row.first_profit_at.replace(tzinfo=UTC) == OBSERVED
    assert row.last_observed_at.replace(tzinfo=UTC) == second_at


def test_simultaneous_same_minute_samples_handle_autoflush_uniqueness_race(setup, tmp_path):
    from sqlalchemy import event

    setup.factory = make_factory(f"sqlite+pysqlite:///{tmp_path / 'same-minute.sqlite'}")
    assert setup.factory.kw["autoflush"] is True
    setup.user_id = add_user(setup.factory)
    setup.context["user_id"] = str(setup.user_id)
    setup.journal_id = add_journal(setup.factory, setup.user_id)
    enroll(setup)
    audit_id = only_audit(setup).id
    both_pending = Barrier(2)

    def synchronize_pending_sample_flush(session, flush_context, instances):
        if any(isinstance(row, StopAuditSample) for row in session.new):
            # Both requests have passed the duplicate check. With autoflush
            # enabled the following UPDATE flushes this insert before commit.
            both_pending.wait(timeout=10)

    event.listen(setup.factory, "before_flush", synchronize_pending_sample_flush)
    brokers = [ReadOnlyBroker(), ReadOnlyBroker()]
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [
                workers.submit(service.sample_stop_audit, audit_id=str(audit_id), broker_client=broker,
                               session_factory=setup.factory, now=OBSERVED)
                for broker in brokers
            ]
            results = [future.result(timeout=15) for future in futures]
    finally:
        event.remove(setup.factory, "before_flush", synchronize_pending_sample_flush)

    assert sorted(result["sampled"] for result in results) == [False, True]
    rejected = next(result for result in results if not result["sampled"])
    assert rejected["reason"] == "ALREADY_SAMPLED_MINUTE"
    assert len(samples(setup)) == 1
    assert samples(setup)[0].status == "VALID"
    row = only_audit(setup)
    assert row.attempted_samples == row.valid_samples == 1
    assert sum(len(broker.quote_reads) for broker in brokers) == 1


def test_background_sampler_never_reuses_one_users_broker_for_another(setup):
    enroll(setup)
    other_id = add_user(setup.factory, "second_audit_user")
    other = SimpleNamespace(factory=setup.factory, user_id=other_id,
                            context={"user_id": str(other_id), "role": "BETA"},
                            journal_id=add_journal(setup.factory, other_id), broker=ReadOnlyBroker())
    other.broker.account_number = "TEST-ACCOUNT-2"
    for order in other.broker.orders.values():
        order["account-number"] = other.broker.account_number
    enroll(other)
    brokers = {str(setup.user_id): setup.broker, str(other_id): other.broker}
    resolutions = []
    def resolve(session, *, user_context, broker_name):
        resolutions.append(user_context["user_id"])
        return brokers[user_context["user_id"]]
    result = service.run_stop_audit_check(session_factory=setup.factory, now=OBSERVED,
                                         broker_resolver=resolve)
    assert result["checked"] == 2
    assert set(resolutions) == set(brokers)
    assert len(setup.broker.quote_reads) == len(other.broker.quote_reads) == 1
    with setup.factory() as session:
        rows = session.scalars(select(StopAudit)).all()
        assert len(rows) == 2
        assert all(row.valid_samples == 1 for row in rows)
        assert len({row.account_fingerprint for row in rows}) == 2
