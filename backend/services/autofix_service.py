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
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from backend.agents._validation import validate_drafted_docstring, validate_drafted_test
from backend.config import get_settings
from backend.db.models import Finding, Review

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


def create_autofix(db: Session, review_id: int) -> AutofixResult:
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

    if review.autofix_status == "pending_approval":
        raise AutofixError(
            f"Auto-fix branch already exists for review {review_id} "
            f"(branch: {review.autofix_branch}). Approve or reject it first."
        )

    # Gather fixable findings
    fixable_findings = (
        db.query(Finding)
        .filter(Finding.review_id == review_id, Finding.fix_data.isnot(None))
        .all()
    )

    if not fixable_findings:
        raise AutofixError(f"Review {review_id} has no fixable findings.")

    settings = get_settings()
    token = settings.require("github_token")

    branch_name = f"codeguardian/autofix/{review_id}"

    result = _apply_fixes_and_push(
        review=review,
        findings=fixable_findings,
        branch_name=branch_name,
        token=token,
    )

    if not result.applied_fixes:
        raise AutofixError(
            "All fixes failed re-validation against current code. "
            "The PR may have been updated since the review."
        )

    review.autofix_status = "pending_approval"
    review.autofix_branch = branch_name
    db.commit()

    result.branch = branch_name
    return result


def approve_autofix(
    db: Session,
    review_id: int,
    approved_by: str,
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

    review.autofix_status = "approved"
    review.autofix_approved_by = approved_by
    review.autofix_approved_at = datetime.now(timezone.utc)
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

    review.autofix_status = "rejected"
    db.commit()


def _apply_fixes_and_push(
    review: Review,
    findings: list[Finding],
    branch_name: str,
    token: str,
) -> AutofixResult:
    """Clone, apply fixes with re-validation, commit, and push."""
    result = AutofixResult()

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_url = f"https://x-access-token:{token}@github.com/{review.repo_full_name}.git"
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
            _run_git(["add", "-A"], cwd=workspace)
            _run_git(
                ["commit", "-m", f"codeguardian: auto-fix for review #{review.id}"],
                cwd=workspace,
            )
            _run_git(["push", "origin", branch_name], cwd=workspace)
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
    test_dir = os.path.join(workspace, "tests")
    os.makedirs(test_dir, exist_ok=True)
    test_filename = f"test_{target_function}.py"
    test_path = os.path.join(test_dir, test_filename)

    with open(test_path, "w", encoding="utf-8") as f:
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
    full_path = os.path.join(workspace, target_file)
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

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                # Find the line after the function def (colon line)
                insert_line = node.body[0].lineno - 1  # 0-indexed

                # Check if there's already a docstring
                if (
                    isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, (ast.Constant, ast.Str))
                ):
                    # Replace existing docstring
                    old_end = node.body[0].end_lineno  # 1-indexed
                    indent = "    " * (node.col_offset // 4 + 1)
                    new_docstring_lines = _format_docstring(docstring, indent)
                    lines[insert_line:old_end] = new_docstring_lines
                else:
                    # Insert new docstring
                    indent = "    " * (node.col_offset // 4 + 1)
                    new_docstring_lines = _format_docstring(docstring, indent)
                    lines[insert_line:insert_line] = new_docstring_lines

                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True

    return False


def _format_docstring(docstring: str, indent: str) -> list[str]:
    """Format a docstring into lines with proper indentation and triple quotes."""
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
    )
