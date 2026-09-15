from urllib.parse import urlencode

import requests

from bxk_app import config


TASTYTRADE_AUTHORIZE_URL = (
    "https://my.tastytrade.com/auth.html"
)

TASTYTRADE_TOKEN_URL = (
    "https://api.tastyworks.com/oauth/token"
)

TASTYTRADE_USER_AGENT = (
    "bxk-trader-pro/1.0"
)

DEFAULT_TIMEOUT_SECONDS = 15

DEFAULT_SCOPES = (
    "read trade openid"
)


class TastytradeOAuthError(
    RuntimeError
):
    pass


def _oauth_config():
    client_id = str(
        config.TASTYTRADE_CLIENT_ID
        or ""
    ).strip()

    client_secret = str(
        config.TASTYTRADE_CLIENT_SECRET
        or ""
    ).strip()

    redirect_uri = str(
        config.TASTYTRADE_REDIRECT_URI
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
        raise TastytradeOAuthError(
            "TASTYTRADE_CLIENT_ID is not configured."
        )

    if not redirect_uri:
        raise TastytradeOAuthError(
            "TASTYTRADE_REDIRECT_URI is not configured."
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
        raise TastytradeOAuthError(
            "TASTYTRADE_CLIENT_ID is not configured."
        )

    if not client_secret:
        raise TastytradeOAuthError(
            "TASTYTRADE_CLIENT_SECRET is not configured."
        )

    if not redirect_uri:
        raise TastytradeOAuthError(
            "TASTYTRADE_REDIRECT_URI is not configured."
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
        raise TastytradeOAuthError(
            "OAuth state is required."
        )

    (
        client_id,
        redirect_uri,
    ) = _require_authorization_config()

    query = urlencode({
        "client_id":
            client_id,
        "redirect_uri":
            redirect_uri,
        "response_type":
            "code",
        "scope":
            DEFAULT_SCOPES,
        "state":
            clean_state,
    })

    return (
        f"{TASTYTRADE_AUTHORIZE_URL}"
        f"?{query}"
    )


def _post_token_request(
    payload: dict,
    *,
    session=None,
) -> dict:
    http = (
        session
        or requests
    )

    try:
        response = http.post(
            TASTYTRADE_TOKEN_URL,
            headers={
                "User-Agent":
                    TASTYTRADE_USER_AGENT,
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
            },
            json=payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise TastytradeOAuthError(
            "Tastytrade OAuth request failed."
        ) from exc

    if not (
        200
        <= response.status_code
        < 300
    ):
        raise TastytradeOAuthError(
            "Tastytrade OAuth request failed "
            f"with HTTP {response.status_code}."
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise TastytradeOAuthError(
            "Tastytrade OAuth returned invalid JSON."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise TastytradeOAuthError(
            "Tastytrade OAuth returned "
            "an invalid response."
        )

    return data


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
        raise TastytradeOAuthError(
            "Tastytrade OAuth response did not "
            "contain an access token."
        )

    if (
        require_refresh_token
        and not refresh_token
    ):
        raise TastytradeOAuthError(
            "Tastytrade OAuth response did not "
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
        raise TastytradeOAuthError(
            "Tastytrade OAuth response contained "
            "an invalid access-token lifetime."
        ) from exc

    if expires_in <= 0:
        raise TastytradeOAuthError(
            "Tastytrade OAuth response contained "
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
        "scope":
            payload.get("scope"),
        "id_token":
            payload.get("id_token"),
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
        raise TastytradeOAuthError(
            "Tastytrade authorization code "
            "is required."
        )

    (
        client_id,
        client_secret,
        redirect_uri,
    ) = _require_token_config()

    payload = _post_token_request(
        {
            "grant_type":
                "authorization_code",
            "code":
                clean_code,
            "client_id":
                client_id,
            "client_secret":
                client_secret,
            "redirect_uri":
                redirect_uri,
        },
        session=session,
    )

    return _normalize_token_payload(
        payload,
        require_refresh_token=True,
    )
