"""Security Agent.

Runs deterministic scanners (Semgrep, Bandit, Gitleaks) and uses the LLM only to
triage / explain / prioritize the raw scanner output. The LLM must never invent a
finding. Placeholder for Session 2.
"""
