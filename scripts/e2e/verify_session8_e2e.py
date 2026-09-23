"""End-to-End Real Verification for Session 8 (GitHub App Migration).

1. Unset GITHUB_TOKEN to prove the review runs entirely on the GitHub App installation token.
2. Create and run a real review on DhyanMehta/httpx PR #1 with installation_id=161715271.
3. Verify that the PR comment is posted by the GitHub App bot (codeguardian-ai-devsecops-platform[bot]).
4. Verify auto-fix branch creation and push to GitHub using the installation token.
5. Clean up the auto-fix test branch.
"""

from __future__ import annotations

import json
import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Unset legacy PAT from environment to guarantee App-token-only execution
os.environ.pop("GITHUB_TOKEN", None)

from backend.config import get_settings
get_settings.cache_clear()

from backend.db.database import get_sessionmaker
from backend.db.models import Finding, Review
from backend.services.autofix_service import create_autofix
from backend.services.review_service import create_review, run_review
from backend.tools.github_app import get_installation_github, get_installation_token

INSTALLATION_ID = 161715271
REPO_NAME = "DhyanMehta/httpx"
PR_NUMBER = 1
HEAD_SHA = "5b2630b1d2b7442718dea99c443513677afc06dd"

print("=" * 72)
print("SESSION 8 REAL END-TO-END VERIFICATION")
print("=" * 72)

# Step 1: Confirm initial state
print("\n[STEP 1] Checking GitHub App installation and current PR comments...")
gh = get_installation_github(INSTALLATION_ID)
repo = gh.get_repo(REPO_NAME)
pr = repo.get_pull(PR_NUMBER)

initial_comments = list(pr.get_issue_comments())
initial_comment_ids = {c.id for c in initial_comments}
print(f"  Repo: {repo.full_name}")
print(f"  PR #{PR_NUMBER}: '{pr.title}' (head: {pr.head.sha[:8]})")
print(f"  Initial comment count: {len(initial_comments)}")
if initial_comments:
    latest = initial_comments[-1]
    print(f"  Latest previous comment: #{latest.id} by {latest.user.login}")

# Step 2: Run real PR review
print("\n[STEP 2] Running real PR review with installation_id=161715271 (NO PAT)...")
SessionLocal = get_sessionmaker()
with SessionLocal() as db:
    # Ensure the installation row exists (in production, the webhook receiver auto-creates this)
    from backend.db.models import Installation
    inst = db.get(Installation, INSTALLATION_ID)
    if inst is None:
        print(f"  Recording installation {INSTALLATION_ID} in database...")
        inst = Installation(
            id=INSTALLATION_ID,
            account_login="DhyanMehta",
            account_type="User",
            app_slug="codeguardian-ai-devsecops-platform",
            target_type="selected",
        )
        db.add(inst)
        db.commit()

    review = create_review(
        db,
        repo_full_name=REPO_NAME,
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        is_fork=False,
        installation_id=INSTALLATION_ID,
    )
    review_id = review.id
    print(f"  Created pending review ID: {review_id} (installation_id={review.installation_id})")

    t0 = time.time()
    run_review(db, review_id, installation_id=INSTALLATION_ID)
    duration = time.time() - t0

    db.refresh(review)
    print(f"  Review finished in {duration:.1f}s with status: {review.status}")
    print(f"  Summary: {review.summary}")
    print(f"  Findings count: {len(review.findings)}")

if review.status != "completed":
    print(f"  [FAIL] Review did not complete successfully: {review.summary}")
    sys.exit(1)

# Step 3: Verify the comment on GitHub
print("\n[STEP 3] Verifying PR comment posted to GitHub...")
updated_comments = list(pr.get_issue_comments())
new_comments = [c for c in updated_comments if c.id not in initial_comment_ids]

if not new_comments:
    print("  [FAIL] No new comment found on PR #1!")
    sys.exit(1)

new_comment = new_comments[-1]
author_login = new_comment.user.login
print(f"  [OK] New comment posted: ID #{new_comment.id}")
print(f"  Comment Author: {author_login}")
print(f"  Comment Snippet:\n    " + "\n    ".join(new_comment.body.splitlines()[:5]))

# Verify the author is the GitHub App bot, NOT the old PAT user
if "bot" in author_login.lower() or "codeguardian" in author_login.lower():
    print(f"  [OK] Verified comment author is the GitHub App: '{author_login}' (NOT the old PAT user)!")
else:
    print(f"  [FAIL] Comment was posted by '{author_login}', expected App bot!")
    sys.exit(1)

# Step 4: Verify auto-fix branch push using installation token
print("\n[STEP 4] Verifying auto-fix branch creation and push via installation token...")
with SessionLocal() as db:
    db_review = db.get(Review, review_id)

    # Check if there are fixable findings; if none, add a synthetic fixable finding to test the flow
    fixable = [f for f in db_review.findings if f.fix_data]
    if not fixable:
        print("  No natural fixable findings in PR; creating a test docstring fixable finding...")
        dummy_finding = Finding(
            review_id=review_id,
            agent="documentation",
            severity="low",
            title="Missing docstring: retry helper",
            detail="Test docstring fix for session 8 verification",
            file_path="httpx/_retry.py",
            line=10,
            fix_data=json.dumps({
                "target_file": "httpx/_retry.py",
                "target_function": "record_success",
                "proposed_docstring": "Record a successful execution, resetting failure count.",
            }),
        )
        db.add(dummy_finding)
        db.commit()

    try:
        autofix_resp = create_autofix(db, review_id)
        db.refresh(db_review)
        print(f"  Auto-fix status: {db_review.autofix_status}")
        print(f"  Auto-fix branch: {db_review.autofix_branch}")
        print(f"  Applied fixes: {db_review.autofix_applied_count}")

        # Verify the branch exists on GitHub
        branch_name = db_review.autofix_branch
        print(f"  Checking if branch '{branch_name}' exists on GitHub...")
        branch = repo.get_branch(branch_name)
        print(f"  [OK] Verified branch exists on GitHub! Commit: {branch.commit.sha[:8]}")

        # Cleanup the test branch from remote
        print(f"  Cleaning up test branch '{branch_name}' on GitHub...")
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()
        print(f"  [OK] Remote branch cleaned up successfully.")

    except Exception as exc:
        print(f"  [FAIL] Auto-fix failed: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

print("\n" + "=" * 72)
print("ALL REAL END-TO-END VERIFICATIONS PASSED!")
print("=" * 72)
