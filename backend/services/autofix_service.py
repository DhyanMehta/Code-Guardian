"""Auto-fix service — branch creation, fix application, and approval recording.

Handles the auto-fix gate: creates a branch with applied fixes (tests, docstrings),
re-validates each fix at apply time, and records human approval. No code is ever
pushed without an explicit human action.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import ast
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

from sqlalchemy.orm import Session, object_session

from backend.agents._validation import validate_drafted_docstring, validate_drafted_test
from backend.agents._validation import find_function, safe_workspace_path
from backend.config import get_settings
from backend.db.models import Finding, Review, User
from sqlalchemy import update, text
from backend.tools.git_auth import git_auth, git_environment

logger = logging.getLogger(__name__)


@dataclass
class AppliedFix:
    target_function: str
    target_file: str
    fix_type: str  # "test" | "docstring"


@dataclass
class SkippedFix:
    target_function: str
    target_file: str
    reason: str


@dataclass
class AutofixResult:
    branch: str = ""
    applied_fixes: list[AppliedFix] = field(default_factory=list)
    skipped_fixes: list[SkippedFix] = field(default_factory=list)


class AutofixError(Exception):
    """Raised when autofix cannot proceed."""


def create_autofix(db: Session, review_id: int, *, user: User | None = None) -> AutofixResult:
    """Serialize branch creation across processes; reconcile interrupted pushes."""
    engine = db.get_bind()
    if engine.dialect.name != "postgresql":
        return _create_autofix(db, review_id, user=user)
    with engine.connect() as lock:
        if not lock.execute(text("SELECT pg_try_advisory_lock(79301, :id)"), {"id": review_id}).scalar():
            raise AutofixError("Auto-fix already exists or is being created.")
        try:
            review = db.get(Review, review_id)
            if review and review.autofix_status == "creating":
                review.autofix_status = "failed"
                db.commit()
            return _create_autofix(db, review_id, user=user)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(79301, :id)"), {"id": review_id})


def _create_autofix(db: Session, review_id: int, *, user: User | None = None) -> AutofixResult:
    """Create an auto-fix branch with validated fixes.

    Returns the result with applied/skipped counts. Raises AutofixError if the
    operation cannot proceed (no fixable findings, fork PR, already pending, etc).
    """
    review = db.get(Review, review_id)
    if review is None:
        raise AutofixError(f"Review {review_id} not found.")

    if review.status != "completed":
        raise AutofixError(
            f"Review {review_id} is in '{review.status}' state. "
            "Auto-fix is only available for completed reviews."
        )

    if review.is_fork:
        raise AutofixError(
            "Auto-fix is unavailable for fork PRs. The bot lacks push access "
            "to the fork repository. Apply the suggested fixes manually from "
            "the review comment."
        )

    if review.autofix_status in ("creating", "pending_approval", "approved", "rejected"):
        raise AutofixError(
            f"Auto-fix branch already exists for review {review_id} "
            f"(branch: {review.autofix_branch}). Approve or reject it first."
        )

    if user and review.autofix_commit_sha and review.autofix_branch:
        from backend.services.authorization import user_github, require_repo
        from github import GithubException
        require_repo(user, review.installation_id, review.repo_full_name, write=True)
        try:
            branch = user_github(user).get_repo(review.repo_full_name).get_branch(review.autofix_branch)
        except GithubException as exc:
            if exc.status != 404:
                raise AutofixError("Could not reconcile the previous branch push.") from exc
        else:
            if branch.commit.sha != review.autofix_commit_sha:
                raise AutofixError("Auto-fix branch changed; refusing to overwrite it.")
            review.autofix_status = "pending_approval"
            review.autofix_error = None
            db.commit()
            return AutofixResult(branch=review.autofix_branch,
                applied_fixes=[AppliedFix(**item) for item in json.loads(review.autofix_applied_fixes or "[]")],
                skipped_fixes=[SkippedFix(item["target_function"], item["target_file"], item["reason"]) for item in json.loads(review.autofix_skipped_fixes or "[]")])

    # Gather fixable findings
    fixable_findings = (
        db.query(Finding)
        .filter(Finding.review_id == review_id, Finding.fix_data.isnot(None))
        .all()
    )

    if not fixable_findings:
        raise AutofixError(f"Review {review_id} has no fixable findings.")

    if user:
        from backend.services.authorization import user_token, user_github, require_repo
        require_repo(user, review.installation_id, review.repo_full_name, write=True)
        head = user_github(user).get_repo(review.repo_full_name).get_pull(review.pr_number).head.sha
        if head != review.commit_sha:
            raise AutofixError("PR head changed; run a new review before creating fixes.")
        token = user_token(user)
    elif review.installation_id:
        from backend.tools.github_app import get_installation_token
        token = get_installation_token(review.installation_id)
    else:
        settings = get_settings()
        token = settings.require("github_token")

    branch_name = f"codeguardian/autofix/{review_id}"
    claimed = db.execute(update(Review).where(Review.id == review_id, (Review.autofix_status.is_(None)) | (Review.autofix_status == "failed")).values(autofix_status="creating"))
    db.commit()
    if not claimed.rowcount:
        raise AutofixError("Auto-fix already exists or is being created.")
    try:
        result = _apply_fixes_and_push(review=review, findings=fixable_findings, branch_name=branch_name, token=token)
    except Exception as exc:
        db.rollback()
        review = db.get(Review, review_id)
        review.autofix_status = "failed"
        review.autofix_error = f"Auto-fix failed ({type(exc).__name__})."
        db.commit()
        raise AutofixError(review.autofix_error) from exc

    if not result.applied_fixes:
        review.autofix_status = "failed"
        review.autofix_error = "All fixes failed validation."
        db.commit()
        raise AutofixError(
            "All fixes failed re-validation against current code. "
            "The PR may have been updated since the review."
        )

    review.autofix_status = "pending_approval"
    review.autofix_error = None
    review.autofix_branch = branch_name
    # Persist the outcome detail, not just the status. The applied/skipped split is
    # the evidence that apply-time re-validation rejected unusable fixes, and
    # returning it only in this response meant it vanished on the next page load.
    review.autofix_applied_count = len(result.applied_fixes)
    review.autofix_applied_fixes = json.dumps([asdict(item) for item in result.applied_fixes])
    review.autofix_skipped_fixes = json.dumps([
        {
            "target": f"{s.target_file}:{s.target_function}",
            "target_file": s.target_file,
            "target_function": s.target_function,
            "reason": s.reason,
        }
        for s in result.skipped_fixes
    ])
    db.commit()

    result.branch = branch_name
    return result


def approve_autofix(
    db: Session,
    review_id: int,
    approved_by: str,
    *, user: User | None = None,
) -> None:
    """Record explicit human approval for an auto-fix branch.

    Raises AutofixError if the review isn't in pending_approval state.
    """
    from datetime import datetime, timezone

    review = db.get(Review, review_id)
    if review is None:
        raise AutofixError(f"Review {review_id} not found.")

    if review.autofix_status != "pending_approval":
        raise AutofixError(
            f"Review {review_id} auto-fix is in '{review.autofix_status}' state. "
            "Only 'pending_approval' reviews can be approved."
        )

    if user and review.autofix_commit_sha:
        from backend.services.authorization import user_github
        try:
            actual = user_github(user).get_repo(review.repo_full_name).get_branch(review.autofix_branch).commit.sha
        except Exception as exc:
            raise AutofixError("Could not verify the auto-fix branch before approval.") from exc
        if actual != review.autofix_commit_sha:
            raise AutofixError("Auto-fix branch changed; the recorded commit cannot be approved.")
    claimed = db.execute(update(Review).where(Review.id == review_id, Review.autofix_status == "pending_approval").values(autofix_status="approved", autofix_approved_by=approved_by, autofix_approved_at=datetime.now(timezone.utc)))
    if not claimed.rowcount:
        db.rollback()
        raise AutofixError("Auto-fix decision was already recorded.")
    db.commit()


def reject_autofix(db: Session, review_id: int) -> None:
    """Reject an auto-fix branch."""
    review = db.get(Review, review_id)
    if review is None:
        raise AutofixError(f"Review {review_id} not found.")

    if review.autofix_status != "pending_approval":
        raise AutofixError(
            f"Review {review_id} auto-fix is in '{review.autofix_status}' state. "
            "Only 'pending_approval' reviews can be rejected."
        )

    claimed = db.execute(update(Review).where(Review.id == review_id, Review.autofix_status == "pending_approval").values(autofix_status="rejected"))
    if not claimed.rowcount:
        db.rollback()
        raise AutofixError("Auto-fix decision was already recorded.")
    db.commit()


def _apply_fixes_and_push(
    review: Review,
    findings: list[Finding],
    branch_name: str,
    token: str,
) -> AutofixResult:
    """Clone, apply fixes with re-validation, commit, and push."""
    result = AutofixResult()

    with tempfile.TemporaryDirectory() as tmpdir, git_auth(token):
        repo_url = f"https://github.com/{review.repo_full_name}.git"
        workspace = os.path.join(tmpdir, "repo")

        try:
            _run_git(["clone", "--depth=1", repo_url, workspace], cwd=tmpdir)
            _run_git(["fetch", "origin", review.commit_sha, "--depth=1"], cwd=workspace)
            _run_git(["checkout", review.commit_sha], cwd=workspace)
            _run_git(["checkout", "-b", branch_name], cwd=workspace)
        except subprocess.CalledProcessError as exc:
            raise AutofixError(f"Git setup failed: {exc.stderr[:200]}") from exc

        # Apply each fix with re-validation
        for finding in findings:
            fix_data = json.loads(finding.fix_data)
            _apply_single_fix(finding, fix_data, workspace, result)

        if not result.applied_fixes:
            return result

        # Commit and push
        try:
            changed = _run_git(["diff", "--name-only"], cwd=workspace).stdout.splitlines()
            untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=workspace).stdout.splitlines()
            for name in changed + untracked:
                path = safe_workspace_path(workspace, name)
                if path.suffix == ".py":
                    ast.parse(path.read_text(encoding="utf-8"))
            _run_git(["add", "--", *(changed + untracked)], cwd=workspace)
            _run_git(
                ["-c", "user.name=CodeGuardian", "-c", "user.email=codeguardian@users.noreply.github.com", "commit", "-m", f"codeguardian: auto-fix for review #{review.id}"],
                cwd=workspace,
            )
            review.autofix_commit_sha = _run_git(["rev-parse", "HEAD"], cwd=workspace).stdout.strip()
            review.autofix_branch = branch_name
            review.autofix_applied_count = len(result.applied_fixes)
            review.autofix_applied_fixes = json.dumps([asdict(item) for item in result.applied_fixes])
            review.autofix_skipped_fixes = json.dumps([asdict(item) for item in result.skipped_fixes])
            session = object_session(review)
            if session:
                session.commit()
            # The prepared commit is durable before the network side effect.
            from github import Auth, Github
            current_head = Github(auth=Auth.Token(token), timeout=15).get_repo(review.repo_full_name).get_pull(review.pr_number).head.sha
            if current_head != review.commit_sha:
                raise AutofixError("PR head changed while preparing fixes; run a new review.")
            ref = f"refs/heads/{branch_name}"
            _run_git(["push", f"--force-with-lease={ref}:", "origin", f"HEAD:{ref}"], cwd=workspace)
        except subprocess.CalledProcessError as exc:
            raise AutofixError(f"Git commit/push failed: {exc.stderr[:200]}") from exc

    return result


def _apply_single_fix(
    finding: Finding,
    fix_data: dict[str, Any],
    workspace: str,
    result: AutofixResult,
) -> None:
    """Apply and validate a single fix. Appends to result.applied or result.skipped."""
    if finding.agent == "test_gap":
        _apply_test_fix(finding, fix_data, workspace, result)
    elif finding.agent == "documentation":
        _apply_docstring_fix(finding, fix_data, workspace, result)
    else:
        result.skipped_fixes.append(SkippedFix(
            target_function=finding.title,
            target_file=finding.file_path or "",
            reason=f"Agent '{finding.agent}' fixes are not supported for auto-apply.",
        ))


def _apply_test_fix(
    finding: Finding,
    fix_data: dict[str, Any],
    workspace: str,
    result: AutofixResult,
) -> None:
    """Apply a drafted test with re-validation."""
    target_function = fix_data.get("target_function", "")
    target_file = fix_data.get("target_file", "")
    test_code = fix_data.get("test_code", "")

    is_valid, reason = validate_drafted_test(
        target_function=target_function,
        target_file=target_file,
        test_code=test_code,
        workspace_path=workspace,
    )

    if not is_valid:
        result.skipped_fixes.append(SkippedFix(
            target_function=target_function,
            target_file=target_file,
            reason=reason,
        ))
        return

    # Write test file
    test_dir = str(safe_workspace_path(workspace, "tests/codeguardian"))
    os.makedirs(test_dir, exist_ok=True)
    suffix = hashlib.sha256(f"{target_file}:{target_function}".encode()).hexdigest()[:12]
    test_filename = f"test_{target_function.replace('.', '_')}_{suffix}.py"
    test_path = os.path.join(test_dir, test_filename)

    if os.path.lexists(test_path):
        result.skipped_fixes.append(SkippedFix(target_function, target_file, "Generated test path already exists."))
        return
    with open(test_path, "x", encoding="utf-8") as f:
        f.write(test_code)

    result.applied_fixes.append(AppliedFix(
        target_function=target_function,
        target_file=target_file,
        fix_type="test",
    ))


def _apply_docstring_fix(
    finding: Finding,
    fix_data: dict[str, Any],
    workspace: str,
    result: AutofixResult,
) -> None:
    """Apply a drafted docstring with re-validation."""
    target_function = fix_data.get("target_function", "")
    target_file = fix_data.get("target_file", "")
    docstring = fix_data.get("docstring", "")

    is_valid, reason = validate_drafted_docstring(
        target_function=target_function,
        target_file=target_file,
        docstring=docstring,
        workspace_path=workspace,
    )

    if not is_valid:
        result.skipped_fixes.append(SkippedFix(
            target_function=target_function,
            target_file=target_file,
            reason=reason,
        ))
        return

    # Insert docstring into the source file
    full_path = str(safe_workspace_path(workspace, target_file))
    if not _insert_docstring(full_path, target_function, docstring):
        result.skipped_fixes.append(SkippedFix(
            target_function=target_function,
            target_file=target_file,
            reason="Failed to insert docstring into source file.",
        ))
        return

    result.applied_fixes.append(AppliedFix(
        target_function=target_function,
        target_file=target_file,
        fix_type="docstring",
    ))


def _insert_docstring(file_path: str, func_name: str, docstring: str) -> bool:
    """Insert a docstring into a function definition via AST line detection."""
    import ast

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        source = "".join(lines)
        tree = ast.parse(source)
    except (SyntaxError, OSError) as exc:
        logger.warning("Cannot parse %s for docstring insertion: %s", file_path, exc)
        return False

    selected = find_function(tree, func_name)
    for node in [selected] if selected else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node is selected:
                # A one-line suite needs structural rewriting; skip rather than corrupt it.
                if node.body[0].lineno == node.lineno:
                    return False
                # Find the line after the function def (colon line)
                insert_line = node.body[0].lineno - 1  # 0-indexed

                # Check if there's already a docstring
                if (
                    isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    # Replace existing docstring
                    old_end = node.body[0].end_lineno  # 1-indexed
                    indent = lines[insert_line][:len(lines[insert_line]) - len(lines[insert_line].lstrip())]
                    new_docstring_lines = _format_docstring(docstring, indent)
                    lines[insert_line:old_end] = new_docstring_lines
                else:
                    # Insert new docstring
                    indent = lines[insert_line][:len(lines[insert_line]) - len(lines[insert_line].lstrip())]
                    new_docstring_lines = _format_docstring(docstring, indent)
                    lines[insert_line:insert_line] = new_docstring_lines

                try:
                    ast.parse("".join(lines))
                except SyntaxError:
                    return False
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True

    return False


def _format_docstring(docstring: str, indent: str) -> list[str]:
    """Format a docstring into lines with proper indentation and triple quotes."""
    docstring = docstring.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    doc_lines = docstring.strip().split("\n")
    if len(doc_lines) == 1:
        return [f'{indent}"""{doc_lines[0]}"""\n']
    result = [f'{indent}"""{doc_lines[0]}\n']
    for line in doc_lines[1:]:
        if line.strip():
            result.append(f"{indent}{line}\n")
        else:
            result.append("\n")
    result.append(f'{indent}"""\n')
    return result


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run a git command with timeout and error capture."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        env=git_environment(),
    )
