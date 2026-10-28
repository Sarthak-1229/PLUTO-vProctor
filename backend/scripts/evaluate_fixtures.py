#!/usr/bin/env python3
"""Evaluation harness for benchmark fixtures.

Runs the real audio and video analysis pipelines against ground-truth labeled fixtures.
Reports:
  - Filler recall, precision, F1
  - Pause detection recall, precision
  - Look-away recall across duration buckets (<1s, 1-2s, >=2s)
  - False alarm rate (per minute)
  - Timestamp error (median, p95)
  - ASR Word Error Rate (WER) against reference transcripts

Usage:
    python backend/scripts/evaluate_fixtures.py [--fixtures-dir <path>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.edit_distance import levenshtein
from backend.app.pipelines.audio_pipeline import audio_pipeline
from backend.app.pipelines.video_pipeline import video_pipeline


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER) using Levenshtein distance on tokenized word sequences."""
    ref_words = [w.lower().strip(".,?!;:'\"") for w in reference.split() if w.strip()]
    hyp_words = [w.lower().strip(".,?!;:'\"") for w in hypothesis.split() if w.strip()]
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    n = len(ref_words)
    m = len(hyp_words)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    dist = dp[n][m]
    return min(2.0, dist / float(n))


def match_events(
    ground_truth: List[Dict[str, Any]],
    detected: List[Dict[str, Any]],
    max_tolerance_sec: float = 1.0,
) -> Tuple[int, int, int, List[float]]:
    """Match detected events against ground truth intervals. Returns (TP, FP, FN, time_errors)."""
    matched_gt = set()
    matched_det = set()
    time_errors = []

    for d_idx, d in enumerate(detected):
        d_start = d.get("t_start") if d.get("t_start") is not None else d.get("start", 0.0)
        best_gt_idx = None
        best_diff = float("inf")

        for g_idx, g in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue
            g_start = g.get("start", 0.0)
            g_end = g.get("end", g_start + 0.5)

            # Check overlap or proximity
            if (g_start - max_tolerance_sec) <= d_start <= (g_end + max_tolerance_sec):
                diff = abs(d_start - g_start)
                if diff < best_diff:
                    best_diff = diff
                    best_gt_idx = g_idx

        if best_gt_idx is not None:
            matched_gt.add(best_gt_idx)
            matched_det.add(d_idx)
            time_errors.append(round(best_diff, 3))

    tp = len(matched_gt)
    fp = len(detected) - len(matched_det)
    fn = len(ground_truth) - len(matched_gt)
    return tp, fp, fn, time_errors


