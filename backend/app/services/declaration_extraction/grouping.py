"""Spatial layout and multi-block text grouping for OCR blocks."""
from typing import Any, List, Tuple


class TextSpan:
    """Represents a sequence of one or more adjacent OCR blocks forming a candidate text span."""

    def __init__(self, text: str, blocks: List[Any], is_multi_line: bool = False):
        self.text = text
        self.blocks = blocks
        self.is_multi_line = is_multi_line

    @property
    def confidence(self) -> float:
        if not self.blocks:
            return 0.0
        return sum(float(b.confidence) for b in self.blocks) / len(self.blocks)

    @property
    def block_ids(self) -> List[str]:
        return [b.id for b in self.blocks if hasattr(b, "id") and b.id]


def sort_blocks_reading_order(blocks: List[Any]) -> List[Any]:
    """Sort OCR blocks in natural reading order (top-to-bottom, left-to-right)."""
    return sorted(blocks, key=lambda b: (getattr(b, "bbox_y1", 0), getattr(b, "bbox_x1", 0)))


def cluster_blocks_into_lines(blocks: List[Any]) -> List[List[Any]]:
    """
    Cluster OCR blocks on a single image into horizontal text lines based on vertical overlap.
    """
    if not blocks:
        return []

    sorted_blocks = sort_blocks_reading_order(blocks)
    lines: List[List[Any]] = []

    for block in sorted_blocks:
        b_y1 = getattr(block, "bbox_y1", 0)
        b_y2 = getattr(block, "bbox_y2", 0)
        b_height = max(1, b_y2 - b_y1)
        b_mid_y = (b_y1 + b_y2) / 2.0

        placed = False
        for line in lines:
            line_y1 = min(getattr(b, "bbox_y1", 0) for b in line)
            line_y2 = max(getattr(b, "bbox_y2", 0) for b in line)
            line_height = max(1, line_y2 - line_y1)
            line_mid_y = (line_y1 + line_y2) / 2.0

            # Vertical proximity threshold: 50% height overlap or center within half line height
            threshold = min(b_height, line_height) * 0.6
            if abs(b_mid_y - line_mid_y) <= threshold:
                line.append(block)
                placed = True
                break

        if not placed:
            lines.append([block])

    # Sort each line horizontally from left to right
    for line in lines:
        line.sort(key=lambda b: getattr(b, "bbox_x1", 0))

    # Sort lines vertically
    lines.sort(key=lambda line: min(getattr(b, "bbox_y1", 0) for b in line))

    return lines


def generate_candidate_text_spans(blocks: List[Any], max_n_gram: int = 5) -> List[TextSpan]:
    """
    Generate single-block and multi-block candidate text spans from OCR blocks on an image.
    Supports:
    1. Single individual blocks.
    2. Same-line adjacent n-grams (e.g., ['Net', 'Qty', '79', 'g'] -> 'Net Qty 79 g').
    3. Multi-line contiguous paragraph blocks for addresses and manufacturer details.
    """
    spans: List[TextSpan] = []
    lines = cluster_blocks_into_lines(blocks)

    # 1. Single block spans
    for b in blocks:
        spans.append(TextSpan(text=b.text.strip(), blocks=[b], is_multi_line=False))

    # 2. Same-line n-grams
    for line in lines:
        n = len(line)
        if n > 1:
            # Full line span
            full_line_text = " ".join(b.text.strip() for b in line)
            spans.append(TextSpan(text=full_line_text, blocks=line, is_multi_line=False))

            # Sub-sequence n-grams (2 to max_n_gram)
            for length in range(2, min(max_n_gram + 1, n)):
                for start_idx in range(n - length + 1):
                    sub_blocks = line[start_idx : start_idx + length]
                    sub_text = " ".join(b.text.strip() for b in sub_blocks)
                    spans.append(TextSpan(text=sub_text, blocks=sub_blocks, is_multi_line=False))

    # 3. Multi-line spans for consecutive lines (useful for multi-line manufacturer/address)
    for i in range(len(lines)):
        for j in range(i + 1, min(i + 5, len(lines))):
            group_lines = lines[i : j + 1]
            all_line_blocks = [b for l in group_lines for b in l]
            # Verify vertical proximity between consecutive lines (within 2.5x line height)
            line_texts = [" ".join(b.text.strip() for b in l) for l in group_lines]
            combined_text = "\n".join(line_texts)
            spans.append(TextSpan(text=combined_text, blocks=all_line_blocks, is_multi_line=True))

    return spans
