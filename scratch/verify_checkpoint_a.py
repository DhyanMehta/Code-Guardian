"""Verification script for Checkpoint A (Backend Auth Hardening).

Tests:
1. Unauthenticated requests -> 401
2. Garbage cookie requests -> 401
3. Seeds dummy installation (id=999999) + dummy review (id=999999) not linked to user
4. Valid user session accessing unauthorized installation -> 403
5. Valid user session accessing unauthorized review / report / autofix -> 403
6. Verifies seeded review is omitted from GET /reviews
7. Valid user session accessing own installation/review -> 200
8. Cleans up seeded dummy installation & review
"""

import sys
import json
from datetime import datetime, timezone, timedelta
import httpx
import jwt
from backend.config import get_settings
from backend.db.database import get_sessionmaker
from backend.db.models import Installation, Review, User, UserInstallation

BASE_URL = "http://127.0.0.1:8000"

def get_valid_jwt() -> str:
    settings = get_settings()
    secret = settings.require("session_secret")
    session = get_sessionmaker()()
    user = session.query(User).filter(User.github_login == "DhyanMehta").first()
    assert user is not None, "User DhyanMehta not found in DB"
    user_id = user.id
    session.close()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "github_login": "DhyanMehta",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def seed_dummy_data():
    session = get_sessionmaker()()
    try:
        # Check if already exists and clean up first
        existing_rev = session.get(Review, 999999)
        if existing_rev:
            session.delete(existing_rev)
            session.commit()
        existing_inst = session.get(Installation, 999999)
        if existing_inst:
            session.delete(existing_inst)
            session.commit()

        # Seed dummy installation not linked to user
        dummy_inst = Installation(
            id=999999,
            account_login="unauthorized-org",
            account_type="Organization",
            app_slug="codeguardian",
            target_type="selected",
        )
        session.add(dummy_inst)
        session.commit()

        dummy_rev = Review(
            id=999999,
            repo_full_name="unauthorized-org/secret-repo",
            pr_number=42,
            status="completed",
            summary="Confidential review.",
            is_fork=False,
            installation_id=999999,
        )
        session.add(dummy_rev)
        session.commit()
        print("[SETUP] Seeded dummy installation 999999 and review 999999")
    finally:
        session.close()

def cleanup_dummy_data():
    session = get_sessionmaker()()
    try:
        rev = session.get(Review, 999999)
        if rev:
            session.delete(rev)
        inst = session.get(Installation, 999999)
        if inst:
            session.delete(inst)
        session.commit()
        print("[CLEANUP] Deleted dummy installation 999999 and review 999999")
    finally:
        session.close()

def run_tests():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    valid_token = get_valid_jwt()
    valid_cookies = {"session_jwt": valid_token}
    garbage_cookies = {"session_jwt": "garbage.invalid.token"}

    results = []

    def check(name, resp, expected_status, note=""):
        status = resp.status_code
        passed = status == expected_status
        result_str = f"[{'PASS' if passed else 'FAIL'}] {name}: got {status}, expected {expected_status}. {note}"
        print(result_str)
        results.append((passed, result_str))
        return passed

    print("\n--- 1. UNAUTHENTICATED TESTS (NO COOKIE) ---")
    check("GET /metrics/trends (unauth)", client.get("/metrics/trends"), 401)
    check("GET /reviews/1/report (unauth)", client.get("/reviews/1/report"), 401)
    check("POST /reviews/1/autofix (unauth)", client.post("/reviews/1/autofix"), 401)
    check("POST /reviews/1/autofix/approve (unauth)", client.post("/reviews/1/autofix/approve", json={"approved_by": "attacker"}), 401)
    check("POST /reviews/1/autofix/reject (unauth)", client.post("/reviews/1/autofix/reject"), 401)

    print("\n--- 2. GARBAGE COOKIE TESTS ---")
    check("GET /metrics/trends (garbage cookie)", client.get("/metrics/trends", cookies=garbage_cookies), 401)
    check("GET /reviews/1/report (garbage cookie)", client.get("/reviews/1/report", cookies=garbage_cookies), 401)
    check("POST /reviews/1/autofix (garbage cookie)", client.post("/reviews/1/autofix", cookies=garbage_cookies), 401)
    check("POST /reviews/1/autofix/approve (garbage cookie)", client.post("/reviews/1/autofix/approve", json={"approved_by": "attacker"}, cookies=garbage_cookies), 401)
    check("POST /reviews/1/autofix/reject (garbage cookie)", client.post("/reviews/1/autofix/reject", cookies=garbage_cookies), 401)
    check("GET /reviews (garbage cookie)", client.get("/reviews", cookies=garbage_cookies), 401)

    print("\n--- 3. CROSS-INSTALLATION / AUTHORIZATION TESTS (VALID USER COOKIE) ---")
    check("GET /metrics/trends?installation_id=999999", client.get("/metrics/trends?installation_id=999999", cookies=valid_cookies), 403)
    check("GET /reviews?installation_id=999999", client.get("/reviews?installation_id=999999", cookies=valid_cookies), 403)
    check("GET /reviews/999999", client.get("/reviews/999999", cookies=valid_cookies), 403)
    check("GET /reviews/999999/report", client.get("/reviews/999999/report", cookies=valid_cookies), 403)
    check("POST /reviews/999999/autofix", client.post("/reviews/999999/autofix", cookies=valid_cookies), 403)
    check("POST /reviews/999999/autofix/approve", client.post("/reviews/999999/autofix/approve", json={"approved_by": "DhyanMehta"}, cookies=valid_cookies), 403)
    check("POST /reviews/999999/autofix/reject", client.post("/reviews/999999/autofix/reject", cookies=valid_cookies), 403)

    print("\n--- 4. ISOLATION TEST (SEEDED REVIEW OMITTED FROM GET /reviews) ---")
    resp_list = client.get("/reviews?limit=100", cookies=valid_cookies)
    if check("GET /reviews returns 200", resp_list, 200):
        items = resp_list.json().get("items", [])
        seeded_present = any(item["id"] == 999999 for item in items)
        if not seeded_present:
            print("[PASS] Seeded review 999999 is NOT present in user's review list")
            results.append((True, "[PASS] Seeded review omitted from user's review list"))
        else:
            print("[FAIL] Seeded review 999999 WAS found in user's review list!")
            results.append((False, "[FAIL] Seeded review found in user's review list"))

    print("\n--- 5. AUTHORIZED TESTS (VALID USER OWNS INSTALLATION 161715271) ---")
    check("GET /metrics/trends?installation_id=161715271", client.get("/metrics/trends?installation_id=161715271", cookies=valid_cookies), 200)
    check("GET /reviews?installation_id=161715271", client.get("/reviews?installation_id=161715271", cookies=valid_cookies), 200)
    check("GET /reviews/71 (owned review)", client.get("/reviews/71", cookies=valid_cookies), 200)
    check("GET /reviews/71/report (owned review report)", client.get("/reviews/71/report", cookies=valid_cookies), 200)

    all_passed = all(p for p, _ in results)
    print(f"\n==========================================")
    print(f"OVERALL RESULT: {'ALL PASSED' if all_passed else 'SOME FAILED'} ({sum(1 for p, _ in results if p)}/{len(results)})")
    print(f"==========================================")
    return all_passed

if __name__ == "__main__":
    try:
        seed_dummy_data()
        success = run_tests()
    finally:
        cleanup_dummy_data()
    sys.exit(0 if success else 1)
