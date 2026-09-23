"""Read-only: which real review exercises which auto-fix panel state.

The panel is a state machine over `autofix.status` plus three disable reasons. This
lists what the live database can actually demonstrate, so the verification run uses
real rows instead of invented ones.
"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    listing = get("/reviews?limit=200")
    print(
        f"{'rev':>4} {'status':<10} {'fork':<6} {'fixable':>7} {'autofix':<16} "
        f"{'branch':<28} panel state it exercises"
    )
    print("-" * 118)
    for item in sorted(listing["items"], key=lambda entry: entry["id"]):
        detail = get(f"/reviews/{item['id']}")
        autofix = detail["autofix"]
        status = autofix["status"]

        if status == "pending_approval":
            state = "pending_approval (approve/reject form)"
        elif status == "approved":
            state = "approved (not-merged notice)"
        elif status == "rejected":
            state = "rejected"
        elif item["status"] != "completed":
            state = f"disabled: review is {item['status']}"
        elif item["is_fork"]:
            state = "disabled: fork PR"
        elif item["fixable_count"] == 0:
            state = "disabled: no fixable findings"
        else:
            state = "enabled: create branch"

        print(
            f"{item['id']:>4} {item['status']:<10} {str(item['is_fork']):<6} "
            f"{item['fixable_count']:>7} {str(status):<16} "
            f"{str(autofix['branch'])[:27]:<28} {state}"
        )

    print("\nreport endpoint status per review:")
    for item in sorted(listing["items"], key=lambda entry: entry["id"]):
        request = urllib.request.Request(f"{BASE}/reviews/{item['id']}/report")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                code, note = response.status, f"{len(response.read())} bytes"
        except urllib.error.HTTPError as error:  # noqa: PERF203
            code, note = error.code, error.read().decode("utf-8")[:80]
        print(f"  review {item['id']:>3} -> HTTP {code}  {note}")


if __name__ == "__main__":
    main()
