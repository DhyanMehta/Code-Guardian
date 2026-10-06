"""Tests for the Documentation Agent (backend/agents/documentation_agent.py)."""

from __future__ import annotations

import json
import os
import textwrap

from backend.agents.documentation_agent import DocumentationAgent, DocAgentResult
from backend.tools.llm_client import LLMError


class _FakeLLM:
    """Fake LLM client returning a preset completion."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.calls = 0

    def complete(self, **kwargs) -> str:
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _write_file(tmp_path, rel_path: str, content: str) -> None:
    """Write a file at a relative path under tmp_path."""
    full = tmp_path / rel_path.replace("/", os.sep)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(textwrap.dedent(content), encoding="utf-8")


DIFF_NEW_PUBLIC_FUNC = """\
--- a/service.py
+++ b/service.py
@@ -0,0 +1,5 @@
+def process_payment(amount, currency, user_id):
+    if amount <= 0:
+        raise ValueError("Invalid amount")
+    # process logic here
+    return {"status": "ok", "amount": amount}
"""

DIFF_OUTDATED_DOCSTRING = """\
--- a/service.py
+++ b/service.py
@@ -1,6 +1,6 @@
-def process_payment(uid, amount):
+def process_payment(user_id, amount, currency):
     \"\"\"Process a payment.

     Args:
-        uid: The user identifier.
+        user_id: The user identifier.
         amount: Payment amount.
     \"\"\"
     return {"status": "ok"}
