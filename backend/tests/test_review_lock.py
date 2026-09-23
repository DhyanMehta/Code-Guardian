import pytest
from unittest.mock import patch, MagicMock
from backend.services.review_service import run_review, _review_run_lock
from backend.db.models import Review

def test_review_run_lock_released_on_exception():
    """Verify that an exception in the graph execution does not permanently hold the lock."""
    # Ensure lock is in a clean state
    assert _review_run_lock.acquire(blocking=False), "Lock should be free initially"
    _review_run_lock.release()

    # Mock DB, Review, and checkout_pr
    db_mock = MagicMock()
    review_mock = MagicMock(spec=Review)
    review_mock.id = 1
    review_mock.repo_full_name = "test/repo"
    review_mock.commit_sha = "abcd123"
    db_mock.get.return_value = review_mock

    # Mock settings to avoid auth errors
    with patch("backend.services.review_service.start_review", return_value=True), \
         patch("backend.services.review_service.get_settings") as settings_mock, \
         patch("backend.services.review_service.checkout_pr") as checkout_mock, \
         patch("backend.services.review_service._execute_graph_and_persist") as execute_mock:
        
        settings_mock.return_value.require.return_value = "dummy_token"
        
        # Make checkout_pr return a dummy context manager
        workspace_ctx = MagicMock()
        workspace_ctx.path = "/dummy/path"
        checkout_mock.return_value.__enter__.return_value = workspace_ctx

        # Simulate exception during graph execution
        execute_mock.side_effect = RuntimeError("Simulated graph failure")

        # Call run_review
        run_review(db_mock, 1)

    # Assert the lock was released correctly
    assert _review_run_lock.acquire(blocking=False), "Lock should be released after exception"
    _review_run_lock.release()

    # Verify review status was set to failed
    assert review_mock.status == "failed"
