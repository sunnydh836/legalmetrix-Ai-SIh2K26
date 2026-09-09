"""
LegalMetrix AI — OCR Benchmark Runner
Evaluates real package photographs, computes OpenCV quality metrics, runs local PaddleOCR,
and calculates CER/WER against ground truth when available.
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.image_quality_service import OpenCVImageQualityService
from app.services.ocr_service import PaddleOCRService


def calculate_levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Standard Levenshtein distance matrix computation."""
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = [[0] * size_y for _ in range(size_x)]
    for x in range(size_x):
        matrix[x][0] = x
    for y in range(size_y):
        matrix[0][y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x - 1] == seq2[y - 1]:
                matrix[x][y] = matrix[x - 1][y - 1]
            else:
                matrix[x][y] = min(
                    matrix[x - 1][y] + 1,      # Deletion
                    matrix[x][y - 1] + 1,      # Insertion
                    matrix[x - 1][y - 1] + 1   # Substitution
                )
    return matrix[size_x - 1][size_y - 1]


def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate calculation."""
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = calculate_levenshtein_distance(ref_chars, hyp_chars)
    return round(min(1.0, dist / len(ref_chars)), 4)


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate calculation."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = calculate_levenshtein_distance(ref_words, hyp_words)
    return round(min(1.0, dist / len(ref_words)), 4)


def run_benchmark(dataset_dir: Optional[str] = None) -> List[Dict]:
    benchmark_dir = Path(__file__).resolve().parent
    img_dir = Path(dataset_dir) if dataset_dir else benchmark_dir / "dataset" / "images"
    gt_dir = benchmark_dir / "dataset" / "ground_truth"

    quality_service = OpenCVImageQualityService()
    ocr_service = PaddleOCRService()

    image_files = []
    if img_dir.exists():
        image_files = sorted(
            [p for p in img_dir.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
        )

    results = []

    print("=" * 70)
    print(f"LegalMetrix AI — OCR Benchmark Execution ({len(image_files)} images found)")
    print("=" * 70)

    for img_path in image_files:
        print(f"\nProcessing: {img_path.name}")
        gt_path = gt_dir / f"{img_path.stem}.txt"
        has_gt = gt_path.is_file()
        ground_truth_text = ""
        if has_gt:
            with open(gt_path, "r", encoding="utf-8") as f:
                ground_truth_text = f.read().strip()

        # Quality
        start_q = time.perf_counter()
        q_res = quality_service.evaluate_quality(str(img_path))
        q_time_ms = int((time.perf_counter() - start_q) * 1000)

        # OCR
        start_ocr = time.perf_counter()
        ocr_res = ocr_service.process_image(str(img_path))
        ocr_time_ms = int((time.perf_counter() - start_ocr) * 1000)

        detected_text = " ".join(b.text for b in ocr_res.blocks)

        cer = compute_cer(ground_truth_text, detected_text) if has_gt else None
        wer = compute_wer(ground_truth_text, detected_text) if has_gt else None

        record = {
            "filename": img_path.name,
            "dimensions": f"{q_res.resolution['width']}x{q_res.resolution['height']}",
            "quality_status": q_res.quality_status.value,
            "blur_score": q_res.blur_score,
            "glare_score": q_res.glare_score,
            "warnings": [w.value for w in q_res.warnings],
            "ocr_block_count": len(ocr_res.blocks),
            "ocr_duration_ms": ocr_res.processing_duration_ms,
            "ground_truth_available": has_gt,
            "cer": cer,
            "wer": wer,
            "extracted_preview": detected_text[:80] + ("..." if len(detected_text) > 80 else ""),
        }
        results.append(record)

        print(f"  Quality: {record['quality_status']} | Blur: {record['blur_score']} | Glare: {record['glare_score']}")
        print(f"  OCR: {record['ocr_block_count']} blocks extracted in {record['ocr_duration_ms']}ms")
        if has_gt:
            print(f"  CER: {cer * 100:.1f}% | WER: {wer * 100:.1f}%")
        else:
            print("  Ground Truth: Not provided (CER/WER pending)")

    # Save results to JSON
    out_file = benchmark_dir / "results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Benchmark completed. Output saved to: {out_file}")
    return results


if __name__ == "__main__":
    run_benchmark()
