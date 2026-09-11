from urllib.parse import urlencode

import requests

from bxk_app import config


SCHWAB_AUTHORIZE_URL = (
    "https://api.schwabapi.com/v1/oauth/authorize"
)

SCHWAB_TOKEN_URL = (
    "https://api.schwabapi.com/v1/oauth/token"
)

DEFAULT_TIMEOUT_SECONDS = 15


class SchwabOAuthError(RuntimeError):
    pass


def _oauth_config():
    client_id = str(
        config.SCHWAB_CLIENT_ID
        or ""
    ).strip()

    client_secret = str(
        config.SCHWAB_CLIENT_SECRET
        or ""
    ).strip()

    redirect_uri = str(
        config.SCHWAB_REDIRECT_URI
        or ""
    ).strip()

    return (
        client_id,
        client_secret,
        redirect_uri,
    )


def _require_authorization_config():
    (
        client_id,
        _,
        redirect_uri,
    ) = _oauth_config()

    if not client_id:
        raise SchwabOAuthError(
            "SCHWAB_CLIENT_ID is not configured."
        )

    if not redirect_uri:
        raise SchwabOAuthError(
            "SCHWAB_REDIRECT_URI is not configured."
        )

    return (
        client_id,
        redirect_uri,
    )


def _require_token_config():
    (
        client_id,
        client_secret,
        redirect_uri,
    ) = _oauth_config()

    if not client_id:
        raise SchwabOAuthError(
            "SCHWAB_CLIENT_ID is not configured."
        )

    if not client_secret:
        raise SchwabOAuthError(
            "SCHWAB_CLIENT_SECRET is not configured."
        )

    if not redirect_uri:
        raise SchwabOAuthError(
            "SCHWAB_REDIRECT_URI is not configured."
        )

    return (
        client_id,
        client_secret,
        redirect_uri,
    )


def build_authorization_url(
    state: str,
) -> str:
    clean_state = str(
        state or ""
    ).strip()

    if not clean_state:
        raise SchwabOAuthError(
            "OAuth state is required."
        )

    (
        client_id,
        redirect_uri,
    ) = _require_authorization_config()

    query = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": clean_state,
    })

    return (
        f"{SCHWAB_AUTHORIZE_URL}"
        f"?{query}"
    )


def _post_token_request(
    data: dict,
    *,
    session=None,
) -> dict:
    (
        client_id,
        client_secret,
        _,
    ) = _require_token_config()

    http = (
        session
        or requests
    )

    try:
        response = http.post(
            SCHWAB_TOKEN_URL,
            auth=(
                client_id,
                client_secret,
            ),
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/x-www-form-urlencoded",
            },
            data=data,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SchwabOAuthError(
            "Schwab OAuth request failed."
        ) from exc

    if not (
        200
        <= response.status_code
        < 300
    ):
        raise SchwabOAuthError(
            "Schwab OAuth request failed "
            f"with HTTP {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise SchwabOAuthError(
            "Schwab OAuth returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise SchwabOAuthError(
            "Schwab OAuth returned an invalid response."
        )

    return payload


def _normalize_token_payload(
    payload: dict,
    *,
    require_refresh_token: bool,
) -> dict:
    access_token = str(
        payload.get("access_token")
        or ""
    ).strip()

    refresh_token = str(
        payload.get("refresh_token")
        or ""
    ).strip()

    if not access_token:
        raise SchwabOAuthError(
            "Schwab OAuth response did not "
            "contain an access token."
        )

    if (
        require_refresh_token
        and not refresh_token
    ):
        raise SchwabOAuthError(
            "Schwab OAuth response did not "
            "contain a refresh token."
        )

    raw_expires_in = payload.get(
        "expires_in",
        0,
    )

    try:
        expires_in = int(
            raw_expires_in
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SchwabOAuthError(
            "Schwab OAuth response contained "
            "an invalid access-token lifetime."
        ) from exc

    if expires_in <= 0:
        raise SchwabOAuthError(
            "Schwab OAuth response contained "
            "an invalid access-token lifetime."
        )

    return {
        "access_token":
            access_token,
        "refresh_token": (
            refresh_token
            or None
        ),
        "expires_in":
            expires_in,
        "token_type": str(
            payload.get("token_type")
            or "Bearer"
        ),
        "scope": payload.get(
            "scope"
        ),
    }


def exchange_authorization_code(
    code: str,
    *,
    session=None,
) -> dict:
    clean_code = str(
        code or ""
    ).strip()

    if not clean_code:
        raise SchwabOAuthError(
            "Schwab authorization code is required."
        )

    (
        _,
        _,
        redirect_uri,
    ) = _require_token_config()

    payload = _post_token_request(
        {
            "grant_type":
                "authorization_code",
            "code":
                clean_code,
            "redirect_uri":
                redirect_uri,
        },
        session=session,
    )

    return _normalize_token_payload(
        payload,
        require_refresh_token=True,
    )


def refresh_access_token(
    refresh_token: str,
    *,
    session=None,
) -> dict:
    clean_refresh_token = str(
        refresh_token or ""
    ).strip()

    if not clean_refresh_token:
        raise SchwabOAuthError(
            "Schwab refresh token is required."
        )

    payload = _post_token_request(
        {
            "grant_type":
                "refresh_token",
            "refresh_token":
                clean_refresh_token,
        },
        session=session,
    )

    normalized = _normalize_token_payload(
        payload,
        require_refresh_token=False,
    )

    if not normalized[
        "refresh_token"
    ]:
        normalized[
            "refresh_token"
        ] = clean_refresh_token

    return normalized
