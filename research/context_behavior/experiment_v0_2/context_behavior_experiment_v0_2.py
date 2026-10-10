import argparse, csv, glob, json, os, random, statistics
from collections import defaultdict


def load_stream(path):
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            rows.append({
                'time': float(r['time']),
                'position': float(r['position']),
                'temperature': float(r['temperature']),
                'voltage': float(r['voltage']),
                'label': int(r['label']),
            })
    rows.sort(key=lambda x: x['time'])
    return rows


def bucket(x, width):
    return int(x // width)


def sign_bucket(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def run_stream(rows, position_bin, voltage_bin, min_history, threshold, persistence):
    """v0.2 context = v0.1 position/voltage bins + instantaneous motion/trend signs.

    Only prior observations contribute to the expected temperature. Labels are never
    used to construct the baseline. The detection rule is unchanged from v0.1.
    """
    history = defaultdict(list)
    results = []
    consecutive = 0
    prev_position = None
    prev_voltage = None

    for r in rows:
        dp = None if prev_position is None else r['position'] - prev_position
        dv = None if prev_voltage is None else r['voltage'] - prev_voltage
        motion = None if dp is None else sign_bucket(dp)
        voltage_trend = None if dv is None else sign_bucket(dv)

        key = None if motion is None else (
            bucket(r['position'], position_bin),
            bucket(r['voltage'], voltage_bin),
            motion,
            voltage_trend,
        )
        prior = [] if key is None else history[key]
        expected = statistics.median(prior) if len(prior) >= min_history else None
        deviation = None if expected is None else r['temperature'] - expected
        consecutive = consecutive + 1 if deviation is not None and deviation >= threshold else 0
        results.append({
            **r,
            'position_delta': dp,
            'voltage_delta': dv,
            'motion_state': motion,
            'voltage_trend': voltage_trend,
            'expected_temperature': expected,
            'deviation': deviation,
            'persistent': consecutive >= persistence,
        })
        if key is not None:
            history[key].append(r['temperature'])
        prev_position = r['position']
        prev_voltage = r['voltage']
    return results


def summarize(path, results):
    pos = [x for x in results if x['label'] == 1]
    neg = [x for x in results if x['label'] == 0]
    pers = [x for x in results if x['persistent']]
    pp = [x for x in pers if x['label'] == 1]
    pn = [x for x in pers if x['label'] == 0]
    eligible = [x for x in results if x['deviation'] is not None]
    return {
        'stream': os.path.relpath(path),
        'observations': len(results),
        'positive_observations': len(pos),
        'eligible_context_observations': len(eligible),
        'persistent_deviations': len(pers),
        'persistent_positive': len(pp),
        'persistent_negative': len(pn),
        'has_positive_label': bool(pos),
        'has_persistent_deviation': bool(pers),
        'persistent_overlap_positive': bool(pp),
        'persistent_rate_positive': len(pp) / len(pos) if pos else None,
        'persistent_rate_negative': len(pn) / len(neg) if neg else None,
    }


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def discover(data_root):
    patterns = [
        os.path.join(data_root, '*', 'data_motor_*.csv'),
        os.path.join(data_root, 'training_data', '*', 'data_motor_*.csv'),
        os.path.join(data_root, 'training_data', 'training_data', '*', 'data_motor_*.csv'),
    ]
    return sorted(set(p for pat in patterns for p in glob.glob(pat)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', required=True)
    ap.add_argument('--output-dir', default='results')
    ap.add_argument('--position-bin', type=float, default=25)
    ap.add_argument('--voltage-bin', type=float, default=100)
    ap.add_argument('--min-history', type=int, default=5)
    ap.add_argument('--deviation-threshold', type=float, default=5.0)
    ap.add_argument('--persistence', type=int, default=3)
    args = ap.parse_args()

    paths = discover(args.data_root)
    if not paths:
        raise SystemExit('No data_motor_*.csv files found under --data-root')

    summaries = []
    observation_rows = []
    totals = defaultdict(int)

    for p in paths:
        rows = load_stream(p)
        res = run_stream(rows, args.position_bin, args.voltage_bin, args.min_history,
                         args.deviation_threshold, args.persistence)
        s = summarize(p, res)
        summaries.append(s)
        totals['observations'] += len(res)
        totals['positive_observations'] += sum(x['label'] == 1 for x in res)
        totals['eligible_context_observations'] += sum(x['deviation'] is not None for x in res)
        totals['persistent_deviations'] += sum(x['persistent'] for x in res)
        totals['persistent_positive'] += sum(x['persistent'] and x['label'] == 1 for x in res)
        totals['persistent_negative'] += sum(x['persistent'] and x['label'] == 0 for x in res)
        for x in res:
            observation_rows.append({
                'stream': s['stream'], 'time': x['time'], 'position': x['position'],
                'temperature': x['temperature'], 'voltage': x['voltage'], 'label': x['label'],
                'position_delta': x['position_delta'], 'voltage_delta': x['voltage_delta'],
                'motion_state': x['motion_state'], 'voltage_trend': x['voltage_trend'],
                'expected_temperature': x['expected_temperature'], 'deviation': x['deviation'],
                'persistent': int(x['persistent']),
            })

    pos_streams = [s for s in summaries if s['has_positive_label']]
    neg_streams = [s for s in summaries if not s['has_positive_label']]

    # Same randomized-label control as v0.1; labels are shuffled only after the signal is fixed.
    rng = random.Random(20261002)
    control_hits = []
    for p in paths:
        rows = load_stream(p)
        res = run_stream(rows, args.position_bin, args.voltage_bin, args.min_history,
                         args.deviation_threshold, args.persistence)
        labels = [x['label'] for x in res]
        rng.shuffle(labels)
        control_hits.append(sum(x['persistent'] and label == 1 for x, label in zip(res, labels)))

    summary = {
        'experiment': 'Context Behavior Experiment v0.2',
        'question': 'Does adding label-independent operating context (motion direction and voltage trend) to the v0.1 position/voltage context reduce detections in negative-label streams while preserving contextual deviation signal?',
        'streams': len(summaries),
        'positive_streams': len(pos_streams),
        'negative_streams': len(neg_streams),
        **dict(totals),
        'positive_streams_with_persistent_deviation': sum(s['has_persistent_deviation'] for s in pos_streams),
        'negative_streams_with_persistent_deviation': sum(s['has_persistent_deviation'] for s in neg_streams),
        'positive_streams_with_persistent_overlap': sum(s['persistent_overlap_positive'] for s in pos_streams),
        'parameters': {
            'position_bin': args.position_bin,
            'voltage_bin': args.voltage_bin,
            'context_extensions': ['motion_direction_sign', 'voltage_change_sign'],
            'min_history': args.min_history,
            'deviation_threshold': args.deviation_threshold,
            'persistence': args.persistence,
        },
        'randomized_label_control': {
            'seed': 20261002,
            'persistent_positive_observations_after_shuffle': sum(control_hits),
            'streams_with_control_overlap': sum(x > 0 for x in control_hits),
        },
        'interpretation': 'Research evidence only. Labels are used only for evaluation and are never used to construct the baseline or trigger the deviation signal.',
    }

    os.makedirs(args.output_dir, exist_ok=True)
    write_csv(os.path.join(args.output_dir, 'observation_results.csv'), observation_rows,
              ['stream','time','position','temperature','voltage','label','position_delta','voltage_delta','motion_state','voltage_trend','expected_temperature','deviation','persistent'])
    write_csv(os.path.join(args.output_dir, 'stream_summary.csv'), summaries, list(summaries[0].keys()))
    with open(os.path.join(args.output_dir, 'experiment_report.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    report = f'''GENESIS CONTEXT BEHAVIOR EXPERIMENT v0.2

Question
{summary['question']}

Dataset
{summary['streams']} streams; {summary['observations']} observations; {summary['positive_streams']} positive-label streams; {summary['negative_streams']} negative-label streams.

Method
The v0.1 context is retained: position bins ({args.position_bin}) and voltage bins ({args.voltage_bin}). v0.2 adds two label-independent context dimensions: the sign of the immediately preceding position change (negative/stationary/positive) and the sign of the immediately preceding voltage change (negative/stationary/positive). Expected temperature is the median of prior observations in the exact context key. At least {args.min_history} prior observations are required. The detection rule is unchanged: deviation >= {args.deviation_threshold} C for {args.persistence} consecutive observations.

Result
Positive-label streams with persistent deviation: {summary['positive_streams_with_persistent_deviation']}/{summary['positive_streams']}.
Negative-label streams with persistent deviation: {summary['negative_streams_with_persistent_deviation']}/{summary['negative_streams']}.
Persistent observations overlapping positive labels: {summary['persistent_positive']}.
Persistent observations in negative labels: {summary['persistent_negative']}.

Randomized-label control
After shuffling labels within each stream (seed 20261002), persistent observations assigned a positive label: {summary['randomized_label_control']['persistent_positive_observations_after_shuffle']}; streams with any control overlap: {summary['randomized_label_control']['streams_with_control_overlap']}.

Interpretation
This experiment is research evidence only. It tests whether a modest, label-independent context expansion reduces detections in negative-label streams while retaining signal in positive-label streams. It does not establish failure causation or a deployable failure detector.
'''
    with open(os.path.join(args.output_dir, 'experiment_report.txt'), 'w') as f:
        f.write(report)
    print(report)

if __name__ == '__main__':
    main()
