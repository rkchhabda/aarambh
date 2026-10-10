"""Production-readiness scorecard and audit report generator for Milestone 4.11.

Generates a non-investment engineering scorecard evaluating 15 governed domains:
1. Test integrity
2. Persistence durability
3. Manifest integrity
4. Checkpoint integrity
5. Recovery behavior
6. Resume authorization
7. Concurrency protection
8. Security boundaries
9. Logging and redaction
10. Backup and restoration
11. Synthetic scale
12. Operational drills
13. Phase 6 protection
14. Production isolation
15. External-acquisition quarantine

Each domain is scored as PASS, PARTIAL, FAIL, or NOT_TESTED.
Final classification when all pass:
INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REQUIRED_CLASSIFICATION = "INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED"

DOMAINS = [
    "test_integrity",
    "persistence_durability",
    "manifest_integrity",
    "checkpoint_integrity",
    "recovery_behavior",
    "resume_authorization",
    "concurrency_protection",
    "security_boundaries",
    "logging_and_redaction",
    "backup_and_restoration",
    "synthetic_scale",
    "operational_drills",
    "phase6_protection",
    "production_isolation",
    "external_acquisition_quarantine",
]


@dataclass
class DomainScore:
    domain_id: str
    display_name: str
    status: str  # PASS, PARTIAL, FAIL, NOT_TESTED
    evidence: str
    details: Dict[str, Any]


class ReadinessScorecard:
    """Evaluates readiness criteria and produces structured Markdown and JSON reports."""

    def __init__(self) -> None:
        self.domain_scores: Dict[str, DomainScore] = {}

    def set_domain_score(
        self,
        domain_id: str,
        display_name: str,
        status: str,
        evidence: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if domain_id not in DOMAINS:
            raise ValueError(f"Unknown domain '{domain_id}'. Must be one of: {DOMAINS}")
        if status not in ("PASS", "PARTIAL", "FAIL", "NOT_TESTED"):
            raise ValueError(f"Invalid status '{status}'. Must be PASS, PARTIAL, FAIL, or NOT_TESTED.")

        self.domain_scores[domain_id] = DomainScore(
            domain_id=domain_id,
            display_name=display_name,
            status=status,
            evidence=evidence,
            details=details or {},
        )

    def evaluate_overall_status(self) -> Tuple[str, bool]:
        if len(self.domain_scores) < len(DOMAINS):
            return "NOT_FULLY_EVALUATED", False

        for d_id in DOMAINS:
            score = self.domain_scores.get(d_id)
            if not score or score.status != "PASS":
                return "FAIL_GATES_OPEN", False

        return REQUIRED_CLASSIFICATION, True

    def generate_json_report(self) -> Dict[str, Any]:
        classification, all_passed = self.evaluate_overall_status()
        return {
            "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "classification": classification,
            "all_gates_passed": all_passed,
            "total_domains": len(DOMAINS),
            "passed_domains": sum(1 for s in self.domain_scores.values() if s.status == "PASS"),
            "domains": {
                d_id: {
                    "display_name": s.display_name,
                    "status": s.status,
                    "evidence": s.evidence,
                    "details": s.details,
                }
                for d_id, s in self.domain_scores.items()
            },
        }

    def generate_markdown_report(self) -> str:
        classification, all_passed = self.evaluate_overall_status()
        now_utc = datetime.now(timezone.utc).isoformat()

        lines = [
            "# Phase 7 Internal Production-Like Readiness Scorecard",
            "",
            f"**Evaluation Date (UTC):** {now_utc}  ",
            f"**Overall Classification:** `{classification}`  ",
            f"**All Gates Passed:** `{all_passed}`  ",
            "",
            "## Domain Evaluation Summary",
            "",
            "| # | Domain | Status | Evidence / Verification |",
            "|---|--------|:------:|-------------------------|",
        ]

        for idx, d_id in enumerate(DOMAINS, start=1):
            s = self.domain_scores.get(d_id)
            if s:
                lines.append(f"| {idx:02d} | {s.display_name} | **{s.status}** | {s.evidence} |")
            else:
                lines.append(f"| {idx:02d} | {d_id} | *NOT_TESTED* | Not evaluated |")

        lines.extend([
            "",
            "## Governance & Posture Affirmation",
            "- Posture: `INTERNAL_NON_DISTRIBUTED_DEVELOPMENT_ONLY`",
            "- External Acquisition: `EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER`",
            "- Network: `ZERO_NETWORK_CALLS` (All sockets blocked)",
            "- Models & Targets: `STRICTLY_PROHIBITED`",
            "- Milestone 5: `BLOCKED`",
            "",
            "*(This report confirms engineering readiness for internal pipeline resilience and does not constitute commercial deployment).*  ",
        ])

        return "\n".join(lines)
