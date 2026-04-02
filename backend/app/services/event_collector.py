"""EventCollector: accumulates pipeline events in memory, bulk-inserts via flush().

Events are partitioned into two categories:
- Stage summaries (always captured): start/end of each pipeline stage with record counts
- Detail events (fault_diagnosis only): API calls, transform decisions, exclusion results, etc.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime

# Event types
STAGE_SUMMARY = "stage_summary"
API_CALL = "api_call"
TRANSFORM_DECISION = "transform_decision"
EXCLUSION_RESULT = "exclusion_result"
QUALYS_BATCH = "qualys_batch"
QUALYS_REJECTION = "qualys_rejection"

# Stage names
STAGE_FETCH = "source_fetch"
STAGE_TRANSFORM = "transformation"
STAGE_EXCLUSION = "exclusion"
STAGE_QUALYS = "qualys_submit"


@dataclass
class PendingEvent:
    event_type: str
    stage: str
    message: str
    detail: dict | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventCollector:
    """Accumulates pipeline events in memory and bulk-inserts via flush().

    Stage summaries are always captured. Detail events (API calls, transform
    decisions, etc.) are only captured when fault_diagnosis is True.
    """

    def __init__(self, run_id: str, fault_diagnosis: bool = False) -> None:
        self.run_id = run_id
        self.fault_diagnosis = fault_diagnosis
        self._events: list[PendingEvent] = []
        self._stage_timers: dict[str, float] = {}

    def start_stage(self, stage: str) -> None:
        """Record the start time for a pipeline stage."""
        self._stage_timers[stage] = time.monotonic()

    def end_stage(
        self,
        stage: str,
        records_in: int,
        records_out: int,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        """Record stage completion with duration and record counts."""
        start = self._stage_timers.pop(stage, None)
        duration_ms = int((time.monotonic() - start) * 1000) if start is not None else 0

        self._events.append(
            PendingEvent(
                event_type=STAGE_SUMMARY,
                stage=stage,
                message=f"Stage {stage} completed: {status}",
                detail={
                    "records_in": records_in,
                    "records_out": records_out,
                    "duration_ms": duration_ms,
                    "status": status,
                    "error": error,
                },
            )
        )

    def add_detail(
        self,
        event_type: str,
        stage: str,
        message: str,
        detail: dict | None = None,
    ) -> None:
        """Add a detail event. No-op when fault_diagnosis is disabled."""
        if not self.fault_diagnosis:
            return
        self._events.append(
            PendingEvent(
                event_type=event_type,
                stage=stage,
                message=message,
                detail=detail,
            )
        )

    def flush(self, db) -> int:
        """Bulk-insert all accumulated events into the database.

        Returns the number of events inserted.
        """
        if not self._events:
            return 0

        from app.models.run_event import RunEvent

        objects = [
            RunEvent(
                run_id=self.run_id,
                event_type=ev.event_type,
                stage=ev.stage,
                message=ev.message,
                detail=ev.detail,
                timestamp=ev.timestamp,
            )
            for ev in self._events
        ]
        db.add_all(objects)
        db.commit()
        count = len(objects)
        self._events.clear()
        return count
