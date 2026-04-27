#!/usr/bin/env python3
"""
Compute inter-rater agreement (Cohen's kappa) and validation metrics
from the completed validation CSV files.

Run this AFTER both raters have filled in their labels in:
  - data/validation/ai_identifying/attribution_sample.csv
  - data/validation/vul_check/issue_sample.csv

Usage:
  python3 scripts/compute_validation_agreement.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VAL_DIR = BASE_DIR / "data" / "validation"


def cohens_kappa(labels_a, labels_b):
    """Compute Cohen's kappa for two raters."""
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return 0.0

    # Observed agreement
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agree / n

    # Expected agreement by chance
    all_labels = set(labels_a) | set(labels_b)
    p_e = 0.0
    for label in all_labels:
        p_a = sum(1 for x in labels_a if x == label) / n
        p_b = sum(1 for x in labels_b if x == label) / n
        p_e += p_a * p_b

    if p_e == 1.0:
        return 1.0
    kappa = (p_o - p_e) / (1 - p_e)
    return kappa


def interpret_kappa(k):
    """Landis & Koch interpretation."""
    if k < 0:
        return "Poor"
    elif k < 0.21:
        return "Slight"
    elif k < 0.41:
        return "Fair"
    elif k < 0.61:
        return "Moderate"
    elif k < 0.81:
        return "Substantial"
    else:
        return "Almost Perfect"


def validate_attribution():
    """Analyze AI attribution validation results."""
    csv_path = VAL_DIR / "ai_identifying" / "attribution_sample.csv"
    if not csv_path.exists():
        print("  File not found. Skipping.")
        return

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Check if labels are filled
    labeled = [r for r in rows if r.get("label_rater1") and r.get("label_rater2")]
    if not labeled:
        print("  No labels found yet. Fill in label_rater1 and label_rater2 columns first.")
        return

    print(f"  Total samples: {len(rows)}")
    print(f"  Labeled: {len(labeled)}")

    labels_1 = [r["label_rater1"].strip().lower() for r in labeled]
    labels_2 = [r["label_rater2"].strip().lower() for r in labeled]

    # Cohen's kappa
    kappa = cohens_kappa(labels_1, labels_2)
    print(f"\n  Cohen's kappa: {kappa:.3f} ({interpret_kappa(kappa)})")

    # Agreement rate
    agree = sum(1 for a, b in zip(labels_1, labels_2) if a == b)
    print(f"  Raw agreement: {agree}/{len(labeled)} ({agree/len(labeled)*100:.1f}%)")

    # Distribution per rater
    print(f"\n  Rater 1 distribution: {dict(Counter(labels_1))}")
    print(f"  Rater 2 distribution: {dict(Counter(labels_2))}")

    # Final labels (after resolution)
    final_labeled = [r for r in rows if r.get("label_final")]
    if final_labeled:
        final_labels = [r["label_final"].strip().lower() for r in final_labeled]
        correct = sum(1 for l in final_labels if l == "correct")
        total = len(final_labels)
        print(f"\n  Final labels: {total}")
        print(f"  Correctly attributed: {correct}/{total} ({correct/total*100:.1f}%)")
        print(f"  Precision: {correct/total*100:.1f}%")

        # By tool
        by_tool = {}
        for r in final_labeled:
            tool = r["ai_tool"]
            label = r["label_final"].strip().lower()
            by_tool.setdefault(tool, {"correct": 0, "total": 0})
            by_tool[tool]["total"] += 1
            if label == "correct":
                by_tool[tool]["correct"] += 1

        print("\n  By tool:")
        for tool in sorted(by_tool):
            d = by_tool[tool]
            pct = d["correct"] / d["total"] * 100 if d["total"] else 0
            print(f"    {tool}: {d['correct']}/{d['total']} ({pct:.1f}%)")


def validate_issues():
    """Analyze issue detection & survival validation results."""
    csv_path = VAL_DIR / "vul_check" / "issue_sample.csv"
    if not csv_path.exists():
        print("  File not found. Skipping.")
        return

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"  Total samples: {len(rows)}")

    # ── Issue Detection ──
    det_labeled = [
        r for r in rows
        if r.get("is_real_issue_rater1") and r.get("is_real_issue_rater2")
    ]
    if det_labeled:
        print(f"\n  Issue Detection:")
        print(f"    Labeled: {len(det_labeled)}")

        d1 = [r["is_real_issue_rater1"].strip().lower() for r in det_labeled]
        d2 = [r["is_real_issue_rater2"].strip().lower() for r in det_labeled]

        kappa = cohens_kappa(d1, d2)
        agree = sum(1 for a, b in zip(d1, d2) if a == b)
        print(f"    Cohen's kappa: {kappa:.3f} ({interpret_kappa(kappa)})")
        print(f"    Raw agreement: {agree}/{len(det_labeled)} ({agree/len(det_labeled)*100:.1f}%)")

        final = [r for r in rows if r.get("is_real_issue_final")]
        if final:
            real = sum(1 for r in final if r["is_real_issue_final"].strip().lower() == "yes")
            print(f"    Issue detection precision: {real}/{len(final)} ({real/len(final)*100:.1f}%)")
    else:
        print("\n  Issue Detection: No labels found yet.")

    # ── Survival Classification ──
    surv_labeled = [
        r for r in rows
        if r.get("survival_correct_rater1") and r.get("survival_correct_rater2")
    ]
    if surv_labeled:
        print(f"\n  Survival Classification:")
        print(f"    Labeled: {len(surv_labeled)}")

        s1 = [r["survival_correct_rater1"].strip().lower() for r in surv_labeled]
        s2 = [r["survival_correct_rater2"].strip().lower() for r in surv_labeled]

        kappa = cohens_kappa(s1, s2)
        agree = sum(1 for a, b in zip(s1, s2) if a == b)
        print(f"    Cohen's kappa: {kappa:.3f} ({interpret_kappa(kappa)})")
        print(f"    Raw agreement: {agree}/{len(surv_labeled)} ({agree/len(surv_labeled)*100:.1f}%)")

        final = [r for r in rows if r.get("survival_correct_final")]
        if final:
            correct = sum(1 for r in final if r["survival_correct_final"].strip().lower() == "yes")
            print(f"    Survival accuracy: {correct}/{len(final)} ({correct/len(final)*100:.1f}%)")
    else:
        print("\n  Survival Classification: No labels found yet.")


def main():
    print("=" * 60)
    print("Validation Agreement Analysis")
    print("=" * 60)

    print("\n[1] AI Attribution Validation")
    validate_attribution()

    print("\n[2] Issue Detection & Survival Validation")
    validate_issues()

    print()


if __name__ == "__main__":
    main()
