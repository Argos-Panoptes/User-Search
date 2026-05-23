"""
API key & JWT auth test playground.

Usage:
    # Run all tests (uses defaults below)
    pytest test_api_auth.py -v

    # Override via env vars
    BASE_URL=http://localhost:8000  API_KEY=usk_xxx.yyy  pytest test_api_auth.py -v

    # Run only a specific test
    pytest test_api_auth.py::test_api_key_auth_me -v

Config: edit the DEFAULT_* constants below or set env vars.
"""

import os
import pytest
import requests

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL     = os.environ.get("BASE_URL",      "http://localhost:8000").rstrip("/")
API_KEY      = os.environ.get("API_KEY",       "usk_hJLrsQ9kFVk.SDeTt1Mz26X8_rODL71OuX-ombggda40g37aQR_yHA4")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN",  "")   # paste a JWT here to test bearer auth
# ────────────────────────────────────────────────────────────────────────────


# ── Helpers ──────────────────────────────────────────────────────────────────
def api_key_headers() -> dict:
    return {"X-API-Key": API_KEY}


def bearer_headers() -> dict:
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}


def no_auth_headers() -> dict:
    return {}


def url(path: str) -> str:
    return f"{BASE_URL}{path}"


# ── Auth: /v1/auth/me ────────────────────────────────────────────────────────

