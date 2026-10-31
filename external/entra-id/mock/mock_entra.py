"""E2E テスト用の模擬 Microsoft Entra ID（v2 エンドポイント）。

本物と同じ形のパスで、次を提供する。

- GET  /{tenant}/v2.0/.well-known/openid-configuration
- GET  /{tenant}/discovery/v2.0/keys
- GET  /{tenant}/oauth2/v2.0/authorize   認可コード＋PKCE（利用者は login_hint か MOCK_AUTO_LOGIN_USER で選ぶ）
- POST /{tenant}/oauth2/v2.0/token       authorization_code / refresh_token / jwt-bearer（OBO）

利用者は users.json で定義する。割り当ての無い利用者は AADSTS50105、
同意の無い Graph のスコープでの OBO は AADSTS65001 を返す。
状態（認可コード、リフレッシュトークン）はメモリに持ち、再起動で消える。

設定（環境変数）:
    MOCK_TENANT_ID, MOCK_CLIENT_ID, MOCK_CLIENT_SECRET: 受け付けるテナントとクライアント。
    MOCK_USERS_FILE: 利用者の定義（既定はこのファイルと同じ場所の users.json）。
    MOCK_AUTO_LOGIN_USER: 指定すると、login_hint が無いときにこの利用者で画面を出さずにサインインする。
    MOCK_ACCESS_TOKEN_LIFETIME: アクセストークンの有効期間（秒、既定 3600）。
    MOCK_SIGNING_KEY_FILE: 署名鍵（PEM）。無ければ起動時に作る。
    MOCK_TLS_CERT, MOCK_TLS_KEY, MOCK_PORT: 直接起動するときの TLS 証明書・鍵とポート（既定 8443）。
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

GRAPH_RESOURCE = "https://graph.microsoft.com"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
OIDC_SCOPES = {"openid", "profile", "email", "offline_access"}
JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"


@dataclass
class MockConfig:
    """模擬サーバーの設定。"""

    tenant_id: str = "00000000-0000-0000-0000-000000000001"
    client_id: str = "11111111-1111-1111-1111-111111111111"
    client_secret: str = "mock-client-secret-not-a-real-secret"
    users_file: Path = Path(__file__).with_name("users.json")
    auto_login_user: str | None = None
    access_token_lifetime: int = 3600
    signing_key_file: Path | None = None

    @classmethod
    def from_env(cls) -> MockConfig:
        """環境変数から設定を読む。"""
        env = os.environ
        return cls(
            tenant_id=env.get("MOCK_TENANT_ID", cls.tenant_id),
            client_id=env.get("MOCK_CLIENT_ID", cls.client_id),
            client_secret=env.get("MOCK_CLIENT_SECRET", cls.client_secret),
            users_file=Path(env.get("MOCK_USERS_FILE", str(cls.users_file))),
            auto_login_user=env.get("MOCK_AUTO_LOGIN_USER") or None,
            access_token_lifetime=int(env.get("MOCK_ACCESS_TOKEN_LIFETIME", cls.access_token_lifetime)),
            signing_key_file=Path(env["MOCK_SIGNING_KEY_FILE"]) if env.get("MOCK_SIGNING_KEY_FILE") else None,
        )


@dataclass
class MockState:
    """メモリに持つ状態。"""

    codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    refresh_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)


def _load_key(path: Path | None) -> rsa.RSAPrivateKey:
    if path is not None:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError("MOCK_SIGNING_KEY_FILE must be an RSA private key")
        return key
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _entra_error(status: int, error: str, aadsts: int, description: str, suberror: str | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "error": error,
        "error_description": f"AADSTS{aadsts}: {description}",
        "error_codes": [aadsts],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "trace_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
    }
    if suberror:
        body["suberror"] = suberror
    return JSONResponse(body, status_code=status)


def create_app(config: MockConfig | None = None) -> Starlette:
    """模擬 Entra ID の ASGI アプリを作る。"""
    cfg = config or MockConfig.from_env()
    users: dict[str, dict[str, Any]] = {u["id"]: u for u in json.loads(cfg.users_file.read_text("utf-8"))["users"]}
    key = _load_key(cfg.signing_key_file)
    public = key.public_key().public_numbers()
    kid = hashlib.sha256(str(public.n).encode()).hexdigest()[:16]
    state = MockState()

    def issuer(request: Request) -> str:
        return f"https://{request.headers['host']}/{cfg.tenant_id}/v2.0"

    def check_tenant(request: Request) -> Response | None:
        if request.path_params["tenant"] != cfg.tenant_id:
            return _entra_error(400, "invalid_request", 90002, f"Tenant '{request.path_params['tenant']}' not found.")
        return None

    def sign(claims: dict[str, Any]) -> str:
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid, "typ": "JWT"})

    def user_claims(request: Request, user: dict[str, Any], aud: str, scp: list[str]) -> dict[str, Any]:
        now = int(time.time())
        return {
            "aud": aud,
            "iss": issuer(request),
            "iat": now,
            "nbf": now,
            "exp": now + cfg.access_token_lifetime,
            "sub": user["oid"],
            "oid": user["oid"],
            "tid": cfg.tenant_id,
            "azp": cfg.client_id,
            "name": user["name"],
            "preferred_username": user["upn"],
            "upn": user["upn"],
            "scp": " ".join(scp),
            "ver": "2.0",
        }

    def api_scope_names(scopes: list[str]) -> list[str]:
        prefixes = (f"api://{cfg.client_id}/", f"{cfg.client_id}/")
        names = []
        for s in scopes:
            for p in prefixes:
                if s.startswith(p):
                    names.append(s[len(p) :])
        return names

    def issue_user_tokens(request: Request, user: dict[str, Any], scopes: list[str]) -> JSONResponse:
        names = api_scope_names(scopes)
        access = sign(user_claims(request, user, cfg.client_id, names))
        id_token = sign(user_claims(request, user, cfg.client_id, []))
        body: dict[str, Any] = {
            "token_type": "Bearer",
            "scope": " ".join(s for s in scopes if s not in {"openid", "profile", "email"}),
            "expires_in": cfg.access_token_lifetime,
            "ext_expires_in": cfg.access_token_lifetime,
            "access_token": access,
            "id_token": id_token,
        }
        if "offline_access" in scopes:
            rt = secrets.token_urlsafe(32)
            state.refresh_tokens[rt] = {"user": user["id"], "scopes": scopes}
            body["refresh_token"] = rt
        return JSONResponse(body)

    async def openid_configuration(request: Request) -> Response:
        if (err := check_tenant(request)) is not None:
            return err
        base = f"https://{request.headers['host']}/{cfg.tenant_id}"
        return JSONResponse(
            {
                "issuer": issuer(request),
                "authorization_endpoint": f"{base}/oauth2/v2.0/authorize",
                "token_endpoint": f"{base}/oauth2/v2.0/token",
                "jwks_uri": f"{base}/discovery/v2.0/keys",
                "response_types_supported": ["code"],
                "subject_types_supported": ["pairwise"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": sorted(OIDC_SCOPES),
                "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
                "code_challenge_methods_supported": ["S256", "plain"],
                "tenant_region_scope": "AS",
            }
        )

    async def jwks(request: Request) -> Response:
        if (err := check_tenant(request)) is not None:
            return err
        jwk = {"kty": "RSA", "use": "sig", "kid": kid, "alg": "RS256", "n": _b64url_uint(public.n), "e": _b64url_uint(public.e)}
        return JSONResponse({"keys": [jwk]})

    async def authorize(request: Request) -> Response:
        if (err := check_tenant(request)) is not None:
            return err
        q = request.query_params
        if q.get("client_id") != cfg.client_id:
            return HTMLResponse("AADSTS700016: Application not found in the directory.", status_code=400)
        if q.get("response_type") != "code" or not q.get("redirect_uri"):
            return HTMLResponse("AADSTS900144: The request body must contain response_type=code and redirect_uri.", status_code=400)
        user_id = q.get("login_hint") or cfg.auto_login_user
        if not user_id:
            links = "".join(
                f'<li><a href="?{html.escape(urlencode({**dict(q), "login_hint": uid}))}">{html.escape(u["name"])}</a></li>'
                for uid, u in users.items()
            )
            return HTMLResponse(f"<h1>Mock Entra ID sign-in</h1><ul>{links}</ul>")
        user = users.get(user_id)
        if user is None:
            return HTMLResponse("AADSTS50034: The user account does not exist in this directory.", status_code=400)
        if not user.get("assigned", True):
            return HTMLResponse(
                "AADSTS50105: Your administrator has configured the application to block users unless they are "
                "specifically granted ('assigned') access to the application.",
                status_code=403,
            )
        code = secrets.token_urlsafe(32)
        state.codes[code] = {
            "user": user_id,
            "redirect_uri": q["redirect_uri"],
            "scopes": q.get("scope", "").split(),
            "code_challenge": q.get("code_challenge"),
            "code_challenge_method": q.get("code_challenge_method", "plain"),
            "exp": time.time() + 600,
        }
        params = {"code": code}
        if q.get("state") is not None:
            params["state"] = q["state"]
        sep = "&" if "?" in q["redirect_uri"] else "?"
        return RedirectResponse(f"{q['redirect_uri']}{sep}{urlencode(params)}", status_code=302)

    def client_authenticated(request: Request, form: dict[str, str]) -> bool:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("basic "):
            try:
                cid, _, secret = base64.b64decode(auth[6:]).decode().partition(":")
            except ValueError:
                return False
            return unquote(cid) == cfg.client_id and unquote(secret) == cfg.client_secret
        return form.get("client_id") == cfg.client_id and form.get("client_secret") == cfg.client_secret

    async def token(request: Request) -> Response:
        if (err := check_tenant(request)) is not None:
            return err
        form = {k: str(v) for k, v in (await request.form()).items()}
        if not client_authenticated(request, form):
            return _entra_error(401, "invalid_client", 7000215, "Invalid client secret provided.")
        grant = form.get("grant_type")
        if grant == "authorization_code":
            entry = state.codes.pop(form.get("code", ""), None)
            if entry is None or entry["exp"] < time.time():
                return _entra_error(400, "invalid_grant", 70008, "The provided authorization code or refresh token has expired.")
            if form.get("redirect_uri") != entry["redirect_uri"]:
                return _entra_error(400, "invalid_grant", 50148, "The redirect_uri does not match the authorization request.")
            challenge = entry["code_challenge"]
            if challenge:
                verifier = form.get("code_verifier", "")
                if entry["code_challenge_method"] == "S256":
                    computed = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                else:
                    computed = verifier
                if computed != challenge:
                    return _entra_error(400, "invalid_grant", 501481, "The Code_Verifier does not match the code_challenge.")
            scopes = form.get("scope", "").split() or entry["scopes"]
            return issue_user_tokens(request, users[entry["user"]], scopes)
        if grant == "refresh_token":
            entry = state.refresh_tokens.pop(form.get("refresh_token", ""), None)
            if entry is None:
                return _entra_error(400, "invalid_grant", 70008, "The provided authorization code or refresh token has expired.")
            scopes = form.get("scope", "").split() or entry["scopes"]
            if "offline_access" not in scopes:
                scopes = [*scopes, "offline_access"]
            return issue_user_tokens(request, users[entry["user"]], scopes)
        if grant == JWT_BEARER and form.get("requested_token_use") == "on_behalf_of":
            try:
                claims = jwt.decode(
                    form.get("assertion", ""),
                    key.public_key(),
                    algorithms=["RS256"],
                    audience=[cfg.client_id, f"api://{cfg.client_id}"],
                    issuer=issuer(request),
                )
            except jwt.PyJWTError as exc:
                return _entra_error(400, "invalid_grant", 50013, f"Assertion failed signature validation. ({type(exc).__name__})")
            user = next((u for u in users.values() if u["oid"] == claims.get("oid")), None)
            if user is None:
                return _entra_error(400, "invalid_grant", 50034, "The user account does not exist in this directory.")
            consented = set(user.get("consented_graph_scopes", []))
            requested = form.get("scope", "").split()
            names = []
            for s in requested:
                if s in OIDC_SCOPES:
                    continue
                if not s.startswith(GRAPH_RESOURCE + "/"):
                    return _entra_error(400, "invalid_scope", 70011, f"The provided value for scope {s} is not valid.")
                names.append(s[len(GRAPH_RESOURCE) + 1 :])
            missing = [n for n in names if n != ".default" and n not in consented]
            if missing:
                return _entra_error(
                    400,
                    "invalid_grant",
                    65001,
                    f"The user or administrator has not consented to use the application. Missing: {' '.join(missing)}",
                    suberror="consent_required",
                )
            graph_claims = user_claims(request, user, GRAPH_APP_ID, sorted(consented))
            return JSONResponse(
                {
                    "token_type": "Bearer",
                    "scope": " ".join(f"{GRAPH_RESOURCE}/{n}" for n in sorted(consented)),
                    "expires_in": cfg.access_token_lifetime,
                    "ext_expires_in": cfg.access_token_lifetime,
                    "access_token": sign(graph_claims),
                }
            )
        return _entra_error(400, "unsupported_grant_type", 70003, f"The app requested an unsupported grant type '{grant}'.")

    return Starlette(
        routes=[
            Route("/{tenant}/v2.0/.well-known/openid-configuration", openid_configuration),
            Route("/{tenant}/discovery/v2.0/keys", jwks),
            Route("/{tenant}/oauth2/v2.0/authorize", authorize),
            Route("/{tenant}/oauth2/v2.0/token", token, methods=["POST"]),
        ]
    )


def main() -> None:
    """TLS を付けて直接起動する（コンテナの起動コマンドに使う）。"""
    import uvicorn

    uvicorn.run(
        create_app(),
        host="0.0.0.0",
        port=int(os.environ.get("MOCK_PORT", "8443")),
        ssl_certfile=os.environ["MOCK_TLS_CERT"],
        ssl_keyfile=os.environ["MOCK_TLS_KEY"],
    )


if __name__ == "__main__":
    main()
