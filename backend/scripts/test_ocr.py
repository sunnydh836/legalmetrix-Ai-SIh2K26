"""
Standalone CLI tool for running local OCR and image quality analysis.
Usage:
    python scripts/test_ocr.py path/to/image.jpg
"""
import sys
import os
import json
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.image_quality_service import OpenCVImageQualityService
from app.services.ocr_service import PaddleOCRService


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ocr.py <path_to_image>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' does not exist.")
        sys.exit(1)

    print("=" * 60)
    print("LegalMetrix AI — Day 4 Local Image Quality & OCR Benchmark")
    print("=" * 60)
    print(f"Target Image: {image_path}")

    # 1. Quality Analysis
    print("\n[1] Running OpenCV Image Quality Analysis...")
    quality_service = OpenCVImageQualityService()
    start_q = time.perf_counter()
    quality_res = quality_service.evaluate_quality(image_path)
    q_dur = (time.perf_counter() - start_q) * 1000

    print(f"  - Quality Status:    {quality_res.quality_status.value}")
    print(f"  - Blur Score:        {quality_res.blur_score} (Threshold: {quality_service.blur_threshold})")
    print(f"  - Glare Score:       {quality_res.glare_score} (Threshold: {quality_service.glare_threshold})")
    print(f"  - Resolution:        {quality_res.resolution['width']}x{quality_res.resolution['height']}")
    print(f"  - Warnings:          {[w.value for w in quality_res.warnings] or 'None'}")
    print(f"  - Quality Engine:    {quality_service.engine_version}")
    print(f"  - Quality Duration:  {q_dur:.1f}ms")

    # 2. Local PaddleOCR
    print("\n[2] Running Local PaddleOCR Engine (RapidOCR ONNX Runtime)...")
    ocr_service = PaddleOCRService()
    start_ocr = time.perf_counter()
    ocr_res = ocr_service.process_image(image_path)
    ocr_dur = (time.perf_counter() - start_ocr) * 1000

    print(f"  - OCR Engine:        {ocr_res.engine} (version: {ocr_res.engine_version})")
    print(f"  - OCR Duration:      {ocr_res.processing_duration_ms}ms (total: {ocr_dur:.1f}ms)")
    print(f"  - Blocks Extracted:  {len(ocr_res.blocks)}")

    print("\n[3] Extracted OCR Text Blocks (Ordered by Reading Order):")
    print("-" * 60)
    for idx, block in enumerate(ocr_res.blocks):
        print(f"  [{block.block_order + 1:02d}] \"{block.text}\"")
        print(f"       Confidence: {block.confidence * 100:.1f}%")
        print(f"       BoundingBox: [{block.bbox.x1}, {block.bbox.y1}, {block.bbox.x2}, {block.bbox.y2}]")
        print(f"       Polygon: {block.polygon}")
    print("-" * 60)
    print("Execution completed successfully.")


if __name__ == "__main__":
    main()
