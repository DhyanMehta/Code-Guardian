"""Store validated agent outputs independently of report finalization."""
import hashlib
import json
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from backend.agents.state import ScannerStatus, TriagedFinding
from backend.db.models import ReviewAgentCheckpoint
from backend.tools.results import RawFinding, Severity


quality_checkpoints: ContextVar["AgentCheckpoints | None"] = ContextVar("quality_checkpoints", default=None)


def validation_fingerprint():
    root = Path(__file__).resolve().parents[1]
    paths = [root / "agents" / name for name in
             ("quality_agent.py", "_validation.py", "frontend_analysis.py", "test_gap_agent.py", "documentation_agent.py")]
    paths += [root / "tools/frontend_ast.cjs", root / "tools/parser/package-lock.json"]
    paths += sorted((root / "tools/semgrep_rules").glob("*.yml"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class AgentCheckpoints:
    def __init__(self, bind, review_id: int, fingerprint: str):
        self.bind = bind
        self.review_id = review_id
        self.fingerprint = fingerprint

    def quality_batch(self, batch: str) -> "AgentCheckpoints":
        identity = hashlib.sha256(f"quality-batch-v1:{self.fingerprint}:{batch}".encode()).hexdigest()
        return AgentCheckpoints(self.bind, self.review_id, identity)

    def load(self, agent: str) -> dict | None:
        with Session(self.bind) as db:
            row = db.get(ReviewAgentCheckpoint, (self.review_id, self.fingerprint, agent))
            if row is None:
                return None
            result = json.loads(row.payload)
        for raw in result.get("raw_findings", {}).get(agent, []):
            raw["severity"] = Severity(raw["severity"])
        for triaged in result.get("triaged_findings", {}).get(agent, []):
            for key in ("original_severity", "triaged_severity"):
                triaged[key] = Severity(triaged[key])
        for key, cls in (("raw_findings", RawFinding), ("triaged_findings", TriagedFinding),
                         ("scanner_statuses", ScannerStatus)):
            if key in result:
                result[key][agent] = [cls(**item) for item in result[key][agent]]
        return result

    def save(self, agent: str, result: dict) -> None:
        def encode(value):
            if is_dataclass(value):
                return asdict(value)
            raise TypeError(f"Unsupported checkpoint value: {type(value).__name__}")

        with Session(self.bind) as db:
            values = dict(review_id=self.review_id, fingerprint=self.fingerprint,
                          agent=agent, payload=json.dumps(result, default=encode))
            if db.get_bind().dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
                statement = insert(ReviewAgentCheckpoint).values(**values)
                db.execute(statement.on_conflict_do_nothing(
                    index_elements=["review_id", "fingerprint", "agent"]))
            else:
                db.merge(ReviewAgentCheckpoint(**values))
            db.commit()
