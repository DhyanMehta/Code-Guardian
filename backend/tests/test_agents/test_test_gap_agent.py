"""Tests for the Test-Gap Agent (backend/agents/test_gap_agent.py)."""

from __future__ import annotations

import json
import os
import textwrap

from backend.agents.test_gap_agent import TestGapAgent, TestGapAgentResult
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


SAMPLE_DIFF = """\
--- a/app.py
+++ b/app.py
@@ -0,0 +1,8 @@
+def calculate_risk(score, threshold):
+    if score > threshold:
+        return "high"
+    elif score > threshold / 2:
+        return "medium"
+    return "low"
+
+
"""

DIFF_TWO_FUNCTIONS = """\
--- a/app.py
+++ b/app.py
@@ -0,0 +1,12 @@
+def calculate_risk(score, threshold):
+    if score > threshold:
+        return "high"
+    return "low"
+
+def simple_add(a, b):
+    return a + b
+
+def validate_input(data):
+    if not data:
+        raise ValueError("empty")
+    return data
"""

DIFF_MODIFY_EXISTING = """\
--- a/utils.py
+++ b/utils.py
@@ -2,3 +2,5 @@
 def existing_func(x):
-    return x
+    if x > 0:
+        return x * 2
+    return 0
"""


class TestTestGapAgentHappyPath:
    def test_identifies_new_function_without_test(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                if score > threshold:
                    return "high"
                elif score > threshold / 2:
                    return "medium"
                return "low"
        """)

        llm_response = json.dumps({
            "test_code": "from app import calculate_risk\n\ndef test_calculate_risk():\n    assert calculate_risk(10, 5) == 'high'\n",
            "imports": ["app"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.gaps) == 1
        assert result.gaps[0].function.name == "calculate_risk"
        assert len(result.drafted_tests) == 1
        assert result.drafted_tests[0].target_function == "calculate_risk"
        assert "calculate_risk" in result.drafted_tests[0].test_code

    def test_modified_function_without_test_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "utils.py", """\
            def existing_func(x):
                if x > 0:
                    return x * 2
                return 0
        """)

        llm_response = json.dumps({
            "test_code": "from utils import existing_func\n\ndef test_existing_func():\n    assert existing_func(5) == 10\n",
            "imports": ["utils"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(DIFF_MODIFY_EXISTING, ["utils.py"], str(tmp_path))

        assert result.has_gaps
        assert result.gaps[0].function.name == "existing_func"

    def test_function_with_existing_test_not_flagged(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                if score > threshold:
                    return "high"
                return "low"

            def validate_input(data):
                if not data:
                    raise ValueError("empty")
                return data
        """)
        _write_file(tmp_path, "tests/test_app.py", """\
            from app import validate_input

            def test_validate_input():
                assert validate_input("hello") == "hello"
        """)

        llm_response = json.dumps({
            "test_code": "from app import calculate_risk\n\ndef test_calculate_risk():\n    assert calculate_risk(10, 5) == 'high'\n",
            "imports": ["app"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(DIFF_TWO_FUNCTIONS, ["app.py"], str(tmp_path))

        # validate_input is tested, calculate_risk is not
        gap_names = [g.function.name for g in result.gaps]
        assert "calculate_risk" in gap_names
        assert "validate_input" not in gap_names

    def test_multiple_gaps_ranked_by_complexity(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                if score > threshold:
                    return "high"
                elif score > threshold / 2:
                    return "medium"
                return "low"

            def simple_add(a, b):
                return a + b

            def validate_input(data):
                if not data:
                    raise ValueError("empty")
                return data
        """)

        llm = _FakeLLM(json.dumps({"test_code": "", "imports": []}))
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(DIFF_TWO_FUNCTIONS, ["app.py"], str(tmp_path))

        assert len(result.gaps) >= 2
        # Higher complexity function should rank first
        assert result.gaps[0].risk_score >= result.gaps[1].risk_score


class TestTestGapAgentNoWorkPaths:
    def test_empty_diff_returns_early(self, tmp_path) -> None:
        llm = _FakeLLM("should not be called")
        agent = TestGapAgent(llm_client=llm)

        result = agent.run("", ["app.py"], str(tmp_path))

        assert not result.has_gaps
        assert llm.calls == 0
        assert any("empty diff" in n.lower() for n in result.notes)

    def test_no_python_files_changed(self, tmp_path) -> None:
        llm = _FakeLLM("should not be called")
        agent = TestGapAgent(llm_client=llm)

        diff = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n+hello\n"
        result = agent.run(diff, ["README.md"], str(tmp_path))

        assert not result.has_gaps
        assert llm.calls == 0
        assert any("no python" in n.lower() for n in result.notes)

    def test_all_functions_already_tested(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                if score > threshold:
                    return "high"
                return "low"
        """)
        _write_file(tmp_path, "tests/test_app.py", """\
            from app import calculate_risk

            def test_calculate_risk():
                assert calculate_risk(10, 5) == "high"
        """)

        llm = _FakeLLM("should not be called")
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert not result.has_gaps
        assert llm.calls == 0
        assert any("all modified" in n.lower() for n in result.notes)


class TestTestGapAgentAntiHallucination:
    def test_drafted_test_referencing_nonexistent_function_dropped(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                return "high" if score > threshold else "low"
        """)

        # LLM returns a test that calls "foo" instead of "calculate_risk"
        llm_response = json.dumps({
            "test_code": "from app import foo\n\ndef test_foo():\n    assert foo() == 'ok'\n",
            "imports": ["app"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.drafted_tests) == 0

    def test_drafted_test_importing_nonexistent_module_dropped(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                return "high" if score > threshold else "low"
        """)

        llm_response = json.dumps({
            "test_code": "from backend.nonexistent import calculate_risk\n\ndef test_calculate_risk():\n    assert calculate_risk(10, 5) == 'high'\n",
            "imports": ["backend.nonexistent"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.drafted_tests) == 0

    def test_valid_drafted_test_accepted(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                return "high" if score > threshold else "low"
        """)

        llm_response = json.dumps({
            "test_code": "from app import calculate_risk\n\ndef test_calculate_risk():\n    assert calculate_risk(10, 5) == 'high'\n",
            "imports": ["app"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.drafted_tests) == 1
        assert result.drafted_tests[0].imports_valid is True


class TestTestGapAgentErrorHandling:
    def test_ast_parse_failure_skips_file_gracefully(self, tmp_path) -> None:
        # Write invalid Python
        _write_file(tmp_path, "bad.py", """\
            def broken(
                # missing closing paren
        """)
        _write_file(tmp_path, "good.py", """\
            def good_func(x):
                return x + 1
        """)

        diff = (
            "--- a/bad.py\n+++ b/bad.py\n@@ -0,0 +1,2 @@\n+def broken(\n+    # missing\n"
            "--- a/good.py\n+++ b/good.py\n@@ -0,0 +1,2 @@\n+def good_func(x):\n+    return x + 1\n"
        )

        llm_response = json.dumps({
            "test_code": "from good import good_func\n\ndef test_good_func():\n    assert good_func(1) == 2\n",
            "imports": ["good"],
        })
        llm = _FakeLLM(llm_response)
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(diff, ["bad.py", "good.py"], str(tmp_path))

        # good_func should still be detected despite bad.py failing
        gap_names = [g.function.name for g in result.gaps]
        assert "good_func" in gap_names

    def test_llm_failure_returns_gaps_without_drafts(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                return "high" if score > threshold else "low"
        """)

        llm = _FakeLLM(LLMError("groq exploded"))
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.drafted_tests) == 0
        assert any("failed" in n.lower() for n in result.notes)

    def test_unparseable_llm_response_no_drafts(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def calculate_risk(score, threshold):
                return "high" if score > threshold else "low"
        """)

        llm = _FakeLLM("this is not JSON!!!")
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(SAMPLE_DIFF, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert len(result.drafted_tests) == 0


class TestTestGapAgentEdgeCases:
    def test_private_functions_still_detected(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def _helper(x):
                if x < 0:
                    raise ValueError("negative")
                return x * 2
        """)

        diff = "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,4 @@\n+def _helper(x):\n+    if x < 0:\n+        raise ValueError(\"negative\")\n+    return x * 2\n"

        llm = _FakeLLM(json.dumps({
            "test_code": "from app import _helper\n\ndef test__helper():\n    assert _helper(5) == 10\n",
            "imports": ["app"],
        }))
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(diff, ["app.py"], str(tmp_path))

        assert result.has_gaps
        assert result.gaps[0].function.name == "_helper"

    def test_class_methods_detected(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            class Calculator:
                def multiply(self, a, b):
                    return a * b
        """)

        diff = "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,3 @@\n+class Calculator:\n+    def multiply(self, a, b):\n+        return a * b\n"

        llm = _FakeLLM(json.dumps({
            "test_code": "from app import Calculator\n\ndef test_multiply():\n    c = Calculator()\n    assert c.multiply(2, 3) == 6\n",
            "imports": ["app"],
        }))
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(diff, ["app.py"], str(tmp_path))

        assert result.has_gaps
        method = result.gaps[0].function
        assert method.name == "multiply"
        assert method.is_method is True
        assert method.class_name == "Calculator"

    def test_nested_functions_skipped(self, tmp_path) -> None:
        _write_file(tmp_path, "app.py", """\
            def outer(x):
                def inner(y):
                    return y + 1
                return inner(x)
        """)

        diff = "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,4 @@\n+def outer(x):\n+    def inner(y):\n+        return y + 1\n+    return inner(x)\n"

        llm = _FakeLLM(json.dumps({
            "test_code": "from app import outer\n\ndef test_outer():\n    assert outer(5) == 6\n",
            "imports": ["app"],
        }))
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(diff, ["app.py"], str(tmp_path))

        # Only outer should be detected, not inner
        gap_names = [g.function.name for g in result.gaps]
        assert "outer" in gap_names
        assert "inner" not in gap_names

    def test_attribute_call_in_test_matches(self, tmp_path) -> None:
        """AST-based matching catches obj.method() calls, not just bare calls."""
        _write_file(tmp_path, "app.py", """\
            class Service:
                def process(self, data):
                    return data.upper()
        """)
        _write_file(tmp_path, "tests/test_app.py", """\
            from app import Service

            def test_service():
                s = Service()
                result = s.process("hello")
                assert result == "HELLO"
        """)

        diff = "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,3 @@\n+class Service:\n+    def process(self, data):\n+        return data.upper()\n"

        llm = _FakeLLM("should not be called")
        agent = TestGapAgent(llm_client=llm)

        result = agent.run(diff, ["app.py"], str(tmp_path))

        # "process" is called via s.process() in tests — should be detected
        gap_names = [g.function.name for g in result.gaps]
        assert "process" not in gap_names
