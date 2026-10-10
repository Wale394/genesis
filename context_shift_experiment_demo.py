"""Run the four Context Shift Stress Test v0.1 cases."""
from context_shift_experiment import ContextDimension, ContextShiftEvaluator


CASES = [
    ("normal_stable", 45, 45, [("load", 50, 50, True), ("motion", "moving", "moving", True)]),
    ("normal_changed_context", 60, 50, [("load", 50, 90, True), ("motion", "moving", "moving", True)]),
    ("abnormal_stable_context", 60, 50, [("load", 50, 50, True), ("motion", "moving", "moving", True)]),
    ("abnormal_unknown_context", 60, 50, [("load", 50, None, True), ("motion", "moving", "moving", True)]),
]


def run():
    evaluator = ContextShiftEvaluator()
    results = []
    for name, observed, expected, raw_context in CASES:
        context = [ContextDimension(*item) for item in raw_context]
        results.append({"case": name, "assessment": evaluator.assess("motor_temperature", observed, expected, context).to_dict()})
    return results


if __name__ == "__main__":
    for result in run():
        assessment = result["assessment"]
        print(f"{result['case']}: {assessment['interpretation']} | investigation={assessment['investigation_required']}")
        print(f"  {assessment['reason']}")
