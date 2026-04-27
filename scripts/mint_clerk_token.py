"""
Mint a Clerk session JWT for a given user via Clerk's Backend API.

Useful for hitting GAM's authenticated DRF endpoints from scripts, ``curl``,
``httpie``, or test harnesses without driving a browser sign-in flow.

The script does two Backend API calls:

1. ``POST /v1/sessions`` to create (or reuse) a session for the user.
2. ``POST /v1/sessions/<session_id>/tokens[/<template>]`` to mint a JWT.

Both calls require ``CLERK_SECRET_KEY``. Direct session creation is permitted
on Clerk *development* instances; production instances reject it, so this
script is intended for local dev and CI against a dev instance only.

Usage::

    export CLERK_SECRET_KEY=sk_test_...
    python scripts/mint_clerk_token.py --user-id user_2abcDEF...

    # With a custom JWT template (matches GAM's configured audience):
    python scripts/mint_clerk_token.py --user-id user_... --template griddy-api

    # Drop straight into a curl call:
    TOKEN=$(python scripts/mint_clerk_token.py --user-id user_...)
    curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/leagues/
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

CLERK_API_BASE = "https://api.clerk.com/v1"


def _auth_headers(secret_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }


def create_session(secret_key: str, user_id: str, *, timeout: float) -> str:
    response = requests.post(
        f"{CLERK_API_BASE}/sessions",
        headers=_auth_headers(secret_key),
        json={"user_id": user_id},
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(
            f"Clerk session creation failed ({response.status_code}): {response.text}"
        )
    session_id = response.json().get("id")
    if not session_id:
        raise RuntimeError(f"Clerk session response missing 'id': {response.text}")
    return session_id


def mint_token(
    secret_key: str,
    session_id: str,
    *,
    template: str | None,
    timeout: float,
) -> str:
    path = f"/sessions/{session_id}/tokens"
    if template:
        path = f"{path}/{template}"
    response = requests.post(
        f"{CLERK_API_BASE}{path}",
        headers=_auth_headers(secret_key),
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(
            f"Clerk token mint failed ({response.status_code}): {response.text}"
        )
    jwt_value = response.json().get("jwt")
    if not jwt_value:
        raise RuntimeError(f"Clerk token response missing 'jwt': {response.text}")
    return jwt_value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        required=True,
        help="Clerk user ID (e.g. user_2abcDEF...). Find via the Clerk dashboard.",
    )
    parser.add_argument(
        "--template",
        default=None,
        help=(
            "Optional Clerk JWT template name. Use this when the API expects a "
            "specific audience or custom claims; omit for the default session token."
        ),
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("CLERK_SECRET_KEY"),
        help="Clerk secret key. Defaults to $CLERK_SECRET_KEY.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    if not args.secret_key:
        parser.error("CLERK_SECRET_KEY is not set and --secret-key was not provided.")

    session_id = create_session(args.secret_key, args.user_id, timeout=args.timeout)
    token = mint_token(
        args.secret_key,
        session_id,
        template=args.template,
        timeout=args.timeout,
    )
    sys.stdout.write(token + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
