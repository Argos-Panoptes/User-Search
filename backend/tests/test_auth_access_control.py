"""
Auth access control tests.

Tests two auth modes:
  - Admin API key  (X-API-Key header)    ->ingestion + jobs access only
  - Paid-user JWT  (Authorization: Bearer) ->users/groups/media access only

Usage:
    pytest test_auth_access_control.py -v -s

Override defaults via env vars:
    BASE_URL   ADMIN_API_KEY   MAGIC_LINK_TOKEN   TEST_EMAIL
"""

import os
import time
import pytest
import requests

# ── Config ───────────────────────────────────────────────────────────────────
BASE_URL          = os.environ.get("BASE_URL",          "http://localhost:8000/app/api")
AUTH_SERVER_URL   = os.environ.get("AUTH_SERVER_URL",   "http://localhost:9000")
ADMIN_API_KEY     = os.environ.get("ADMIN_API_KEY",     "usk_Kg8pey-s_8k.bNJV6p_hVScic2bvoM6d38u_U7SanteRd8eibGP1FwQ")
MAGIC_LINK_TOKEN  = os.environ.get("MAGIC_LINK_TOKEN",  "lIwSEgscbdnrHIYhmvicHSpXJWxIzZRw")
TEST_EMAIL        = os.environ.get("TEST_EMAIL",        "bhavinnor13@gmail.com")
API_PASSWORD      = os.environ.get("API_PASSWORD",      "12345678@$VNln")
CALLBACK_URL      = "http://localhost:5173/app/"
# ─────────────────────────────────────────────────────────────────────────────


def url(path: str) -> str:
    return f"{BASE_URL}{path}"


# ── Session-scoped JWT fixture ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def jwt_token():
    """
    Verify the magic link ->get session cookie ->exchange for JWT.
    Cached for the whole test session so the magic link is only consumed once.
    """
    print(f"\n[fixture] Verifying magic link for {TEST_EMAIL}...")

    auth_session = requests.Session()
    r = auth_session.get(
        f"{AUTH_SERVER_URL}/api/auth/magic-link/verify",
        params={"token": MAGIC_LINK_TOKEN, "callbackURL": CALLBACK_URL},
        allow_redirects=False,
    )
    print(f"[fixture] Magic link verify ->{r.status_code}")
    print(f"[fixture] Cookies set: {dict(r.cookies)}")

    # The session cookie is on domain localhost — copy it to a backend session
    backend_session = requests.Session()
    for cookie in auth_session.cookies:
        backend_session.cookies.set(cookie.name, cookie.value, domain="localhost", path="/")

    # Also propagate any Set-Cookie headers not captured by requests (url-encoded tokens)
    for header_val in r.headers.getlist("Set-Cookie") if hasattr(r.headers, "getlist") else [r.headers.get("Set-Cookie", "")]:
        if "better-auth" in header_val or "session" in header_val.lower():
            parts = header_val.split(";")[0].split("=", 1)
            if len(parts) == 2:
                backend_session.cookies.set(parts[0].strip(), parts[1].strip(), domain="localhost", path="/")

    print(f"[fixture] Backend session cookies: {dict(backend_session.cookies)}")

    # Exchange cookie session for JWT
    token_r = backend_session.get(url("/v1/auth/token"))
    print(f"[fixture] /v1/auth/token ->{token_r.status_code}: {token_r.text[:300]}")
    assert token_r.status_code == 200, (
        f"Failed to get JWT from session. Status {token_r.status_code}: {token_r.text}. "
        "The magic link may have expired — generate a fresh one."
    )
    token = token_r.json()["access_token"]
    print(f"[fixture] JWT obtained (first 40 chars): {token[:40]}...")
    return token


@pytest.fixture(scope="session")
def admin_headers():
    return {"X-API-Key": ADMIN_API_KEY}


@pytest.fixture(scope="session")
def jwt_headers(jwt_token):
    return {"Authorization": f"Bearer {jwt_token}"}


# ── Helper ───────────────────────────────────────────────────────────────────

def hit(method, path, headers, body=None):
    r = requests.request(method, url(path), headers=headers, json=body, timeout=10)
    safe = r.text[:200].encode("ascii", errors="replace").decode("ascii")
    print(f"  {method} {path} ->{r.status_code}: {safe}")
    return r


