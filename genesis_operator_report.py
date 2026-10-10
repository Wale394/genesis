"""Operator-facing reporting for the Genesis multi-domain demo.

This module is presentation-only. It consumes the structured demo result and
never changes evidence, reliability state, investigation, or finding semantics.
"""

from typing import Any, Dict, Iterable, List


def _lines(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _evidence_lines(evidence: Iterable[Dict[str, Any]], prefix: str = "-") -> List[str]:
    output: List[str] = []
    for item in evidence or []:
        category = item.get("category", "UNKNOWN")
        name = item.get("name", "unnamed")
        value = item.get("value", "unknown")
        source = item.get("source", "unknown")
        output.append(f"{prefix} [{category}] {name}: {value} (source: {source})")
    return output


def _finding_text(finding: Dict[str, Any]) -> str:
    status = finding.get("status", "UNKNOWN")
    statement = finding.get("statement", "No finding statement provided.")
    return f"{status} — {statement}"


def build_operator_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a structured operator report without mutating the demo result."""
    assets: List[Dict[str, Any]] = []
    for item in result.get("asset_results", []):
        initial = item.get("initial", {})
        reassessment = item.get("reassessment", {})
        compatibility = item.get("context_compatibility")
        historical = item.get("historical_memory")

        initial_state = initial.get("state", {})
        final_state = reassessment.get("state", {})
        review = reassessment.get("evidence_review", {})
        new_evidence = reassessment.get("new_evidence", [])
        finding = reassessment.get("finding", {})

        assets.append({
            "asset_id": item.get("asset_id"),
            "domain": item.get("domain"),
            "asset_type": item.get("asset_type"),
            "current_state": final_state.get("level", "UNKNOWN"),
            "state_reason": final_state.get("reason"),
            "previous_state": final_state.get("previous_level", initial_state.get("level")),
            "state_changed": final_state.get("changed"),
            "observations": {
                "initial_evidence": initial.get("evidence_review", {}).get("evidence", []),
            },
            "supporting_evidence": [e for e in new_evidence if e.get("metadata", {}).get("stance") == "SUPPORTS"],
            "conflicting_evidence": [e for e in new_evidence if e.get("metadata", {}).get("stance") == "CONTRADICTS"],
            "evidence_review": {
                "escalation_allowed": review.get("escalation_allowed"),
                "conflicts": review.get("conflicts", []),
                "limitations": review.get("limitations", []),
            },
            "historical_context": {
                "available": historical is not None,
                "retrieval": historical,
                "compatibility": compatibility,
            },
            "investigation": initial.get("investigation", {}),
            "finding": finding,
            "assessment_mode": "GENESIS_ONLY",
        })

    return {
        "title": "GENESIS RELIABILITY REPORT",
        "demo": result.get("demo"),
        "fleet": result.get("fleet", {}),
        "supported_domains": result.get("supported_domains", []),
        "assets": assets,
        "claims": list(result.get("claims", [])),
        "limitations": list(result.get("limitations", [])),
    }


def render_operator_report(report: Dict[str, Any]) -> str:
    """Render the structured operator report as a deterministic plain-text view."""
    lines = [
        "=" * 76,
        report.get("title", "GENESIS RELIABILITY REPORT"),
        "=" * 76,
        f"Demo: {report.get('demo', 'unknown')}",
        f"Fleet: {report.get('fleet', {}).get('asset_count', 0)} assets | "
        f"{report.get('fleet', {}).get('domain_count', 0)} domains",
        f"Assessment mode: GENESIS-ONLY",
        "",
    ]

    for asset in report.get("assets", []):
        lines.extend([
            "-" * 76,
            f"ASSET: {asset['asset_id']} | {asset['domain']} | {asset['asset_type']}",
            "-" * 76,
            "CURRENT STATE",
            f"  {asset['current_state']} — {asset.get('state_reason') or 'No reason provided.'}",
            f"  Previous state: {asset.get('previous_state')}",
            f"  State changed: {asset.get('state_changed')}",
            "",
            "WHAT GENESIS OBSERVED",
        ])
        lines.extend(_evidence_lines(asset["observations"].get("initial_evidence", []), "  "))

        lines.append("")
        lines.append("SUPPORTING EVIDENCE")
        supporting = asset.get("supporting_evidence", [])
        lines.extend(_evidence_lines(supporting, "  ") or ["  None recorded."])

        lines.append("")
        lines.append("CONFLICTING EVIDENCE")
        conflicting = asset.get("conflicting_evidence", [])
        lines.extend(_evidence_lines(conflicting, "  ") or ["  None recorded."])
        if asset["evidence_review"].get("conflicts"):
            lines.append("  Review conflicts:")
            lines.extend(f"    - {conflict}" for conflict in asset["evidence_review"]["conflicts"])

        lines.append("")
        lines.append("HISTORICAL CONTEXT")
        compatibility = asset["historical_context"].get("compatibility")
        if compatibility:
            lines.append(f"  Compatibility: {compatibility.get('status', 'UNKNOWN')}")
            lines.append(f"  Investigation required: {compatibility.get('investigation_required')}")
            lines.append(f"  Reason: {compatibility.get('reason') or 'None provided.'}")
            limitations = compatibility.get("limitations", [])
            if limitations:
                lines.append("  Limitations:")
                lines.extend(f"    - {limitation}" for limitation in limitations)
        elif asset["historical_context"].get("available"):
            lines.append("  Historical memory was available; no explicit compatibility assessment was recorded.")
        else:
            lines.append("  No historical context recorded.")

        lines.append("")
        lines.append("INVESTIGATION")
        investigation = asset.get("investigation", {})
        lines.append(f"  Required: {investigation.get('required')}")
        lines.append(f"  Reasons: {', '.join(investigation.get('reasons', [])) or 'None recorded.'}")
        lines.append(f"  Actions: {', '.join(investigation.get('actions', [])) or 'None recorded.'}")

        lines.append("")
        lines.append("REASSESSMENT")
        lines.append(f"  Previous state: {asset.get('previous_state')}")
        lines.append(f"  New evidence count: {len(asset.get('supporting_evidence', [])) + len(asset.get('conflicting_evidence', []))}")
        lines.append(f"  Current state: {asset.get('current_state')}")

        lines.append("")
        lines.append("FINDING")
        lines.append(f"  {_finding_text(asset.get('finding', {}))}")

        lines.append("")
        lines.append("ASSESSMENT SCOPE")
        lines.append("  Genesis-only assessment. No human evidence is included in this demo result.")
        lines.append("")

    lines.extend([
        "=" * 76,
        "SYSTEM CLAIMS",
        "=" * 76,
    ])
    lines.extend(f"- {claim}" for claim in report.get("claims", []))
    lines.append("")
    lines.append("LIMITATIONS")
    lines.extend(f"- {limitation}" for limitation in report.get("limitations", []))
    return "\n".join(lines)
