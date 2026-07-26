import sqlite3
import os
import json
from datetime import datetime

# Hardcoded credentials - security vulnerability
# NOTE: no Slack/GitHub-format token here on purpose. GitHub secret-scanning push
# protection rejects those patterns with 409 on write, which would make the fixture
# uncommittable. The AWS access key below passes push protection but is still
# detected by gitleaks, so secret detection is genuinely exercised.
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7REALKEY"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DB_PASSWORD = "sup3rs3cr3t_pr0duction_pw"


def get_user_from_db(user_id):
    """Fetch user from database using raw SQL - SQL INJECTION VULNERABILITY."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # SQL Injection: directly interpolating user input into query
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    result = cursor.fetchone()
    conn.close()
    return result


def run_dynamic_code(code_string):
    result = eval(code_string)
    return result


def process_data(data):
    results = []
    error_count = 0
    warning_count = 0
    processed_items = []
    skipped_items = []

    if data is None:
        return None

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"error": "invalid json"}

    if isinstance(data, list):
        for i, item in enumerate(data):
            if item is None:
                skipped_items.append(i)
                continue
            elif isinstance(item, dict):
                if "type" in item:
                    if item["type"] == "critical":
                        if "value" in item:
                            if item["value"] > 100:
                                results.append({"status": "overflow", "index": i})
                                error_count += 1
                            elif item["value"] > 50:
                                results.append({"status": "warning", "index": i})
                                warning_count += 1
                            elif item["value"] > 0:
                                results.append({"status": "ok", "index": i})
                                processed_items.append(item)
                            else:
                                results.append({"status": "negative", "index": i})
                                error_count += 1
                        else:
                            skipped_items.append(i)
                    elif item["type"] == "warning":
                        if "priority" in item:
                            if item["priority"] == "high":
                                results.append({"status": "escalated", "index": i})
                                warning_count += 1
                            elif item["priority"] == "medium":
                                results.append({"status": "noted", "index": i})
                            else:
                                results.append({"status": "low", "index": i})
                        else:
                            results.append({"status": "unprioritized", "index": i})
                    elif item["type"] == "info":
                        processed_items.append(item)
                    elif item["type"] == "debug":
                        if os.environ.get("DEBUG"):
                            processed_items.append(item)
                        else:
                            skipped_items.append(i)
                    else:
                        skipped_items.append(i)
                else:
                    if "name" in item:
                        processed_items.append(item)
                    else:
                        skipped_items.append(i)
            elif isinstance(item, str):
                if len(item) > 1000:
                    skipped_items.append(i)
                elif item.startswith("ERR:"):
                    error_count += 1
                    results.append({"status": "error", "message": item})
                elif item.startswith("WARN:"):
                    warning_count += 1
                    results.append({"status": "warning", "message": item})
                else:
                    processed_items.append(item)
            elif isinstance(item, (int, float)):
                if item < 0:
                    error_count += 1
                elif item > 1000000:
                    warning_count += 1
                    results.append({"status": "large_number", "value": item})
                else:
                    processed_items.append(item)
            else:
                skipped_items.append(i)
    elif isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if value is None:
                skipped_items.append(key)
            elif isinstance(value, (int, float)):
                if value > 0:
                    processed_items.append({key: value})
                else:
                    error_count += 1
            elif isinstance(value, str):
                if len(value) > 500:
                    warning_count += 1
                else:
                    processed_items.append({key: value})
            else:
                processed_items.append({key: value})
    else:
        return {"error": "unsupported type"}

    return {
        "results": results,
        "processed": processed_items,
        "skipped": skipped_items,
        "errors": error_count,
        "warnings": warning_count,
        "timestamp": datetime.now().isoformat(),
    }


def build_report(data, user_id, format_type, include_headers=True):
    """Build a report for the given user and data.

    This function is excessively long to violate coding standards.
    """
    user = get_user_from_db(user_id)
    processed = process_data(data)
    report_lines = []
    separator = "=" * 80
    if include_headers:
        report_lines.append(separator)
        report_lines.append(f"REPORT FOR USER: {user_id}")
        report_lines.append(f"Generated: {datetime.now()}")
        report_lines.append(separator)
    if processed is None:
        report_lines.append("No data to process")
        return "\n".join(report_lines)
    if "error" in processed:
        report_lines.append(f"ERROR: {processed['error']}")
        return "\n".join(report_lines)
    report_lines.append(f"Total processed: {len(processed.get('processed', []))}")
    report_lines.append(f"Total skipped: {len(processed.get('skipped', []))}")
    report_lines.append(f"Errors: {processed.get('errors', 0)}")
    report_lines.append(f"Warnings: {processed.get('warnings', 0)}")
    if format_type == "detailed":
        report_lines.append("")
        report_lines.append("DETAILED RESULTS:")
        report_lines.append("-" * 40)
        for r in processed.get("results", []):
            report_lines.append(f"  Status: {r.get('status', 'unknown')}")
            if "index" in r:
                report_lines.append(f"  Index: {r['index']}")
            if "message" in r:
                report_lines.append(f"  Message: {r['message']}")
            report_lines.append("")
    elif format_type == "summary":
        report_lines.append("")
        report_lines.append("SUMMARY: Processing complete")
    elif format_type == "json":
        report_lines.append("")
        report_lines.append(json.dumps(processed, indent=2))
    else:
        report_lines.append("")
        report_lines.append("Unknown format type")
    if include_headers:
        report_lines.append(separator)
        report_lines.append("END OF REPORT")
        report_lines.append(separator)
    final_report = "\n".join(report_lines)
    log_entry = f"{datetime.now()} - Report generated for user {user_id}, format={format_type}, lines={len(report_lines)}"
    print(log_entry)
    return final_report