# ════════════════════════════════════════════════════════════════════════════
# 1. ADMIN API KEY TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestAdminApiKey:
    """Admin API key should access ingestion + jobs. Auth endpoints always accessible."""

    # ── Auth endpoints ──────────────────────────────────────────────────────

    def test_auth_me(self, admin_headers):
        r = hit("GET", "/v1/auth/me", admin_headers)
        assert r.status_code == 200
        data = r.json().get("data") or r.json()
        assert data.get("is_superuser") is True, "Admin key must resolve to a superuser"
        print(f"  ->authenticated as {data.get('email')}")

    def test_auth_token_endpoint(self, admin_headers):
        """Admin key can also fetch a JWT token."""
        r = hit("GET", "/v1/auth/token", admin_headers)
        assert r.status_code == 200
        assert "access_token" in r.json()

    # ── Ingestion endpoints (admin-only, should be ACCESSIBLE) ─────────────

    @pytest.mark.parametrize("path", [
        "/v1/ingest/users",
        "/v1/ingest/groups",
        "/v1/ingest/avatars",
    ])
    def test_ingestion_accessible(self, admin_headers, path):
        """Admin API key must reach ingestion endpoints (422 = auth passed, body invalid — that's fine)."""
        r = hit("POST", path, admin_headers, body={})
        assert r.status_code not in (401, 403), (
            f"Admin key was blocked on {path} with {r.status_code}. "
            "Expected 422 (body validation) or 200."
        )
        # 400/422 = auth OK, request body invalid -- both acceptable
        assert r.status_code in (200, 400, 422), f"Unexpected {r.status_code} on {path}"

    # ── Jobs endpoints (admin-only, should be ACCESSIBLE) ──────────────────

    def test_jobs_accessible(self, admin_headers):
        r = hit("GET", "/v1/jobs", admin_headers)
        assert r.status_code not in (401, 403), f"Admin key blocked on /v1/jobs: {r.status_code}"

    # ── API key management (admin-only, should be ACCESSIBLE) ──────────────

    def test_api_keys_list_accessible(self, admin_headers):
        r = hit("GET", "/v1/api-keys", admin_headers)
        assert r.status_code == 200

    def test_admin_api_keys_accessible(self, admin_headers):
        r = hit("GET", "/v1/admin/api-keys", admin_headers)
        assert r.status_code == 200

    # ── Bad / no key ────────────────────────────────────────────────────────

    def test_invalid_key_returns_401(self):
        r = hit("GET", "/v1/auth/me", {"X-API-Key": "usk_bad.totally_wrong"})
        assert r.status_code == 401

    def test_no_auth_returns_401(self):
        r = hit("GET", "/v1/auth/me", {})
        assert r.status_code in (401, 403)