def evaluate_single_fixture(
    webm_path: Path,
    labels_path: Path,
) -> Dict[str, Any]:
    """Run pipelines and score performance against one fixture."""
    with open(labels_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    labels = gt_data.get("labels", [])
    ref_transcript = gt_data.get("reference_transcript", "")
    duration_sec = gt_data.get("duration_sec", 60.0)

    gt_fillers = [l for l in labels if l.get("type") in ("FILLER", "FILLER_WORD", "FILLER_PHRASE")]
    gt_pauses = [l for l in labels if l.get("type") in ("PAUSE", "LONG_PAUSE", "HESITATION")]
    gt_lookaway = [l for l in labels if l.get("type") in ("LOOK_AWAY", "LOOK_SIDE", "LOOK_DOWN", "LOOK_UP")]

    # Run real pipelines
    video_res = video_pipeline.analyze_video(webm_path)
    audio_res = audio_pipeline.analyze_audio(webm_path)

    det_events = video_res.get("events", []) + audio_res.get("events", [])
    det_fillers = [
        e for e in det_events
        if e.get("type") in ("FILLER_WORD", "FILLER_PHRASE") or e.get("type", "").startswith("FILLER")
    ]
    det_pauses = [
        e for e in det_events
        if e.get("type") in ("LONG_PAUSE", "HESITATION") or e.get("type", "").startswith("PAUSE")
    ]
    det_lookaway = [
        e for e in det_events
        if e.get("type") in ("LOOK_AWAY", "LOOK_SIDE", "LOOK_DOWN", "LOOK_UP")
    ]

    # Match Fillers
    f_tp, f_fp, f_fn, f_errs = match_events(gt_fillers, det_fillers, max_tolerance_sec=1.2)
    f_prec = f_tp / (f_tp + f_fp) if (f_tp + f_fp) > 0 else 1.0 if not gt_fillers else 0.0
    f_rec = f_tp / (f_tp + f_fn) if (f_tp + f_fn) > 0 else 1.0 if not gt_fillers else 0.0
    f_f1 = (2 * f_prec * f_rec) / (f_prec + f_rec) if (f_prec + f_rec) > 0 else 0.0

    # Match Pauses
    p_tp, p_fp, p_fn, p_errs = match_events(gt_pauses, det_pauses, max_tolerance_sec=1.5)
    p_prec = p_tp / (p_tp + p_fp) if (p_tp + p_fp) > 0 else 1.0 if not gt_pauses else 0.0
    p_rec = p_tp / (p_tp + p_fn) if (p_tp + p_fn) > 0 else 1.0 if not gt_pauses else 0.0

    # Match Look-Away (stratified by duration buckets)
    l_tp, l_fp, l_fn, l_errs = match_events(gt_lookaway, det_lookaway, max_tolerance_sec=1.5)
    l_rec_overall = l_tp / (l_tp + l_fn) if (l_tp + l_fn) > 0 else 1.0 if not gt_lookaway else 0.0
    false_alarms_per_min = round((l_fp / max(1.0, duration_sec)) * 60.0, 2)

    # Duration bucket analysis for lookaways
    bucket_counts = {"<1s": [0, 0], "1-2s": [0, 0], ">=2s": [0, 0]}
    for g in gt_lookaway:
        dur = g.get("duration", (g.get("end", 0.0) - g.get("start", 0.0)))
        b_key = "<1s" if dur < 1.0 else ("1-2s" if dur < 2.0 else ">=2s")
        bucket_counts[b_key][1] += 1
        # Check if matched
        g_start = g.get("start", 0.0)
        for d in det_lookaway:
            d_start = d.get("t_start", 0.0)
            if abs(d_start - g_start) <= 1.5:
                bucket_counts[b_key][0] += 1
                break

    # ASR Word Error Rate
    hyp_transcript = audio_res.get("transcript", "")
    wer = calculate_wer(ref_transcript, hyp_transcript) if ref_transcript else 0.0

    all_errs = f_errs + p_errs + l_errs
    med_err = float(np.median(all_errs)) if all_errs else 0.0
    p95_err = float(np.percentile(all_errs, 95)) if all_errs else 0.0

    return {
        "fixture": webm_path.name,
        "duration_sec": duration_sec,
        "filler": {
            "gt_count": len(gt_fillers),
            "det_count": len(det_fillers),
            "tp": f_tp, "fp": f_fp, "fn": f_fn,
            "precision": round(f_prec, 3),
            "recall": round(f_rec, 3),
            "f1": round(f_f1, 3),
        },
        "pause": {
            "gt_count": len(gt_pauses),
            "det_count": len(det_pauses),
            "tp": p_tp, "fp": p_fp, "fn": p_fn,
            "precision": round(p_prec, 3),
            "recall": round(p_rec, 3),
        },
        "lookaway": {
            "gt_count": len(gt_lookaway),
            "det_count": len(det_lookaway),
            "tp": l_tp, "fp": l_fp, "fn": l_fn,
            "recall": round(l_rec_overall, 3),
            "false_alarms_per_min": false_alarms_per_min,
            "buckets": {
                "<1s": f"{bucket_counts['<1s'][0]}/{bucket_counts['<1s'][1]}",
                "1-2s": f"{bucket_counts['1-2s'][0]}/{bucket_counts['1-2s'][1]}",
                ">=2s": f"{bucket_counts['>=2s'][0]}/{bucket_counts['>=2s'][1]}",
            },
        },
        "timestamps": {
            "median_error_sec": round(med_err, 3),
            "p95_error_sec": round(p95_err, 3),
        },
        "asr": {
            "ref_words": len(ref_transcript.split()) if ref_transcript else 0,
            "hyp_words": len(hyp_transcript.split()),
            "wer": round(wer, 3),
            "hyp_transcript": hyp_transcript,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate PLUTO vProctor pipelines on labeled fixtures.")
    parser.add_argument(
        "--fixtures-dir",
        type=str,
        default=str(ROOT_DIR / "backend" / "tests" / "fixtures" / "recordings"),
        help="Directory containing .webm and .labels.json files",
    )
    args = parser.parse_args()

    f_dir = Path(args.fixtures_dir)
    if not f_dir.exists():
        print(f"Notice: Fixtures directory not found: {f_dir}")
        print("Creating directory...")
        f_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(list(f_dir.glob("*.labels.json")))
    if not json_files:
        print(f"No .labels.json fixture files found in {f_dir}.")
        print("Please record a fixture using http://localhost:5173/dev/record-fixture or generate synthetic fixtures.")
        sys.exit(0)

    print("=" * 80)
    print(f"  PLUTO vProctor Fixture Evaluation Harness ({len(json_files)} fixtures found)")
    print("=" * 80)

    all_results = []
    for jf in json_files:
        wf = jf.with_suffix("").with_suffix(".webm")
        if not wf.exists():
            print(f"Warning: Missing video {wf.name} for labels {jf.name}")
            continue

        print(f"\nEvaluating fixture: {wf.name}...")
        res = evaluate_single_fixture(wf, jf)
        all_results.append(res)

        print(f"  * Filler F1:         {res['filler']['f1'] * 100:.1f}% (P={res['filler']['precision']:.2f}, R={res['filler']['recall']:.2f})")
        print(f"  * Pause Recall:      {res['pause']['recall'] * 100:.1f}% (det={res['pause']['det_count']}/{res['pause']['gt_count']})")
        print(f"  * Look-away Recall:  {res['lookaway']['recall'] * 100:.1f}% (>=2s: {res['lookaway']['buckets']['>=2s']})")
        print(f"  * False Alarms/min:  {res['lookaway']['false_alarms_per_min']}")
        print(f"  * Median Time Error: {res['timestamps']['median_error_sec']}s (p95: {res['timestamps']['p95_error_sec']}s)")
        print(f"  * ASR WER:           {res['asr']['wer'] * 100:.1f}%")

    # Aggregate metrics
    out_json = ROOT_DIR / "docs" / "FIXTURE_EVALUATION.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Evaluation complete. Saved results to {out_json.name}")
    print("=" * 80)


if __name__ == "__main__":
    main()