class TestAuthMe:
    """Checks what identity the API sees for each auth method."""

    def test_api_key_auth_me(self):
        """API key should resolve to the owning user."""
        r = requests.get(url("/v1/auth/me"), headers=api_key_headers())
        print(f"\nStatus: {r.status_code}")
        print(f"Body:   {r.text[:500]}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json().get("data") or r.json()
        assert "id" in data or "email" in data, "Response missing user identity fields"
        print(f"Authenticated as: {data.get('email')} (superuser={data.get('is_superuser')})")

    def test_no_auth_returns_401(self):
        """Without any credentials, /auth/me should 401."""
        r = requests.get(url("/v1/auth/me"), headers=no_auth_headers())
        print(f"\nStatus: {r.status_code}  Body: {r.text[:200]}")
        assert r.status_code in (401, 403), f"Expected 401/403 but got {r.status_code}"

    def test_bad_api_key_returns_401(self):
        """A garbled API key should be rejected."""
        r = requests.get(url("/v1/auth/me"), headers={"X-API-Key": "usk_bad.totally_wrong_key"})
        print(f"\nStatus: {r.status_code}  Body: {r.text[:200]}")
        assert r.status_code == 401, f"Expected 401 but got {r.status_code}"

    @pytest.mark.skipif(not BEARER_TOKEN, reason="BEARER_TOKEN env var not set")
    def test_bearer_token_auth_me(self):
        """JWT bearer token should also resolve to a user."""
        r = requests.get(url("/v1/auth/me"), headers=bearer_headers())
        print(f"\nStatus: {r.status_code}")
        print(f"Body:   {r.text[:500]}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"


# ── Auth: /v1/auth/check-auth ────────────────────────────────────────────────

class TestCheckAuth:

    def test_check_auth_with_api_key(self):
        r = requests.get(url("/v1/auth/check-auth"), headers=api_key_headers())
        print(f"\nStatus: {r.status_code}  Body: {r.text[:300]}")
        assert r.status_code == 200


# ── Ingestion: normal user key should be REJECTED (superuser required) ───────

class TestIngestionAccess:
    """
    All /v1/ingest/* endpoints require superuser.
    A normal user API key must get 403 (authenticated but not authorized).
    If you get 401, the key itself is invalid/revoked.
    """

    INGEST_ENDPOINTS = [
        "/v1/ingest/users",
        "/v1/ingest/groups",
        "/v1/ingest/avatars",
    ]

    @pytest.mark.parametrize("path", INGEST_ENDPOINTS)
    def test_normal_key_cannot_access_ingest(self, path):
        """Normal user key should get 403 on ingestion endpoints, not 200."""
        r = requests.post(
            url(path),
            json={"file_path": "/tmp/dummy.json"},
            headers=api_key_headers(),
        )
        print(f"\n{path}  →  {r.status_code}: {r.text[:300]}")

        if r.status_code == 401:
            pytest.fail(
                "Got 401 — the API key is not being recognised at all. "
                "Check that the key is active and not expired."
            )
        elif r.status_code == 200:
            pytest.fail(
                "Got 200 — this key has superuser access! "
                "That is unexpected for a 'normal user' key."
            )
        else:
            # 403 = authenticated but not authorized (expected for normal user)
            assert r.status_code == 403, (
                f"Unexpected status {r.status_code}. "
                "Expected 403 (normal user blocked from superuser endpoint)."
            )
            print("PASS: normal user key correctly blocked with 403")

    def test_no_auth_ingest_returns_401_or_403(self):
        """No credentials → must not reach ingestion at all."""
        r = requests.post(
            url("/v1/ingest/users"),
            json={"file_path": "/tmp/dummy.json"},
            headers=no_auth_headers(),
        )
        print(f"\nStatus: {r.status_code}  Body: {r.text[:200]}")
        assert r.status_code in (401, 403)


# ── API Key self-management ───────────────────────────────────────────────────

class TestApiKeyManagement:
    """Test the /v1/api-keys self-service endpoints."""

    def test_list_my_api_keys(self):
        """Should return the list of keys owned by the authenticated user."""
        r = requests.get(url("/v1/api-keys"), headers=api_key_headers())
        print(f"\nStatus: {r.status_code}  Body: {r.text[:500]}")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data") or body
        print(f"Keys returned: {len(data) if isinstance(data, list) else data}")


# ── Search endpoints (regular user should be able to call these) ──────────────

class TestSearchEndpoints:

    def test_user_search_with_api_key(self):
        r = requests.post(
            url("/v1/users/search"),
            json={"limit": 5, "offset": 0},
            headers=api_key_headers(),
        )
        print(f"\nStatus: {r.status_code}  Body: {r.text[:400]}")
        # 200 = works fine, 403 = subscription required
        assert r.status_code in (200, 403), f"Unexpected: {r.status_code}"
        if r.status_code == 200:
            print("Search works for this key")
        else:
            print("Search blocked — subscription may be required for this key's owner")

    def test_group_search_with_api_key(self):
        r = requests.post(
            url("/v1/groups/search"),
            json={"limit": 5, "offset": 0},
            headers=api_key_headers(),
        )
        print(f"\nStatus: {r.status_code}  Body: {r.text[:400]}")
        assert r.status_code in (200, 403), f"Unexpected: {r.status_code}"


# ── Quick status summary (run standalone: python test_api_auth.py) ────────────

if __name__ == "__main__":
    print(f"Base URL : {BASE_URL}")
    print(f"API Key  : {API_KEY[:20]}...")
    print()

    checks = [
        ("GET /v1/auth/me (api key)",     lambda: requests.get(url("/v1/auth/me"), headers=api_key_headers())),
        ("GET /v1/auth/me (no auth)",     lambda: requests.get(url("/v1/auth/me"), headers=no_auth_headers())),
        ("GET /v1/api-keys",              lambda: requests.get(url("/v1/api-keys"), headers=api_key_headers())),
        ("POST /v1/ingest/users (normal key)", lambda: requests.post(url("/v1/ingest/users"), json={"file_path": "/tmp/x"}, headers=api_key_headers())),
        ("POST /v1/users/search",         lambda: requests.post(url("/v1/users/search"), json={"limit": 3}, headers=api_key_headers())),
    ]

    for label, fn in checks:
        try:
            r = fn()
            body_snippet = r.text[:120].replace("\n", " ")
            print(f"  [{r.status_code}] {label}")
            print(f"         {body_snippet}")
        except Exception as e:
            print(f"  [ERR] {label}: {e}")
        print()
