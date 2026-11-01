"""試験用の Open WebUI の模擬（httpx2 の MockTransport で使う、状態を持つ偽の API）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx2

ADMIN_EMAIL = "admin@example.test"
ADMIN_PASSWORD = "admin-password-for-tests"


@dataclass
class FakeOpenWebUI:
    """Open WebUI の API のうち、初期設定が使うものを真似る。"""

    users: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {ADMIN_EMAIL: {"name": "admin", "password": ADMIN_PASSWORD, "role": "admin"}}
    )
    models: list[dict[str, Any]] = field(default_factory=lambda: [{"id": "mock-model"}])
    tool_servers: list[dict[str, Any]] = field(default_factory=list)
    requests: list[httpx2.Request] = field(default_factory=list)
    health_failures: int = 0
    register_calls: int = 0
    models_config: dict[str, Any] = field(
        default_factory=lambda: {
            "DEFAULT_MODELS": None,
            "DEFAULT_PINNED_MODELS": None,
            "MODEL_ORDER_LIST": ["mock-model"],
            "DEFAULT_MODEL_METADATA": None,
            "DEFAULT_MODEL_PARAMS": None,
        }
    )

    def transport(self) -> httpx2.MockTransport:
        """この模擬に要求を送るトランスポートを返す。"""
        return httpx2.MockTransport(self.handle)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path = request.url.path
        body = json.loads(request.content) if request.content else {}
        if path == "/health":
            if self.health_failures > 0:
                self.health_failures -= 1
                return httpx2.Response(503, json={"detail": "starting"})
            return httpx2.Response(200, json={"status": True})
        if path == "/api/v1/auths/signin":
            user = self.users.get(body.get("email"))
            if user is None or user["password"] != body.get("password"):
                return httpx2.Response(400, json={"detail": "The email or password provided is incorrect."})
            return httpx2.Response(200, json={"token": f"token-{body['email']}", "role": user["role"]})
        if request.headers.get("authorization") != f"Bearer token-{ADMIN_EMAIL}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        if path == "/api/v1/auths/add":
            if body["email"] in self.users:
                return httpx2.Response(400, json={"detail": "Uh-oh! This email is already registered."})
            self.users[body["email"]] = {"name": body["name"], "password": body["password"], "role": body["role"]}
            return httpx2.Response(200, json={"id": body["email"], "email": body["email"], "role": body["role"]})
        if path == "/api/models":
            return httpx2.Response(200, json={"data": self.models})
        if path == "/api/v1/models/model":
            found = [m for m in self.models if m["id"] == request.url.params.get("id") and "access_grants" in m]
            if not found:
                return httpx2.Response(404, json={"detail": "We could not find what you're looking for :/"})
            return httpx2.Response(200, json=found[0])
        if path == "/api/v1/models/model/update":
            for index, existing in enumerate(self.models):
                if existing["id"] == body["id"]:
                    self.models[index] = {**existing, **body}
                    return httpx2.Response(200, json=self.models[index])
            return httpx2.Response(401, json={"detail": "We could not find what you're looking for :/"})
        if path == "/api/v1/models/create":
            self.models.append(body)
            return httpx2.Response(200, json=body)
        if path == "/api/v1/configs/models":
            if request.method == "POST":
                self.models_config = body
            return httpx2.Response(200, json=self.models_config)
        if path == "/api/v1/configs/tool_servers":
            if request.method == "POST":
                self.tool_servers = body["TOOL_SERVER_CONNECTIONS"]
            return httpx2.Response(200, json={"TOOL_SERVER_CONNECTIONS": self.tool_servers})
        if path == "/api/v1/configs/oauth/clients/register":
            self.register_calls += 1
            return httpx2.Response(
                200, json={"status": True, "oauth_client_info": f"encrypted-{body['client_id']}-{self.register_calls}"}
            )
        return httpx2.Response(404, json={"detail": "Not Found"})
