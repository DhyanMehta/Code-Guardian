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
