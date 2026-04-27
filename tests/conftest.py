"""
Shared pytest fixtures for the GAM test suite.

Most existing API tests predate :class:`gam.auth.permissions.HasAPIPermission`
and hit endpoints anonymously. To keep them green without adding token
plumbing to every test, the autouse fixture below short-circuits permission
checks. Tests that explicitly verify enforcement (TGF-316) opt back into the
real check via the ``enforce_api_permissions`` marker.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _bypass_api_permissions(request, monkeypatch):
    if "enforce_api_permissions" in request.keywords:
        return
    from gam.auth.permissions import HasAPIPermission

    monkeypatch.setattr(
        HasAPIPermission, "has_permission", lambda self, req, view: True
    )
