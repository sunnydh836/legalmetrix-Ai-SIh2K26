# LegalMetrix AI — OCR & Image Quality Benchmark Suite

This directory contains the reproducible benchmark harness for evaluating OCR performance, layout extraction accuracy, and image quality diagnostics against real-world Indian packaged goods labels.

---

## Benchmark Directory Structure

```
backend/benchmarks/ocr/
├── README.md               # Benchmark methodology & execution guide
├── benchmark_runner.py     # Evaluation script (calculates CER, WER, processing time)
├── results.json            # Structured benchmark run records
├── dataset/                # Package photograph dataset
│   ├── images/             # Uploaded package photos (clear, blurry, glossy, curved, etc.)
│   └── ground_truth/       # Optional labeled reference text (.txt)
```

---

## Benchmark Categories

Real packaging photographs are categorized across 10 evaluation profiles:
1. **Clear / Front View**: High resolution, sharp focus, direct frontal angle.
2. **Back / Declaration Panel**: Dense declaration text (MRP, net qty, mfg details).
3. **Glossy / Reflective**: Highly reflective plastic wrappers with potential glare.
4. **Blurred / Motion**: Photos taken with minor motion or defocus blur.
5. **Curved / Cylindrical**: Bottles, cans, and curved packaging surfaces.
6. **Rotated / Skewed**: Labels photographed at angles requiring orientation handling.
7. **Low-Light / Shadowed**: Package photos taken in suboptimal lighting conditions.
8. **Small Text / Fine Print**: Micro-typography (ingredient lists, customer care details).
9. **Colored Background**: Low-contrast text on bright or patterned backgrounds.
10. **Multilingual**: Packages containing English, Hindi, and regional scripts.

---

## Metrics

### 1. CER (Character Error Rate)
\[
\text{CER} = \frac{S + D + I}{N}
\]
Where \(S\) is substitutions, \(D\) is deletions, \(I\) is insertions, and \(N\) is total characters in ground truth.

### 2. WER (Word Error Rate)
\[
\text{WER} = \frac{S_w + D_w + I_w}{N_w}
\]
Where \(S_w\) is word substitutions, \(D_w\) is word deletions, \(I_w\) is word insertions, and \(N_w\) is total words in ground truth.

---

## Running the Benchmark

```bash
# Run benchmark on all images in dataset/
python backend/benchmarks/ocr/benchmark_runner.py
```
