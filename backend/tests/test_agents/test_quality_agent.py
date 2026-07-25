"""Tests for the Quality Agent (backend/agents/quality_agent.py)."""

from __future__ import annotations

import json

from backend.agents.quality_agent import QualityAgent, QualityAgentResult
from backend.rag.retriever import RetrievalResult, RetrievedPassage
from backend.tools.llm_client import LLMError


def _passage(text: str, source: str = "standards.md", distance: float = 0.2) -> RetrievedPassage:
    return RetrievedPassage(
        text=text, source_file=source, distance=distance, chunk_id="abc123"
    )


def _retrieval_with_passages(passages: list[RetrievedPassage]) -> RetrievalResult:
    r = RetrievalResult(query_text="test query")
    r.passages = passages
    return r


def _empty_retrieval(error: str = "No relevant passages found.") -> RetrievalResult:
    return RetrievalResult(query_text="test query", error=error)


class _FakeRetriever:
    """Returns a preset RetrievalResult regardless of input."""

    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.calls = 0

    def __call__(self, query_text: str, **kwargs) -> RetrievalResult:
        self.calls += 1
        return self._result


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


SAMPLE_DIFF = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,5 @@
+def getUserName():
+    return "test"
+
 def main():
     pass
"""


class TestQualityAgentHappyPath:
    def test_grounded_finding_accepted(self) -> None:
        passages = [_passage("Use snake_case for all function names.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm_response = json.dumps({
            "findings": [
                {
                    "passage_index": 0,
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "snake_case naming",
                    "explanation": "getUserName should be get_user_name",
                    "severity": "medium",
                }
            ]
        })
        llm = _FakeLLM(llm_response)
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run(SAMPLE_DIFF, ["app.py"])

        assert result.has_findings
        assert len(result.findings) == 1
        f = result.findings[0]
        assert f.file_path == "app.py"
        assert f.line == 1
        assert f.rule_violated == "snake_case naming"
        assert f.severity == "medium"
        assert "snake_case" in f.cited_passage
        assert f.source_file == "standards.md"

    def test_multiple_findings_from_multiple_passages(self) -> None:
        passages = [
            _passage("Use snake_case for functions."),
            _passage("All public functions require type annotations."),
        ]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm_response = json.dumps({
            "findings": [
                {
                    "passage_index": 0,
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "naming",
                    "explanation": "camelCase used",
                    "severity": "medium",
                },
                {
                    "passage_index": 1,
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "type annotations",
                    "explanation": "no return type",
                    "severity": "low",
                },
            ]
        })
        agent = QualityAgent(
            llm_client=_FakeLLM(llm_response), retriever_fn=retriever
        )

        result = agent.run(SAMPLE_DIFF)

        assert len(result.findings) == 2
        assert result.findings[0].source_file == "standards.md"
        assert result.findings[1].rule_violated == "type annotations"


class TestQualityAgentAntiHallucination:
    def test_invalid_passage_index_dropped(self) -> None:
        passages = [_passage("Rule A content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm_response = json.dumps({
            "findings": [
                {
                    "passage_index": 0,
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "real rule",
                    "explanation": "valid",
                    "severity": "medium",
                },
                {
                    "passage_index": 5,
                    "file_path": "app.py",
                    "line": 2,
                    "rule_violated": "invented rule",
                    "explanation": "hallucinated",
                    "severity": "high",
                },
            ]
        })
        agent = QualityAgent(
            llm_client=_FakeLLM(llm_response), retriever_fn=retriever
        )

        result = agent.run(SAMPLE_DIFF)

        assert len(result.findings) == 1
        assert result.findings[0].rule_violated == "real rule"
        assert any("dropped" in n.lower() or "ungrounded" in n.lower() for n in result.notes)

    def test_negative_passage_index_dropped(self) -> None:
        passages = [_passage("Rule content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm_response = json.dumps({
            "findings": [
                {
                    "passage_index": -1,
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "fake",
                    "explanation": "x",
                    "severity": "high",
                }
            ]
        })
        agent = QualityAgent(
            llm_client=_FakeLLM(llm_response), retriever_fn=retriever
        )

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings
        assert any("dropped" in n.lower() for n in result.notes)

    def test_non_integer_passage_index_dropped(self) -> None:
        passages = [_passage("Rule content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm_response = json.dumps({
            "findings": [
                {
                    "passage_index": "zero",
                    "file_path": "app.py",
                    "line": 1,
                    "rule_violated": "fake",
                    "explanation": "x",
                    "severity": "high",
                }
            ]
        })
        agent = QualityAgent(
            llm_client=_FakeLLM(llm_response), retriever_fn=retriever
        )

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings


class TestQualityAgentNoContext:
    def test_empty_retrieval_refuses_review(self) -> None:
        retriever = _FakeRetriever(_empty_retrieval("Collection not found"))
        llm = _FakeLLM("should not be called")
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings
        assert llm.calls == 0
        assert any("no relevant" in n.lower() for n in result.notes)
        assert any("cannot perform" in n.lower() for n in result.notes)

    def test_empty_diff_returns_early(self) -> None:
        retriever = _FakeRetriever(_retrieval_with_passages([_passage("x")]))
        llm = _FakeLLM("should not be called")
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run("")

        assert not result.has_findings
        assert llm.calls == 0
        assert retriever.calls == 0
        assert any("empty diff" in n.lower() for n in result.notes)


class TestQualityAgentErrorHandling:
    def test_llm_failure_does_not_crash(self) -> None:
        passages = [_passage("Rule content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm = _FakeLLM(LLMError("groq exploded"))
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings
        assert any("failed" in n.lower() for n in result.notes)

    def test_unparseable_llm_response(self) -> None:
        passages = [_passage("Rule content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm = _FakeLLM("this is not JSON at all!!!")
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings
        assert any("parsed" in n.lower() for n in result.notes)

    def test_code_fenced_response_is_parsed(self) -> None:
        passages = [_passage("Use snake_case.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        fenced = (
            "```json\n"
            + json.dumps({"findings": [
                {"passage_index": 0, "file_path": "a.py", "line": 1,
                 "rule_violated": "naming", "explanation": "x", "severity": "low"}
            ]})
            + "\n```"
        )
        agent = QualityAgent(
            llm_client=_FakeLLM(fenced), retriever_fn=retriever
        )

        result = agent.run(SAMPLE_DIFF)

        assert result.has_findings
        assert len(result.findings) == 1

    def test_no_findings_from_llm_is_valid(self) -> None:
        passages = [_passage("Rule content.")]
        retriever = _FakeRetriever(_retrieval_with_passages(passages))
        llm = _FakeLLM(json.dumps({"findings": []}))
        agent = QualityAgent(llm_client=llm, retriever_fn=retriever)

        result = agent.run(SAMPLE_DIFF)

        assert not result.has_findings
        assert not any("dropped" in n.lower() for n in result.notes)
