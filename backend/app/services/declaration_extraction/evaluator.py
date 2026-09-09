"""Ground-truth benchmark dataset evaluation utility for LegalMetrix AI Declaration Extraction."""
from typing import Any, Dict, List, Optional


def evaluate_declaration_benchmark(
    dataset_records: Optional[List[Dict[str, Any]]] = None,
    min_package_threshold: int = 50,
) -> Dict[str, Any]:
    """
    Evaluate precision, recall, and F1 per declaration type against a labeled ground-truth dataset.

    If fewer than min_package_threshold packages are labeled, reports 'benchmark dataset pending'
    without fabricating metrics.
    """
    if not dataset_records or len(dataset_records) < min_package_threshold:
        count = len(dataset_records) if dataset_records else 0
        return {
            "status": "benchmark dataset pending",
            "labeled_packages_count": count,
            "threshold_required": min_package_threshold,
            "message": f"Benchmark evaluation requires at least {min_package_threshold} labeled real-package fixtures ({count} provided). Synthetic numbers will not be fabricated.",
            "metrics": {},
        }

    # If sufficient packages exist, compute exact precision, recall, F1
    type_stats: Dict[str, Dict[str, int]] = {}

    for record in dataset_records:
        expected_list = record.get("expected_declarations", [])
        predicted_list = record.get("predicted_declarations", [])

        expected_map = {e["type"]: e for e in expected_list}
        predicted_map = {p["type"]: p for p in predicted_list}

        all_types = set(expected_map.keys()) | set(predicted_map.keys())

        for dtype in all_types:
            stats = type_stats.setdefault(dtype, {"tp": 0, "fp": 0, "fn": 0})
            if dtype in expected_map and dtype in predicted_map:
                exp = expected_map[dtype]
                pred = predicted_map[dtype]
                # Compare normalized values
                if exp.get("normalized_expected") == pred.get("normalized_value"):
                    stats["tp"] += 1
                else:
                    stats["fp"] += 1
            elif dtype in predicted_map:
                stats["fp"] += 1
            elif dtype in expected_map:
                stats["fn"] += 1

    per_type_metrics = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for dtype, s in type_stats.items():
        tp = s["tp"]
        fp = s["fp"]
        fn = s["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_type_metrics[dtype] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_precision * micro_recall) / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0.0

    return {
        "status": "COMPLETED",
        "labeled_packages_count": len(dataset_records),
        "overall": {
            "micro_precision": round(micro_precision, 4),
            "micro_recall": round(micro_recall, 4),
            "micro_f1": round(micro_f1, 4),
        },
        "per_declaration_metrics": per_type_metrics,
    }
