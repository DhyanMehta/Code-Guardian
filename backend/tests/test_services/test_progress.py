from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from backend.db.models import Review, ReviewProgress
from backend.services.progress import recorder
from backend.tests.conftest import _TestSessionLocal
from backend.agents.supervisor import build_supervisor_graph, AGENT_NAMES

def test_parallel_progress_is_committed_and_attempt_scoped():
    with _TestSessionLocal() as db:
        review=Review(repo_full_name='test/repo',pr_number=2,attempt=2)
        db.add(review); db.commit(); review_id=review.id
        record=recorder(db.get_bind(),review_id,2)
    def run(agent):
        record('agent','started',agent); record('agent','ok',agent)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, AGENT_NAMES))
    with _TestSessionLocal() as db:
        events=db.query(ReviewProgress).order_by(ReviewProgress.id).all()
        assert len(events)==8 and all(e.attempt==2 for e in events)
        for agent in AGENT_NAMES:
            assert [e.status for e in events if e.agent==agent]==['started','ok']

def test_graph_reports_actual_outcomes():
    events=[]
    def result(name): return lambda state: {'agent_outcomes':{name:'degraded' if name=='security' else 'ok'}}
    with patch('backend.agents.supervisor._run_security_node',result('security')), patch('backend.agents.supervisor._run_quality_node',result('quality')), patch('backend.agents.supervisor._run_test_gap_node',result('test_gap')), patch('backend.agents.supervisor._run_documentation_node',result('documentation')):
        build_supervisor_graph(progress=lambda *e: events.append(e)).invoke({'agent_outcomes':{}})
    assert ('agent','degraded','security') in events
    for agent in AGENT_NAMES:
        assert events.index(('agent','started',agent)) < events.index(('agent','degraded' if agent=='security' else 'ok',agent))


def test_parallel_graph_shares_cap_and_defers_optional_sends(monkeypatch):
    from threading import Lock
    from time import monotonic
    from types import SimpleNamespace

    from backend.agents import supervisor
    from backend.tools.llm_client import LLMClient, LLMRequestBudgetError
    from backend.tools.review_budget import optional_draft_budget

    sent = []
    calls_lock = Lock()

    def send(**kwargs):
        with calls_lock:
            sent.append(kwargs["messages"][-1]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    provider = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=send)))
    client = LLMClient(client=provider)

    def node(name, optional):
        def request():
            try:
                client.complete(system_prompt="test", user_prompt=name)
                return {"agent_outcomes": {name: "ok"}}
            except LLMRequestBudgetError:
                return {"agent_outcomes": {name: "degraded"}}

        def run(_state):
            if not optional:
                return request()
            with optional_draft_budget() as allowed:
                assert allowed
                return request()
        return run

    for name in AGENT_NAMES:
        monkeypatch.setattr(supervisor, f"_run_{name}_node",
                            node(name, name in {"test_gap", "documentation"}))
    graph = build_supervisor_graph(analysis_deadline=monotonic() + 15, provider_request_limit=2)
    result = graph.invoke({"agent_outcomes": {}})
    assert sorted(sent) == ["quality", "security"]
    assert result["agent_outcomes"] == {
        "quality": "ok", "security": "ok", "test_gap": "degraded", "documentation": "degraded",
    }
