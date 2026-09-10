"""Spatial layout and multi-block text grouping for OCR blocks.

Hardened v1.5.0:
- Multi-line span generation now enforces a vertical proximity guard: consecutive
  line-groups must be within MAX_LINE_GAP_FACTOR × their average line height to be
  merged. This prevents address blocks on opposite sides of the label being combined.
- Added sort_blocks_reading_order and cluster_blocks_into_lines improvements.
"""
from typing import Any, List, Tuple

# Maximum allowed gap between consecutive lines relative to average line height,
# for multi-line span grouping.  1.8× means "at most ~2 line heights apart."
MAX_LINE_GAP_FACTOR: float = 1.8


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


def _line_height(line: List[Any]) -> float:
    """Compute the average height of blocks in a line cluster."""
    if not line:
        return 0.0
    heights = [
        max(1, getattr(b, "bbox_y2", 0) - getattr(b, "bbox_y1", 0))
        for b in line
    ]
    return sum(heights) / len(heights)


def _lines_are_proximate(line_a: List[Any], line_b: List[Any]) -> bool:
    """Return True if line_b immediately follows line_a within MAX_LINE_GAP_FACTOR."""
    if not line_a or not line_b:
        return False
    a_y2 = max(getattr(b, "bbox_y2", 0) for b in line_a)
    b_y1 = min(getattr(b, "bbox_y1", 0) for b in line_b)
    gap = b_y1 - a_y2  # positive means line_b is below line_a

    avg_h = (_line_height(line_a) + _line_height(line_b)) / 2.0
    max_gap = avg_h * MAX_LINE_GAP_FACTOR
    return gap <= max_gap


def get_block_distance(b1: Any, b2: Any) -> Tuple[float, float]:
    """Calculate horizontal and vertical distance between two blocks."""
    # Horizontal distance (closest edges)
    # If overlapping horizontally, dx = 0
    b1_x1, b1_x2 = getattr(b1, "bbox_x1", 0), getattr(b1, "bbox_x2", 0)
    b2_x1, b2_x2 = getattr(b2, "bbox_x1", 0), getattr(b2, "bbox_x2", 0)
    if b1_x2 < b2_x1:
        dx = b2_x1 - b1_x2
    elif b2_x2 < b1_x1:
        dx = b1_x1 - b2_x2
    else:
        dx = 0.0

    # Vertical distance
    b1_y1, b1_y2 = getattr(b1, "bbox_y1", 0), getattr(b1, "bbox_y2", 0)
    b2_y1, b2_y2 = getattr(b2, "bbox_y1", 0), getattr(b2, "bbox_y2", 0)
    if b1_y2 < b2_y1:
        dy = b2_y1 - b1_y2
    elif b2_y2 < b1_y1:
        dy = b1_y1 - b2_y2
    else:
        dy = 0.0

    return dx, dy


def find_neighborhood_blocks(
    anchor_span: TextSpan,
    all_blocks: List[Any],
    max_horizontal_gap: float = 250.0,
    max_vertical_gap: float = 80.0,
) -> List[Any]:
    """
    Given an anchor span, find all blocks in `all_blocks` that are spatially nearby
    (within max_horizontal_gap and max_vertical_gap).
    Excludes the blocks already in the anchor_span.
    """
    nearby_blocks = []
    anchor_ids = set(anchor_span.block_ids)

    # Determine bounding box of anchor span
    if not anchor_span.blocks:
        return []

    a_x1 = min(getattr(b, "bbox_x1", 0) for b in anchor_span.blocks)
    a_x2 = max(getattr(b, "bbox_x2", 0) for b in anchor_span.blocks)
    a_y1 = min(getattr(b, "bbox_y1", 0) for b in anchor_span.blocks)
    a_y2 = max(getattr(b, "bbox_y2", 0) for b in anchor_span.blocks)

    # Create a synthetic anchor block object to measure distances
    class SyntheticBlock:
        def __init__(self, x1, y1, x2, y2):
            self.bbox_x1, self.bbox_y1 = x1, y1
            self.bbox_x2, self.bbox_y2 = x2, y2

    synth_anchor = SyntheticBlock(a_x1, a_y1, a_x2, a_y2)

    for b in all_blocks:
        b_id = getattr(b, "id", None)
        if b_id in anchor_ids:
            continue
        
        dx, dy = get_block_distance(synth_anchor, b)
        if dx <= max_horizontal_gap and dy <= max_vertical_gap:
            nearby_blocks.append((b, dx, dy))
    
    # Sort by spatial proximity (vertical matters a bit more than horizontal generally for reading order, 
    # but we can sort by simple Euclidean distance approximation)
    nearby_blocks.sort(key=lambda item: item[1] + item[2])
    
    return [b for b, dx, dy in nearby_blocks]



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

            # Vertical proximity threshold: 60% height overlap or center within half line height
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


def generate_candidate_text_spans(blocks: List[Any], max_n_gram: int = 6) -> List[TextSpan]:
    """
    Generate single-block and multi-block candidate text spans from OCR blocks on an image.
    Supports:
    1. Single individual blocks.
    2. Same-line adjacent n-grams (e.g., ['Net', 'Qty', '79', 'g'] -> 'Net Qty 79 g').
    3. Multi-line contiguous paragraph blocks for addresses and manufacturer details,
       subject to a vertical proximity guard to prevent distant blocks being merged.
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
                    sub_blocks = line[start_idx: start_idx + length]
                    sub_text = " ".join(b.text.strip() for b in sub_blocks)
                    spans.append(TextSpan(text=sub_text, blocks=sub_blocks, is_multi_line=False))

    # 3. Multi-line spans for consecutive proximate lines (useful for multi-line manufacturer/address)
    # Subject to vertical proximity guard: consecutive lines must be within MAX_LINE_GAP_FACTOR.
    for i in range(len(lines)):
        # Progressively expand the group, but only if each successive line is proximate.
        group_lines: List[List[Any]] = [lines[i]]
        for j in range(i + 1, min(i + 5, len(lines))):
            if not _lines_are_proximate(group_lines[-1], lines[j]):
                break  # Stop once lines are too far apart
            group_lines.append(lines[j])

            all_line_blocks = [b for ln in group_lines for b in ln]
            line_texts = [" ".join(b.text.strip() for b in ln) for ln in group_lines]
            combined_text = "\n".join(line_texts)
            spans.append(TextSpan(text=combined_text, blocks=all_line_blocks, is_multi_line=True))

    return spans
