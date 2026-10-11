"""Run the synthetic recorded-telemetry example and write a readable report.

This is an offline demo runner. It does not connect to ROS 2 or a robot.
"""

import argparse
import json
from pathlib import Path

from genesis_field_agent import GenesisFieldAgent
from genesis_field_agent_config import GenesisFieldAgentConfig
from investigation_report import build_field_session_report, render_investigation_report

PACKAGE = Path(__file__).resolve().parent
DEMO_NOTICE = (
    "DEMO NOTICE: The included input is synthetic demonstration data, not telemetry from a real robot.\n"
    "Any state or recommendation reflects prototype rules, not robot-specific calibration, a confirmed fault, or a safety assessment.\n"
)


def load_messages(path):
    source = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(source, dict):
        source = source.get("messages", source)
        if isinstance(source, dict):
            source = [source]
    if not isinstance(source, list):
        raise ValueError("input must be a diagnostic message object or a list of messages")
    return source


def main():
    parser = argparse.ArgumentParser(
        description="Run KORDEX/Genesis against the included synthetic recorded-telemetry example (offline)."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PACKAGE / "demo-output",
        help="directory for the session JSON and readable report (default: demo-output)",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session_path = output_dir / "field-session.json"
    report_path = output_dir / "investigation-report.txt"

    config_data = json.loads((PACKAGE / "config.example.json").read_text(encoding="utf-8"))
    config_data["output_path"] = str(session_path)
    config = GenesisFieldAgentConfig.from_dict(config_data)
    agent = GenesisFieldAgent(config)
    for message in load_messages(PACKAGE / "examples" / "recorded_diagnostics_example.json"):
        agent.ingest_diagnostics(message)
    agent.save_session()

    report = build_field_session_report(agent.get_session())
    rendered = DEMO_NOTICE + "\n" + render_investigation_report(report) + "\n"
    report_path.write_text(rendered, encoding="utf-8")

    print(DEMO_NOTICE)
    print(f"Saved structured session: {session_path}")
    print(f"Saved readable report:    {report_path}")
    print("\n" + rendered)


if __name__ == "__main__":
    main()
