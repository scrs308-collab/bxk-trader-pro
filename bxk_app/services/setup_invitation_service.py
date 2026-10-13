"""Owner-initiated, single-use first-password setup. No automatic invitations."""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import urllib.error
from urllib.parse import urlsplit
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.db_models.setup_invitation import SetupInvitation
from bxk_app.db_models.user import User, UserRole
from bxk_app.services.email_service import send_setup_invitation_email
from bxk_app.services.system_settings_service import hash_app_password

INVITATION_TTL = timedelta(hours=24)
RESEND_COOLDOWN = timedelta(seconds=60)
INVALID_LINK = "This setup link is invalid or expired. Ask the owner for a new link."


class InvalidSetupLink(ValueError):
    pass


class InvitationCooldown(ValueError):
    pass


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def invitation_eligible(user: User) -> bool:
    return bool(user.is_active and user.must_change_password and user.role in {UserRole.BETA, UserRole.VIEWER})


def invitation_metadata(invitation: SetupInvitation | None, *, now=None):
    if invitation is None:
        return None
    now = now or datetime.now(timezone.utc)
    status = invitation.delivery_status
    if invitation.consumed_at:
        status = "USED"
    elif _utc(invitation.expires_at) <= now:
        status = "EXPIRED"
    elif status == "DISPATCHING":
        # A process may have restarted after committing, or the provider may
        # still be responding. Never present this as a confirmed send.
        status = "UNKNOWN"
    return {
        "status": status,
        "created_at": _utc(invitation.created_at).isoformat(),
        "expires_at": _utc(invitation.expires_at).isoformat(),
    }


def public_app_origin() -> str:
    value = str(config.BXK_PUBLIC_APP_URL or "").strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError("A trusted HTTPS BXK_PUBLIC_APP_URL origin is required before sending invitations.")
    return value


def _user_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise LookupError("User not found.") from exc


