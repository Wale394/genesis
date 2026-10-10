import argparse, csv, glob, json, os, random, statistics
from collections import defaultdict

DEFAULT_PATTERN = os.path.join('training_data', 'training_data', '*', 'data_motor_*.csv')


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


def run_stream(rows, position_bin, voltage_bin, min_history, threshold, persistence):
    history = defaultdict(list)
    results = []
    consecutive = 0
    for r in rows:
        key = (bucket(r['position'], position_bin), bucket(r['voltage'], voltage_bin))
        prior = history[key]
        expected = statistics.median(prior) if len(prior) >= min_history else None
        deviation = None if expected is None else r['temperature'] - expected
        consecutive = consecutive + 1 if deviation is not None and deviation >= threshold else 0
        results.append({**r, 'expected_temperature': expected, 'deviation': deviation,
                        'persistent': consecutive >= persistence})
        history[key].append(r['temperature'])
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
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', required=True, help='Root containing training_data/training_data/*/data_motor_*.csv, or the directory containing run folders')
    ap.add_argument('--output-dir', default=os.path.join('results'))
    ap.add_argument('--position-bin', type=float, default=25)
    ap.add_argument('--voltage-bin', type=float, default=100)
    ap.add_argument('--min-history', type=int, default=5)
    ap.add_argument('--deviation-threshold', type=float, default=5.0)
    ap.add_argument('--persistence', type=int, default=3)
    args = ap.parse_args()

    patterns = [
        os.path.join(args.data_root, '*', 'data_motor_*.csv'),
        os.path.join(args.data_root, 'training_data', '*', 'data_motor_*.csv'),
        os.path.join(args.data_root, 'training_data', 'training_data', '*', 'data_motor_*.csv'),
    ]
    paths = sorted(set(p for pat in patterns for p in glob.glob(pat)))
    if not paths:
        raise SystemExit('No data_motor_*.csv files found under --data-root')

    summaries = []
    observation_rows = []
    total_obs = total_pos = total_eligible = total_persistent = total_persistent_pos = total_persistent_neg = 0

    for p in paths:
        rows = load_stream(p)
        res = run_stream(rows, args.position_bin, args.voltage_bin, args.min_history,
                         args.deviation_threshold, args.persistence)
        s = summarize(p, res); summaries.append(s)
        for x in res:
            observation_rows.append({
                'stream': s['stream'], 'time': x['time'], 'position': x['position'],
                'temperature': x['temperature'], 'voltage': x['voltage'], 'label': x['label'],
                'expected_temperature': x['expected_temperature'], 'deviation': x['deviation'],
                'persistent': int(x['persistent']),
            })
        total_obs += len(res); total_pos += sum(x['label'] == 1 for x in res)
        total_eligible += sum(x['deviation'] is not None for x in res)
        total_persistent += sum(x['persistent'] for x in res)
        total_persistent_pos += sum(x['persistent'] and x['label'] == 1 for x in res)
        total_persistent_neg += sum(x['persistent'] and x['label'] == 0 for x in res)

    pos_streams = [s for s in summaries if s['has_positive_label']]
    neg_streams = [s for s in summaries if not s['has_positive_label']]

    rng = random.Random(20261002)
    control_hits = []
    for p in paths:
        rows = load_stream(p)
        res = run_stream(rows, args.position_bin, args.voltage_bin, args.min_history,
                         args.deviation_threshold, args.persistence)
        labels = [x['label'] for x in res]; rng.shuffle(labels)
        control_hits.append(sum(x['persistent'] and label == 1 for x, label in zip(res, labels)))

    summary = {
        'experiment': 'Context Behavior Experiment v0.1',
        'question': 'Does a past-only context-conditioned temperature baseline reveal persistent behavioral deviation, while remaining distinguishable from label-randomization noise?',
        'streams': len(summaries),
        'positive_streams': len(pos_streams),
        'negative_streams': len(neg_streams),
        'observations': total_obs,
        'positive_observations': total_pos,
        'eligible_context_observations': total_eligible,
        'persistent_deviations': total_persistent,
        'persistent_positive': total_persistent_pos,
        'persistent_negative': total_persistent_neg,
        'positive_streams_with_persistent_deviation': sum(s['has_persistent_deviation'] for s in pos_streams),
        'negative_streams_with_persistent_deviation': sum(s['has_persistent_deviation'] for s in neg_streams),
        'positive_streams_with_persistent_overlap': sum(s['persistent_overlap_positive'] for s in pos_streams),
        'parameters': {
            'position_bin': args.position_bin, 'voltage_bin': args.voltage_bin,
            'min_history': args.min_history, 'deviation_threshold': args.deviation_threshold,
            'persistence': args.persistence,
        },
        'randomized_label_control': {
            'seed': 20261002,
            'persistent_positive_observations_after_shuffle': sum(control_hits),
            'streams_with_control_overlap': sum(x > 0 for x in control_hits),
        },
        'interpretation': 'Research evidence only. A positive/negative label is used only for evaluation; labels are never used to build the baseline or trigger the deviation signal.',
    }

    os.makedirs(args.output_dir, exist_ok=True)
    write_csv(os.path.join(args.output_dir, 'observation_results.csv'), observation_rows,
              ['stream','time','position','temperature','voltage','label','expected_temperature','deviation','persistent'])
    write_csv(os.path.join(args.output_dir, 'stream_summary.csv'), summaries, list(summaries[0].keys()))
    with open(os.path.join(args.output_dir, 'experiment_report.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    report = f'''GENESIS CONTEXT BEHAVIOR EXPERIMENT v0.1\n\nQuestion\n{summary['question']}\n\nDataset\n{summary['streams']} streams; {summary['observations']} observations; {summary['positive_streams']} positive-label streams; {summary['negative_streams']} negative-label streams.\n\nMethod\nPast-only median temperature baseline conditioned on position bins ({args.position_bin}) and voltage bins ({args.voltage_bin}). At least {args.min_history} prior observations are required. A deviation >= {args.deviation_threshold} C for {args.persistence} consecutive observations is called a persistent deviation. Labels are excluded from baseline construction.\n\nResult\nPositive-label streams with persistent deviation: {summary['positive_streams_with_persistent_deviation']}/{summary['positive_streams']}.\nNegative-label streams with persistent deviation: {summary['negative_streams_with_persistent_deviation']}/{summary['negative_streams']}.\nPersistent observations overlapping positive labels: {summary['persistent_positive']}.\nPersistent observations in negative labels: {summary['persistent_negative']}.\n\nRandomized-label control\nAfter shuffling labels within each stream (seed 20261002), persistent observations assigned a positive label: {summary['randomized_label_control']['persistent_positive_observations_after_shuffle']}; streams with any control overlap: {summary['randomized_label_control']['streams_with_control_overlap']}.\n\nInterpretation\nThe contextual-deviation signal is present in part of the positive-label population, but it also appears in negative-label streams. Therefore this experiment does not establish a failure detector. The randomized-label control also shows that label overlap alone is not sufficient evidence. The next step, if pursued, is to test whether a better context representation reduces negative-stream detections without using labels.\n'''
    with open(os.path.join(args.output_dir, 'experiment_report.txt'), 'w') as f: f.write(report)
    print(report)

if __name__ == '__main__': main()
