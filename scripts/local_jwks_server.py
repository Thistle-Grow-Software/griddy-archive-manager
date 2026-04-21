"""
Local JWKS server + test-token issuer for exercising :class:`JWKSAuthentication`
end-to-end without depending on a real IdP (Clerk, Auth0, etc.).

Usage::

    # Terminal 1 — start the server and emit a signed token:
    python scripts/local_jwks_server.py --issue

    # Terminal 2 — point the Django app at it and hit any endpoint:
    export JWKS_URL=http://127.0.0.1:8765/.well-known/jwks.json
    export JWT_ISSUER=https://local.griddy.test
    export JWT_AUDIENCE=griddy-api-local
    curl -H "Authorization: Bearer <token-from-terminal-1>" \\
         http://127.0.0.1:8000/api/v1/leagues/

The keypair is regenerated on every server start, so tokens do not survive a
restart. That is intentional — this script is a dev aid, not a persistent IdP.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.utils import to_base64url_uint

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ISSUER = "https://local.griddy.test"
DEFAULT_AUDIENCE = "griddy-api-local"
DEFAULT_KID = "local-dev-key-1"


def _build_jwks(public_key: rsa.RSAPublicKey, kid: str) -> dict[str, Any]:
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": to_base64url_uint(numbers.n).decode("ascii"),
                "e": to_base64url_uint(numbers.e).decode("ascii"),
            }
        ]
    }


def _issue_token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str,
    issuer: str,
    audience: str,
    subject: str,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def _make_handler(jwks: dict[str, Any]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/.well-known/jwks.json":
                self.send_response(404)
                self.end_headers()
                return
            payload = json.dumps(jwks).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(
                f"[jwks-server] {self.address_string()} - {format % args}\n"
            )

    return Handler


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    private_key: rsa.RSAPrivateKey | None = None,
    kid: str = DEFAULT_KID,
) -> tuple[HTTPServer, rsa.RSAPrivateKey]:
    """Start an HTTP server hosting a JWKS derived from ``private_key``.

    Returns the server and the private key. Call ``server.shutdown()`` to
    stop it. Intended for both CLI use and in-process test harnesses.
    """
    if private_key is None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = _build_jwks(private_key.public_key(), kid)
    server = HTTPServer((host, port), _make_handler(jwks))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, private_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--issuer", default=DEFAULT_ISSUER)
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE)
    parser.add_argument("--kid", default=DEFAULT_KID)
    parser.add_argument("--subject", default="user_local_dev")
    parser.add_argument("--ttl", type=int, default=3600, help="Token TTL in seconds.")
    parser.add_argument(
        "--issue",
        action="store_true",
        help="Print a signed token on startup and keep serving.",
    )
    args = parser.parse_args(argv)

    server, private_key = serve(args.host, args.port, kid=args.kid)
    sys.stderr.write(
        f"[jwks-server] serving JWKS at http://{args.host}:{args.port}"
        f"/.well-known/jwks.json\n"
    )

    if args.issue:
        token = _issue_token(
            private_key,
            kid=args.kid,
            issuer=args.issuer,
            audience=args.audience,
            subject=args.subject,
            ttl_seconds=args.ttl,
        )
        sys.stdout.write(token + "\n")
        sys.stdout.flush()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.stderr.write("[jwks-server] shutting down\n")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
