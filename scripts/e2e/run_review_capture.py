import sys
import os
import logging
from backend.db.database import get_db
from backend.services.review_service import run_review

# Setup logging to file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("review_run.log"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

db = next(get_db())
# Review 36 is encode/httpx PR #1
print("Running review 36 synchronously to capture logs...")
run_review(db, 36)
print("Done.")