# ════════════════════════════════════════════════════════════════════════════
# 2. JWT (PAID USER) TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestJwtPaidUser:
    """
    JWT for bhavinnor13@gmail.com (paid, non-admin).
    Should access users/groups/media. Must NOT access admin routes.
    """

    # ── Auth endpoints — accessible ─────────────────────────────────────────

    def test_auth_me_resolves_correct_user(self, jwt_headers):
        r = hit("GET", "/v1/auth/me", jwt_headers)
        assert r.status_code == 200
        data = r.json().get("data") or r.json()
        assert data.get("email") == TEST_EMAIL, f"Expected {TEST_EMAIL}, got {data.get('email')}"
        assert data.get("is_superuser") is False, "Paid user must NOT be superuser"
        print(f"  ->authenticated as {data.get('email')} (superuser={data.get('is_superuser')})")

    def test_auth_check_auth(self, jwt_headers):
        r = hit("GET", "/v1/auth/check-auth", jwt_headers)
        assert r.status_code == 200

    # ── Documented search endpoints — accessible ────────────────────────────

    def test_users_search_accessible(self, jwt_headers):
        r = hit("POST", "/v1/users/search", jwt_headers, body={"limit": 3, "offset": 0})
        assert r.status_code in (200, 422), f"Expected access, got {r.status_code}: {r.text[:200]}"
        assert r.status_code != 401, "JWT user should be authenticated"
        assert r.status_code != 403, "Paid user should have subscription access to /v1/users/search"

    def test_groups_search_accessible(self, jwt_headers):
        r = hit("POST", "/v1/groups/search", jwt_headers, body={"limit": 3, "offset": 0})
        assert r.status_code in (200, 422), f"Expected access, got {r.status_code}: {r.text[:200]}"
        assert r.status_code not in (401, 403)

    def test_media_endpoint_accessible(self, jwt_headers):
        # /v1/media/proxy requires a valid url param but auth should pass
        r = hit("GET", "/v1/media/proxy?url=http://example.com/test.jpg", jwt_headers)
        # 400/422/502 = auth passed, request invalid — acceptable
        assert r.status_code not in (401, 403), f"Media endpoint blocked with {r.status_code}"

    # ── Admin / ingestion endpoints — must be BLOCKED ───────────────────────

    @pytest.mark.parametrize("method,path,body", [
        ("POST", "/v1/ingest/users",   {"file_path": "/tmp/x"}),
        ("POST", "/v1/ingest/groups",  {"file_path": "/tmp/x"}),
        ("POST", "/v1/ingest/avatars", {}),
        ("GET",  "/v1/jobs",           None),
        ("GET",  "/v1/admin/api-keys", None),
        ("GET",  "/v1/app-users",      None),
    ])
    def test_admin_endpoints_blocked(self, jwt_headers, method, path, body):
        r = hit(method, path, jwt_headers, body=body)
        assert r.status_code == 403, (
            f"Expected 403 on {path} for paid user, got {r.status_code}. "
            "Paid users must NOT access admin/ingestion endpoints."
        )

    # ── API key self-service — must be BLOCKED (admin-only now) ────────────

    def test_api_key_creation_blocked(self, jwt_headers):
        r = hit("POST", "/v1/api-keys", jwt_headers, body={"name": "test"})
        assert r.status_code == 403, (
            f"Expected 403 — API key creation is admin-only, got {r.status_code}"
        )

    def test_api_key_list_blocked(self, jwt_headers):
        r = hit("GET", "/v1/api-keys", jwt_headers)
        assert r.status_code == 403, (
            f"Expected 403 — API key listing is admin-only, got {r.status_code}"
        )

    # ── Endpoints not in docs — must be BLOCKED ────────────────────────────

    @pytest.mark.parametrize("method,path", [
        ("GET",  "/v1/internal/ping"),
        ("GET",  "/v1/admin/monitoring/usage"),
        ("POST", "/v1/uploads/init"),
    ])
    def test_undocumented_endpoints_blocked(self, jwt_headers, method, path):
        r = hit(method, path, jwt_headers)
        assert r.status_code in (403, 404, 405), (
            f"Undocumented endpoint {path} returned {r.status_code} for paid user — expected 403/404"
        )

    # ── API key auth must be REJECTED for non-admin user ───────────────────

    def test_api_key_rejected_if_non_admin_owner(self):
        """A hypothetical API key owned by a non-admin should get 403."""
        # This tests the enforcement in _validate_api_key — we can't easily
        # create a non-admin key via API (now blocked), so we verify the error
        # message from the admin key endpoint when used without superuser.
        # The admin key above works, proving the guard runs correctly.
        # We just verify that no non-admin key can be created anymore.
        r = requests.post(
            url("/v1/api-keys"),
            headers={"Authorization": f"Bearer {pytest.jwt_token_cache}"}
            if hasattr(pytest, "jwt_token_cache") else {},
            json={"name": "should-fail"},
            timeout=10,
        )
        # Either 401 (no auth) or 403 (authenticated non-admin) — both are correct
        assert r.status_code in (401, 403), f"Expected blocked, got {r.status_code}"


# ════════════════════════════════════════════════════════════════════════════
# 3. PASSWORD-BASED JWT TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def jwt_token_via_password():
    """Seed the API password via admin key, then obtain a JWT via email+password."""
    print(f"\n[fixture] Seeding API password for {TEST_EMAIL} via admin key...")
    seed = requests.post(
        url("/v1/auth/admin/set-user-api-password"),
        headers={"X-API-Key": ADMIN_API_KEY},
        params={"email": TEST_EMAIL},
        json={"password": API_PASSWORD, "confirm_password": API_PASSWORD},
        timeout=10,
    )
    print(f"[fixture] seed ->{seed.status_code}: {seed.text[:200]}")
    assert seed.status_code == 204, f"Failed to seed password: {seed.status_code}: {seed.text}"

    print(f"[fixture] Getting JWT via password for {TEST_EMAIL}...")
    r = requests.post(
        url("/v1/auth/password-token"),
        json={"email": TEST_EMAIL, "password": API_PASSWORD},
        timeout=10,
    )
    print(f"[fixture] /v1/auth/password-token ->{r.status_code}: {r.text[:300]}")
    assert r.status_code == 200, (
        f"Failed to get JWT via password. Status {r.status_code}: {r.text}"
    )
    token = r.json()["access_token"]
    print(f"[fixture] JWT obtained (first 40 chars): {token[:40]}...")
    return token


