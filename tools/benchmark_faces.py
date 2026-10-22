#!/usr/bin/env python3
"""Offline, labelled, non-clinical face-recognition benchmark.

No downloads, scraping, image exports, per-person scores or embeddings saved.
Requires locally authorized research images and an explicit CSV manifest.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics
import time

from evaluate_policy import evaluate
from opencv_worker import load_models, extract_loaded
from model_identity import verified_paths

ROLES = {'enroll', 'dev_known', 'dev_unknown', 'holdout_known', 'holdout_unknown'}
FIELDS = ('path', 'identity', 'role', 'pose')
BLUR_SIGMAS = (0.0, 1.5, 3.0)


def load_manifest(file):
    source = Path(file).expanduser().resolve()
    root = source.parent
    records = []
    seen_paths = set()
    with source.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS):
            raise ValueError('manifest columns must be path,identity,role,pose')
        for row in reader:
            role = row['role'].strip()
            identity = row['identity'].strip()
            path = (root / row['path']).resolve()
            if role not in ROLES or not identity or len(identity) > 128 or not path.is_file():
                raise ValueError('invalid role, identity, or missing local image')
            if path in seen_paths:
                raise ValueError('an image cannot occur in multiple splits')
            if not path.suffix.lower() in ('.jpg', '.jpeg'):
                raise ValueError('benchmark requires JPEG images')
            seen_paths.add(path)
            records.append({'path': path, 'identity': identity, 'role': role,
                            'pose': row['pose'].strip() or 'unspecified'})
    if not records:
        raise ValueError('manifest is empty')
    enrolled = {r['identity'] for r in records if r['role'] == 'enroll'}
    for row in records:
        if row['role'].endswith('_known') and row['identity'] not in enrolled:
            raise ValueError('known query lacks enrollment')
        if row['role'].endswith('_unknown') and row['identity'] in enrolled:
            raise ValueError('unknown identity is present in gallery')
    for stage in ('dev', 'holdout'):
        if not any(r['role'] == stage + '_known' for r in records) or not any(r['role'] == stage + '_unknown' for r in records):
            raise ValueError('both known and unknown samples are required in each evaluation split')
    # Avoid tuning on identities used as holdout unknowns.
    dev_unknown = {r['identity'] for r in records if r['role'] == 'dev_unknown'}
    holdout_unknown = {r['identity'] for r in records if r['role'] == 'holdout_unknown'}
    if dev_unknown & holdout_unknown:
        raise ValueError('unknown identities must be disjoint across dev and holdout')
    return records


def cosine(a, b):
    if a is None or b is None or len(a) != len(b) or not a:
        return -2.0
    if not all(math.isfinite(float(v)) for v in a + b):
        return -2.0
    dot = sum(float(x)*float(y) for x,y in zip(a,b))
    norm_a = math.sqrt(sum(float(x)**2 for x in a))
    norm_b = math.sqrt(sum(float(x)**2 for x in b))
    return dot / (norm_a * norm_b) if min(norm_a,norm_b) > 1e-9 else -2.0


def average(vectors):
    if not vectors:
        return None
    width = len(vectors[0])
    if not width or any(len(vec) != width for vec in vectors):
        return None
    sums = [sum(float(v[i]) for v in vectors) for i in range(width)]
    norm = math.sqrt(sum(v*v for v in sums))
    return [v / norm for v in sums] if norm > 1e-9 else None


def make_extractor(runtime):
    cv2, np, _, _ = runtime
    def extract(path, sigma):
        raw = path.read_bytes()
        if len(raw) < 4 or len(raw) > 4*1024*1024:
            return None
        if sigma > 0:
            image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return None
            altered = cv2.GaussianBlur(image, (0,0), sigmaX=sigma)
            ok, buf = cv2.imencode('.jpg', altered, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                return None
            raw = buf.tobytes()
        result = extract_loaded([raw], runtime)
        return None if result is None else [float(x) for x in result]
    return extract


def measure(records, extractor, *, sigmas=BLUR_SIGMAS):
    enrolled = {}
    timings = []
    failed_enroll = 0
    for row in records:
        if row['role'] != 'enroll':
            continue
        start = time.perf_counter()
        emb = extractor(row['path'], 0.0)
        timings.append((time.perf_counter() - start)*1000)
        if emb is None:
            failed_enroll += 1
            continue
        enrolled.setdefault(row['identity'], []).append(emb)
    gallery = {key: average(value) for key,value in enrolled.items()}
    if not gallery or any(value is None for value in gallery.values()):
        raise ValueError('no valid enrollment embeddings')
    results = []
    for sigma in sigmas:
        for row in records:
            if row['role'] == 'enroll':
                continue
            start = time.perf_counter()
            emb = extractor(row['path'], sigma)
            elapsed = (time.perf_counter()-start)*1000
            timings.append(elapsed)
            scored = sorted(((cosine(emb, value), key) for key,value in gallery.items()), reverse=True)
            best, identity = scored[0]
            second = scored[1][0] if len(scored) > 1 else -2.0
            if emb is None or best < -1.5:
                identity, best, second = '', -2.0, -2.0
            results.append({
                'split': row['role'].split('_',1)[0], 'sigma': sigma,
                'pose': row['pose'], 'detected': emb is not None,
                'row': {'truth_id': row['identity'] if row['role'].endswith('_known') else '',
                        'best_id': identity, 'best_similarity': str(best),
                        'second_similarity': str(second)}
            })
    return results, {'enrolled_identities': len(gallery), 'enrollment_failures': failed_enroll,
                     'p50_ms': round(statistics.median(timings),2),
                     'p95_ms': round(sorted(timings)[int(.95*(len(timings)-1))],2)}


def choose_policy(development):
    options = []
    for t in range(60, 101):
        threshold = t / 100.0
        for m in range(0, 51):
            margin = m / 100.0
            counts = evaluate(development, threshold, margin)
            if counts['wrong_accepts'] == 0 and counts['correct_accepts'] > 0:
                options.append((counts['correct_accepts'], threshold, margin))
    if not options:
        return None
    # Conservative tie-break, never optimize against holdout.
    _, threshold, margin = max(options)
    return {'threshold': threshold, 'margin': margin}


def summarize(results, timings):
    dev = [item['row'] for item in results if item['split'] == 'dev']
    policy = choose_policy(dev)
    report = {'status': 'EXPERIMENTAL_NOT_APPROVED', 'model': 'yunet-sface',
              'measurement': 'warm-preloaded-model CPU embedding + JPEG handling',
              'gallery': timings, 'development_rows': len(dev),
              'holdout_rows': sum(item['split'] == 'holdout' for item in results),
              'policy': policy, 'holdout': {}, 'holdout_by_pose': {},
              'usable_embeddings_by_blur': {}}
    if policy:
        for sigma in sorted({item['sigma'] for item in results}):
            hold = [item['row'] for item in results if item['split']=='holdout' and item['sigma']==sigma]
            report['holdout'][str(sigma)] = evaluate(hold, policy['threshold'], policy['margin'])
            hold_items = [item for item in results if item['split']=='holdout' and item['sigma']==sigma]
            report['usable_embeddings_by_blur'][str(sigma)] = {
                'attempts': len(hold_items),
                'usable': sum(item['detected'] for item in hold_items),
            }
        for pose in sorted({item['pose'] for item in results if item['split'] == 'holdout'}):
            hold = [item['row'] for item in results if item['split']=='holdout' and item['pose']==pose]
            report['holdout_by_pose'][pose] = evaluate(hold, policy['threshold'], policy['margin'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out', required=True, help='private new JSON report, never overwrite')
    args = parser.parse_args(argv)
    try:
        records = load_manifest(args.manifest)
        paths = verified_paths()
        if paths is None:
            raise ValueError('unpinned or unapproved models')
        runtime = load_models(*paths)
        results, timing = measure(records, make_extractor(runtime))
        report = summarize(results, timing)
        with os.fdopen(os.open(args.out, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600), 'w') as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write('\n')
    except (OSError, ValueError) as error:
        parser.exit(2, f'Benchmark unavailable: {type(error).__name__}\n')
    return 0 if report['policy'] else 2


if __name__ == '__main__':
    raise SystemExit(main())