"""

DIFF_PRIVATE_FUNC = """\
--- a/service.py
+++ b/service.py
@@ -0,0 +1,3 @@
+def _internal_helper(data):
+    # no docstring, but private
+    return data.strip()
"""

DIFF_TRIVIAL_FUNC = """\
--- a/service.py
+++ b/service.py
@@ -0,0 +1,3 @@
+class Config:
+    def get_name(self):
+        return self._name
"""

DIFF_COMPLETE_DOCSTRING = """\
--- a/service.py
+++ b/service.py
@@ -0,0 +1,10 @@
+def process_payment(amount, currency):
+    \"\"\"Process a payment transaction.
+
+    Args:
+        amount: The payment amount in minor units.
+        currency: ISO 4217 currency code.
+
+    Returns:
+        A dict with the transaction status.
+    \"\"\"
+    return {"status": "ok"}
"""


class TestDocAgentHappyPath:
    def test_missing_docstring_on_new_public_function_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                if amount <= 0:
                    raise ValueError("Invalid amount")
                return {"status": "ok", "amount": amount}
        """)

        llm_response = json.dumps({
            "docstring": "Process a payment transaction.\n\nArgs:\n    amount: The payment amount.\n    currency: ISO currency code.\n    user_id: The user identifier.",
            "params_documented": ["amount", "currency", "user_id"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert len(result.flagged_functions) == 1
        assert result.flagged_functions[0].function.name == "process_payment"
        assert result.flagged_functions[0].reason == "missing"
        assert len(result.drafted_docstrings) == 1
        assert result.drafted_docstrings[0].target_function == "process_payment"

    def test_outdated_docstring_with_renamed_param_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(user_id, amount, currency):
                \"\"\"Process a payment.

                Args:
                    uid: The user identifier.
                    amount: Payment amount.
                \"\"\"
                return {"status": "ok"}
        """)

        llm_response = json.dumps({
            "docstring": "Process a payment.\n\nArgs:\n    user_id: The user identifier.\n    amount: Payment amount.\n    currency: The currency code.",
            "params_documented": ["user_id", "amount", "currency"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_OUTDATED_DOCSTRING, ["service.py"], str(tmp_path))

        assert result.has_findings
        target = result.flagged_functions[0]
        assert target.reason == "outdated"
        assert target.existing_docstring is not None

    def test_new_param_not_in_docstring_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def send_email(recipient, subject, timeout):
                \"\"\"Send an email notification.

                Args:
                    recipient: Email address.
                    subject: Email subject line.
                \"\"\"
                return True
        """)

        diff = "--- a/service.py\n+++ b/service.py\n@@ -1,5 +1,7 @@\n-def send_email(recipient, subject):\n+def send_email(recipient, subject, timeout):\n     \"\"\"Send an email notification.\n \n     Args:\n         recipient: Email address.\n         subject: Email subject line.\n     \"\"\"\n     return True\n"

        llm_response = json.dumps({
            "docstring": "Send an email notification.\n\nArgs:\n    recipient: Email address.\n    subject: Email subject line.\n    timeout: Request timeout in seconds.",
            "params_documented": ["recipient", "subject", "timeout"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(diff, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert result.flagged_functions[0].reason == "incomplete"

    def test_valid_drafted_docstring_accepted(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                if amount <= 0:
                    raise ValueError("Invalid amount")
                return {"status": "ok", "amount": amount}
        """)

        llm_response = json.dumps({
            "docstring": "Process a payment.\n\nArgs:\n    amount: Payment amount.\n    currency: Currency code.\n    user_id: User identifier.",
            "params_documented": ["amount", "currency", "user_id"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert len(result.drafted_docstrings) == 1
        assert result.drafted_docstrings[0].params_valid is True


class TestDocAgentNoWorkPaths:
    def test_empty_diff_returns_early(self, tmp_path) -> None:
        llm = _FakeLLM("should not be called")
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run("", ["service.py"], str(tmp_path))

        assert not result.has_findings
        assert llm.calls == 0
        assert any("empty diff" in n.lower() for n in result.notes)

    def test_no_python_files_changed(self, tmp_path) -> None:
        llm = _FakeLLM("should not be called")
        agent = DocumentationAgent(llm_client=llm)

        diff = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n+hello\n"
        result = agent.run(diff, ["README.md"], str(tmp_path))

        assert not result.has_findings
        assert llm.calls == 0
        assert any("no python" in n.lower() for n in result.notes)

    def test_private_function_without_docstring_not_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def _internal_helper(data):
                return data.strip()
        """)

        llm = _FakeLLM("should not be called")
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_PRIVATE_FUNC, ["service.py"], str(tmp_path))

        assert not result.has_findings
        assert llm.calls == 0

    def test_trivial_function_not_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            class Config:
                def get_name(self):
                    return self._name
        """)

        llm = _FakeLLM("should not be called")
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_TRIVIAL_FUNC, ["service.py"], str(tmp_path))

        # get_name is trivial (1 statement, only self param) — not flagged
        # Config class itself may be flagged (public, no docstring) — that's correct
        func_names = [f.function.name for f in result.flagged_functions]
        assert "get_name" not in func_names

    def test_function_with_complete_docstring_not_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency):
                \"\"\"Process a payment transaction.

                Args:
                    amount: The payment amount in minor units.
                    currency: ISO 4217 currency code.

                Returns:
                    A dict with the transaction status.
                \"\"\"
                return {"status": "ok"}
        """)

        llm = _FakeLLM("should not be called")
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_COMPLETE_DOCSTRING, ["service.py"], str(tmp_path))

        assert not result.has_findings
        assert llm.calls == 0


class TestDocAgentAntiHallucination:
    def test_drafted_docstring_referencing_nonexistent_param_dropped(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                return {"status": "ok"}
        """)

        # LLM hallucinates a "data" param that doesn't exist
        llm_response = json.dumps({
            "docstring": "Process a payment.\n\nArgs:\n    amount: Amount.\n    data: The payload.",
            "params_documented": ["amount", "data"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert len(result.drafted_docstrings) == 0

    def test_drafted_docstring_with_only_real_params_accepted(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                return {"status": "ok"}
        """)

        llm_response = json.dumps({
            "docstring": "Process a payment.\n\nArgs:\n    amount: The amount.\n    currency: Code.",
            "params_documented": ["amount", "currency"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        # Documenting a subset of real params is fine (not hallucinating)
        assert len(result.drafted_docstrings) == 1


class TestDocAgentErrorHandling:
    def test_ast_parse_failure_skips_file(self, tmp_path) -> None:
        _write_file(tmp_path, "bad.py", """\
            def broken(
        """)
        _write_file(tmp_path, "good.py", """\
            def good_func(x, y):
                return x + y
        """)

        diff = (
            "--- a/bad.py\n+++ b/bad.py\n@@ -0,0 +1,1 @@\n+def broken(\n"
            "--- a/good.py\n+++ b/good.py\n@@ -0,0 +1,2 @@\n+def good_func(x, y):\n+    return x + y\n"
        )

        llm_response = json.dumps({
            "docstring": "Add two values.\n\nArgs:\n    x: First value.\n    y: Second value.",
            "params_documented": ["x", "y"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(diff, ["bad.py", "good.py"], str(tmp_path))

        # good_func should still be flagged
        names = [f.function.name for f in result.flagged_functions]
        assert "good_func" in names

    def test_llm_failure_returns_flags_without_drafts(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                return {"status": "ok"}
        """)

        llm = _FakeLLM(LLMError("groq exploded"))
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert len(result.drafted_docstrings) == 0
        assert any("failed" in n.lower() for n in result.notes)

    def test_unparseable_llm_response(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                return {"status": "ok"}
        """)

        llm = _FakeLLM("this is not JSON at all!!!")
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert len(result.drafted_docstrings) == 0

    def test_code_fenced_response_parsed(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            def process_payment(amount, currency, user_id):
                return {"status": "ok"}
        """)

        fenced = (
            "```json\n"
            + json.dumps({
                "docstring": "Process payment.\n\nArgs:\n    amount: Amount.",
                "params_documented": ["amount"],
            })
            + "\n```"
        )
        llm = _FakeLLM(fenced)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(DIFF_NEW_PUBLIC_FUNC, ["service.py"], str(tmp_path))

        assert len(result.drafted_docstrings) == 1


class TestDocAgentEdgeCases:
    def test_class_docstring_detected(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            class PaymentService:
                def process(self, amount):
                    return amount * 2
        """)

        diff = "--- a/service.py\n+++ b/service.py\n@@ -0,0 +1,3 @@\n+class PaymentService:\n+    def process(self, amount):\n+        return amount * 2\n"

        llm_response = json.dumps({
            "docstring": "Service for processing payments.",
            "params_documented": [],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(diff, ["service.py"], str(tmp_path))

        # Class itself should be flagged for missing docstring
        names = [f.function.name for f in result.flagged_functions]
        assert "PaymentService" in names

    def test_async_function_handled(self, tmp_path) -> None:
        _write_file(tmp_path, "service.py", """\
            async def fetch_data(url, timeout):
                return {"data": "ok"}
        """)

        diff = "--- a/service.py\n+++ b/service.py\n@@ -0,0 +1,2 @@\n+async def fetch_data(url, timeout):\n+    return {\"data\": \"ok\"}\n"

        llm_response = json.dumps({
            "docstring": "Fetch data from a URL.\n\nArgs:\n    url: The endpoint URL.\n    timeout: Request timeout.",
            "params_documented": ["url", "timeout"],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(diff, ["service.py"], str(tmp_path))

        assert result.has_findings
        assert result.flagged_functions[0].function.name == "fetch_data"
        assert len(result.drafted_docstrings) == 1

    def test_dunder_methods_not_flagged(self, tmp_path) -> None:
        """__init__ and other dunder methods start with _ so are skipped."""
        _write_file(tmp_path, "service.py", """\
            class Foo:
                def __init__(self, x):
                    self.x = x
        """)

        diff = "--- a/service.py\n+++ b/service.py\n@@ -0,0 +1,3 @@\n+class Foo:\n+    def __init__(self, x):\n+        self.x = x\n"

        llm_response = json.dumps({
            "docstring": "A simple container class.",
            "params_documented": [],
        })
        llm = _FakeLLM(llm_response)
        agent = DocumentationAgent(llm_client=llm)

        result = agent.run(diff, ["service.py"], str(tmp_path))

        # __init__ starts with _ so should be skipped
        func_names = [f.function.name for f in result.flagged_functions]
        assert "__init__" not in func_names
        # Foo class itself is public and may be flagged — that's correct
        assert "Foo" in func_names