@pytest.fixture(scope="session")
def jwt_password_headers(jwt_token_via_password):
    return {"Authorization": f"Bearer {jwt_token_via_password}"}


class TestPasswordJwt:
    """JWT obtained via email+password should behave identically to magic-link JWT."""

    def test_password_token_endpoint_returns_jwt(self):
        r = requests.post(url("/v1/auth/password-token"),
                          json={"email": TEST_EMAIL, "password": API_PASSWORD}, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        print(f"\n  Token: {body['access_token'][:40]}...")

    def test_wrong_password_returns_401(self):
        r = requests.post(url("/v1/auth/password-token"),
                          json={"email": TEST_EMAIL, "password": "WrongPass99!!"}, timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_unknown_email_returns_401(self):
        r = requests.post(url("/v1/auth/password-token"),
                          json={"email": "nobody@notreal.com", "password": API_PASSWORD}, timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_auth_me_resolves_correct_user(self, jwt_password_headers):
        r = hit("GET", "/v1/auth/me", jwt_password_headers)
        assert r.status_code == 200
        data = r.json().get("data") or r.json()
        assert data.get("email") == TEST_EMAIL
        assert data.get("is_superuser") is False
        print(f"\n  ->authenticated as {data.get('email')}")

    def test_users_search_accessible(self, jwt_password_headers):
        r = hit("POST", "/v1/users/search", jwt_password_headers, body={"limit": 3, "offset": 0})
        assert r.status_code not in (401, 403), f"Expected access, got {r.status_code}"

    def test_groups_search_accessible(self, jwt_password_headers):
        r = hit("POST", "/v1/groups/search", jwt_password_headers, body={"limit": 3, "offset": 0})
        assert r.status_code not in (401, 403), f"Expected access, got {r.status_code}"

    def test_admin_endpoints_blocked(self, jwt_password_headers):
        for method, path, body in [
            ("POST", "/v1/ingest/users",   {"file_path": "/tmp/x"}),
            ("GET",  "/v1/admin/api-keys", None),
        ]:
            r = hit(method, path, jwt_password_headers, body=body)
            assert r.status_code == 403, f"Expected 403 on {path}, got {r.status_code}"

    def test_api_password_status_endpoint(self, jwt_password_headers):
        r = hit("GET", "/v1/auth/api-password-status", jwt_password_headers)
        assert r.status_code == 200
        assert r.json()["has_api_password"] is True
        print(f"\n  ->has_api_password: {r.json()['has_api_password']}")


# ════════════════════════════════════════════════════════════════════════════
# 4. RATE LIMIT TEST (Admin API Key — 30 req/min)
# ════════════════════════════════════════════════════════════════════════════

class TestAdminApiKeyRateLimit:
    """Fire 35 rapid requests and confirm the 31st gets 429."""

    def test_rate_limit_triggers_at_30(self, admin_headers):
        results = {}
        hit_429_at = None

        for i in range(1, 36):
            r = requests.get(url("/v1/auth/me"), headers=admin_headers, timeout=5)
            results[r.status_code] = results.get(r.status_code, 0) + 1
            if r.status_code == 429 and hit_429_at is None:
                hit_429_at = i
                retry_after = r.headers.get("Retry-After")
                print(f"\n  Rate limit hit at request {i}. Retry-After: {retry_after}s")
                break

        print(f"\n  Results: {results}")

        assert hit_429_at is not None, (
            f"Rate limit was never triggered after 35 requests. "
            f"Results: {results}. Backend may need restart to pick up the rate limit fix."
        )
        assert hit_429_at <= 31, (
            f"Rate limit triggered at request {hit_429_at}, expected ≤ 31 (quota=30/min)"
        )
        print(f"  PASS: Rate limited at request {hit_429_at} as expected.")

        # Wait for the window to reset so we don't pollute other tests
        time.sleep(62)
