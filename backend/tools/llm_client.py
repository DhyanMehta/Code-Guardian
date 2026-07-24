"""Groq LLM client wrapper.

Thin wrapper around the Groq client with timeouts, retries, and explicit error
handling. The LLM is only used to explain / triage / prioritize deterministic tool
output — never to originate a finding. Placeholder for Session 2.
"""