def issue_setup_invitation(session: Session, *, user_id: str, expected_email: str, expected_username: str,
                           owner_id: str | None = None, now=None):
    now = now or datetime.now(timezone.utc)
    origin = public_app_origin()
    user = session.scalar(select(User).where(User.id == _user_id(user_id)).with_for_update())
    if user is None:
        raise LookupError("User not found.")
    if not invitation_eligible(user):
        raise ValueError("Setup invitations are only available for enabled BETA or VIEWER users who still need to set their first password.")
    recipient = str(user.email or "").strip()
    if recipient.casefold() != str(expected_email).strip().casefold() or user.username != expected_username:
        raise ValueError("The account changed since it was reviewed. Refresh and confirm its username and email again.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
        raise ValueError("Review and correct the user's email address before sending a setup invitation.")
    existing = session.get(SetupInvitation, user.id, populate_existing=True)
    if existing is not None and now < _utc(existing.created_at) + RESEND_COOLDOWN:
        raise InvitationCooldown("Wait at least 60 seconds before requesting another setup email.")

    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    fields = {
        "token_hash": digest,
        "recipient_email": recipient.casefold(),
        "credential_version": user.session_version,
        "created_at": now,
        "expires_at": now + INVITATION_TTL,
        "consumed_at": None,
        "delivery_status": "DISPATCHING",
        "requested_by": _user_id(owner_id) if owner_id else None,
    }
    username = user.username
    target_id = user.id
    try:
        if existing is None:
            session.add(SetupInvitation(user_id=target_id, **fields))
        else:
            # CAS also prevents competing workers from issuing multiple links
            # from the same observed invitation on SQLite (no row locks).
            changed = session.execute(update(SetupInvitation).where(
                SetupInvitation.user_id == target_id,
                SetupInvitation.token_hash == existing.token_hash,
                SetupInvitation.created_at == existing.created_at,
            ).values(**fields).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                session.rollback()
                raise InvitationCooldown("Another setup invitation changed. Refresh before trying again.")
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise InvitationCooldown("Another setup invitation is being sent. Refresh before trying again.") from exc

    # The record is durable before the provider is contacted. A crash after
    # this point leaves UNKNOWN metadata; a deliberate resend rotates the link.
    try:
        send_setup_invitation_email(
            recipient,
            username=username,
            setup_url=f"{origin}/setup-password#token={token}",
            expires_hours=24,
        )
        status = "ACCEPTED"
    except Exception as exc:
        # Never log transport exceptions: request objects may contain tokens.
        cause = exc.__cause__
        if isinstance(cause, urllib.error.HTTPError) and 400 <= cause.code < 500:
            status = "FAILED"
        elif isinstance(exc, RuntimeError) and cause is None:
            status = "FAILED"  # Local preflight/configuration failure.
        else:
            status = "UNKNOWN"  # Timeout/network/server response is uncertain.

    session.execute(update(SetupInvitation).where(
        SetupInvitation.user_id == target_id,
        SetupInvitation.token_hash == digest,
    ).values(delivery_status=status).execution_options(synchronize_session=False))
    session.commit()
    messages = {
        "ACCEPTED": "Setup email accepted by the email provider. Delivery is not confirmed. Only the latest setup link works.",
        "FAILED": "The account exists, but the setup email was not accepted. Check email configuration before requesting a new link.",
        "UNKNOWN": "Setup email status is unconfirmed. Check the recipient's inbox before requesting a new link; a resend replaces the earlier link.",
    }
    return {"status": status, "expires_at": (now + INVITATION_TTL).isoformat(), "message": messages[status]}


def redeem_setup_invitation(session: Session, *, token: str, new_password: str, now=None):
    supplied_now = now
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise InvalidSetupLink(INVALID_LINK)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    invitation = session.scalar(select(SetupInvitation).where(SetupInvitation.token_hash == digest))
    if invitation is None:
        raise InvalidSetupLink(INVALID_LINK)
    user = session.scalar(select(User).where(User.id == invitation.user_id).with_for_update())
    session.refresh(invitation)
    now = now or datetime.now(timezone.utc)
    if (user is None or not invitation_eligible(user) or invitation.token_hash != digest
            or invitation.consumed_at is not None or _utc(invitation.expires_at) <= now
            or invitation.recipient_email != str(user.email).strip().casefold()
            or invitation.credential_version != user.session_version
            or invitation.delivery_status == "FAILED"):
        raise InvalidSetupLink(INVALID_LINK)
    if not isinstance(new_password, str) or len(new_password) > 1024:
        raise ValueError("Password must contain between 8 and 1024 characters.")
    password_hash = hash_app_password(new_password)
    # Password hashing takes time; enforce expiry at the consuming write too.
    now = supplied_now or datetime.now(timezone.utc)
    version = user.session_version
    # Both conditional writes commit together, so replay/concurrency either
    # changes the password exactly once or rolls the entire operation back.
    consumed = session.execute(update(SetupInvitation).where(
        SetupInvitation.user_id == user.id,
        SetupInvitation.token_hash == digest,
        SetupInvitation.consumed_at.is_(None),
        SetupInvitation.expires_at > now,
    ).values(consumed_at=now).execution_options(synchronize_session=False))
    changed = session.execute(update(User).where(
        User.id == user.id,
        User.session_version == version,
        User.password_hash == user.password_hash,
        User.must_change_password.is_(True),
        User.is_active.is_(True),
        User.role.in_([UserRole.BETA, UserRole.VIEWER]),
        User.email == user.email,
    ).values(password_hash=password_hash, must_change_password=False,
             session_version=User.session_version + 1).execution_options(synchronize_session=False))
    if consumed.rowcount != 1 or changed.rowcount != 1:
        session.rollback()
        raise InvalidSetupLink(INVALID_LINK)
    session.commit()
    return {"password_set": True, "message": "Your password is set. Sign in with your username and new password."}
