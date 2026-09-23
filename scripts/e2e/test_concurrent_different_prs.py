import sys
import os
import time
import asyncio
import httpx
from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.e2e._common import post_webhook, pr_payload

def post_concurrent(repo: str, pr: int, sha: str):
    payload = pr_payload(repo_full_name=repo, pr_number=pr, head_sha=sha, head_ref="master")
    resp = post_webhook(payload)
    print(f"[{datetime.now().isoformat()}] Response for {repo}: {resp.status_code}")

def main():
    import threading
    print(f"[{datetime.now().isoformat()}] Triggering PR #1 (httpx)")
    t1 = threading.Thread(target=post_concurrent, args=("encode/httpx", 1, "b5addb64f0161ff6bfe94c124ef76f6a1fba5254"))
    t2 = threading.Thread(target=post_concurrent, args=("theskumar/python-dotenv", 1, "a00cb2eed0704cd6d2071b2004c37e95ccc86ee5"))
    
    t1.start()
    time.sleep(0.1)
    t2.start()
    
    t1.join()
    t2.join()
    
    print("Waiting 60 seconds for both reviews to process...")
    for i in range(6):
        time.sleep(10)
        print(f"... elapsed: {(i+1)*10}s")

if __name__ == "__main__":
    main()

