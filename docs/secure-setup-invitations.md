# Secure first-password setup invitations

## Owner workflow

Access request approval is review-only. It sends the approval notification, but
it does not create an account or issue a setup link. Use **Prepare User**, review
the username and email, and **Create User**. Then review the account's displayed
username/email and choose **Send Setup Link**. Existing enabled BETA or VIEWER
users with `must_change_password=true` can also receive an explicitly reviewed
setup invitation. This flag means a first password is still required; it does
not prove that the user has never logged in.

Creating an account retains the existing temporary-password workflow. That
password is not emailed. A setup link lets the recipient choose their password
without knowing or receiving the temporary one. Established users, OWNER
accounts, and disabled accounts cannot receive these first-password invitations.
This is not a general password-reset endpoint. The legacy Forgot Password flow
continues to apply only to the configured owner identity.

No invitations are sent by approval, account creation, migration, app startup,
or deployment. The owner must initiate every send or resend.

## Link and session safety

- Cryptographically random 256-bit tokens, with only SHA-256 digests stored.
- One current invitation per user; deliberate resend rotates the token and
  invalidates the old link, with a persistent 60-second cooldown.
- 24-hour expiry, single-use atomic redemption, and binding to the specific
  user, reviewed email, and credential revision.
- Recheck role, enabled state, first-password requirement, email, revision,
  expiry and consumption at redemption. Never create broker/trading access or
  modify subscriptions or roles.
- PostgreSQL user row locking plus conditional updates protect simultaneous
  issuance/redemption and credential changes. Both the password and consumed
  marker commit together; losing operations cannot overwrite credentials.
- Successful setup requires a fresh normal sign-in. Existing database sessions
  are revoked via `users.session_version`. Ordinary database password changes
  likewise revoke old sessions and clear the browser cookie.
- Existing version-zero database sessions remain valid until the relevant user
  has a credential change. The configured-owner legacy session path is preserved.

Links use the configured trusted HTTPS `BXK_PUBLIC_APP_URL` origin. No request
Host header, client-supplied recipient, role or redirect chooses the destination.
The token is in a URL fragment, not a query or path. The setup page removes the
fragment immediately, holds it only in memory, and sends it in a POST body.
GET/HEAD visits and email link scanners do not consume it. The page has no
third-party scripts, no-store/no-referrer headers, and a restrictive CSP. The
new POST endpoints reject a missing or mismatched Origin.

The owner request includes the username/email that was actually reviewed; stale
identity data is rejected instead of emailing a newly changed address. No raw
tokens or chosen passwords are included in admin metadata, API responses or
application logs. Secret-bearing validation responses are redacted.

## Delivery and recovery

The invitation is committed before calling the email provider. Provider
acceptance is reported as **ACCEPTED**, not proof of inbox delivery. Definite
rejection/configuration failure is **FAILED**. A timeout, network/server error,
or interruption can leave **UNKNOWN**. A process restart after dispatch began
is also displayed as UNKNOWN. Review the inbox/status before a deliberate
resend; never blindly repeat an uncertain send. Only the latest link works.

The stored status also becomes USED or EXPIRED as appropriate. Sending a link
never changes the existing password, sessions, account role or permissions.
A failed send leaves the account intact. After a password has been established,
this invitation route cannot reset it.

## Operations and verification

Migration `b23c45d67e89` follows `a12b34c56d78`, adds the revision column with a
zero default, and creates the invitation table. It sends no emails or tokens and
does not set passwords. Apply migrations before starting the new app.

Automated coverage uses synthetic accounts, tokens and mocked mail only. The
PostgreSQL CI migration job exercises locking/concurrency in its isolated local
test database. Production smoke checks can inspect deployment/migration status,
GET `/setup-password`, its security headers, and unauthenticated API guards
without issuing any invitation. Actual mail delivery and recipient completion
require a separately confirmed real account and owner action.
