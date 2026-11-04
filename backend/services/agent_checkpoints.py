"""Store validated agent outputs independently of report finalization."""
import json
from dataclasses import asdict, is_dataclass

from sqlalchemy.orm import Session

from backend.agents.state import ScannerStatus, TriagedFinding
from backend.db.models import ReviewAgentCheckpoint
from backend.tools.results import RawFinding, Severity


class AgentCheckpoints:
    def __init__(self, bind, review_id: int, fingerprint: str):
        self.bind = bind
        self.review_id = review_id
        self.fingerprint = fingerprint

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
            db.merge(ReviewAgentCheckpoint(review_id=self.review_id,
                fingerprint=self.fingerprint, agent=agent,
                payload=json.dumps(result, default=encode)))
            db.commit()
