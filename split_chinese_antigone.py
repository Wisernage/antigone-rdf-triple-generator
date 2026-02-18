#!/usr/bin/env python3
"""
Split Luo Niensheng's Chinese Antigone translation (PDF) into verse ranges 1-1352.

The Chinese text uses scene markers (開場, 第一場, etc.) which are mapped to the
standard Sophocles Antigone verse structure. Output files follow the project's
naming: aZH_{start}_to_{end}.txt

Usage:
    python split_chinese_antigone.py <path_to_pdf>
    python split_chinese_antigone.py "C:\\Users\\Jim\\Downloads\\Sophocles=Antigone.pdf"

Output: [PRODUCTIONS]_CHINESE/verse_{start}_to_{end}/chinese/aZH_{start}_to_{end}.txt

Note: The Chinese translation has no verse-level line numbers. Splitting is done by
scene markers (開場, 第一場, etc.) mapped to standard Antigone verse ranges. For
fine-grained verse alignment (e.g., line 966 only), manual alignment with the Greek
or English text would be needed.
"""

import re
import sys
from pathlib import Path


# Standard Antigone verse structure (Perseus/Teubner numbering)
# Maps Chinese scene markers to verse ranges
VERSE_STRUCTURE = [
    (1, 99, "Prologue"),           # 開場 - Antigone & Ismene
    (100, 162, "Parodos"),         # 進場歌 - Chorus enters
    (163, 331, "First episode"),   # 第一場 - Creon, Guard
    (332, 375, "First stasimon"), # 第一合唱歌
    (376, 581, "Second episode"),  # 第二場 - Antigone arrested
    (582, 625, "Second stasimon"),
    (626, 780, "Third episode"),   # 第三場 - Haemon
    (781, 800, "Third stasimon"),
    (801, 943, "Fourth episode"),  # 第四場 - Antigone to tomb
    (944, 987, "Fourth stasimon"),
    (988, 1114, "Fifth episode"), # 第五場 - Tiresias
    (1115, 1154, "Fifth stasimon"),
    (1155, 1352, "Exodos"),       # 退場 - Messenger, Eurydice, Creon
]

# Chinese scene markers in order (regex patterns)
# The Chinese doesn't separate parodos/stasima, so we split by 場
CHINESE_SCENE_MARKERS = [
    (r"開\s*場\s*\[1\]", 1, 99),      # Prologue
    (r"第\s*一\s*場", 100, 331),       # Parodos + First episode
    (r"第\s*二\s*場", 332, 581),       # First stasimon + Second episode
    (r"第\s*三\s*場", 582, 780),       # Second stasimon + Third episode
    (r"第\s*四\s*場", 781, 943),       # Third stasimon + Fourth episode
    (r"第\s*五\s*場", 944, 1114),      # Fourth stasimon + Fifth episode
    (r"退\s*場", 1115, 1352),          # Fifth stasimon + Exodos
]


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required. Install with: pip install pypdf")
    
    reader = PdfReader(str(pdf_path))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def extract_text_from_txt(txt_path: Path) -> str:
    """Read text from a plain text file."""
    return txt_path.read_text(encoding="utf-8")


def clean_text(text: str) -> str:
    """Remove page markers and normalize whitespace."""
    # Remove " - N of 24 - " style page markers
    text = re.sub(r"\s*--\s*\d+\s+of\s+\d+\s+--\s*", "\n\n", text)
    # Remove standalone page numbers
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_by_scenes(text: str) -> list[tuple[int, int, str]]:
    """
    Split Chinese text by scene markers. Returns list of (start_verse, end_verse, content).
    """
    text = clean_text(text)
    results = []
    
    # Find all scene marker positions
    positions = []
    for pattern, start_verse, end_verse in CHINESE_SCENE_MARKERS:
        for m in re.finditer(pattern, text):
            positions.append((m.start(), m.end(), start_verse, end_verse, m.group(0)))
            break  # First match only per pattern
    
    # Sort by position
    positions.sort(key=lambda x: x[0])
    
    # Extract content between markers
    for i, (pos_start, pos_end, start_verse, end_verse, marker) in enumerate(positions):
        if i + 1 < len(positions):
            content_end = positions[i + 1][0]
            content = text[pos_start:content_end].strip()
        else:
            content = text[pos_start:].strip()
        
        # Remove the marker from content start (we'll keep it for context)
        results.append((start_verse, end_verse, content))
    
    return results


def split_simple_by_verse_ranges(text: str) -> list[tuple[int, int, str]]:
    """
    Simpler approach: split by scene markers and assign to verse ranges.
    Used when we can't do fine-grained alignment.
    """
    text = clean_text(text)
    results = []
    
    # Split at each 場 marker
    parts = re.split(
        r"(開\s*場\s*\[1\]|第\s*一\s*場|第\s*二\s*場|第\s*三\s*場|第\s*四\s*場|第\s*五\s*場|退\s*場)",
        text,
    )
    
    # parts[0] = front matter (characters, etc.), parts[1] = first marker, parts[2] = first content, ...
    verse_ranges = [(1, 99), (100, 331), (332, 581), (582, 780), (781, 943), (944, 1114), (1115, 1352)]
    idx = 0
    i = 1
    while i < len(parts) and idx < len(verse_ranges):
        marker = parts[i]
        content = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        start, end = verse_ranges[idx]
        full_content = marker + "\n" + content if content else marker
        results.append((start, end, full_content))
        idx += 1
        i += 2
    
    return results


def write_output(
    sections: list[tuple[int, int, str]],
    output_dir: Path,
) -> None:
    """Write verse range files to output directory."""
    output_dir = Path(output_dir)
    
    for start_verse, end_verse, content in sections:
        verse_range_name = f"verse_{start_verse}_to_{end_verse}"
        verse_dir = output_dir / verse_range_name / "chinese"
        verse_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"aZH_{start_verse}_to_{end_verse}.txt"
        filepath = verse_dir / filename
        filepath.write_text(content, encoding="utf-8")
        print(f"  Wrote {filepath.relative_to(output_dir)}")
    
    # Also write full play as verse_1_to_1352
    full_content = "\n\n".join(
        f"=== Verses {s}-{e} ===\n{c}" for s, e, c in sections
    )
    verse_dir = output_dir / "verse_1_to_1352" / "chinese"
    verse_dir.mkdir(parents=True, exist_ok=True)
    filepath = verse_dir / "aZH_1_to_1352.txt"
    filepath.write_text(full_content, encoding="utf-8")
    print(f"  Wrote {filepath.relative_to(output_dir)} (full play)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Please provide the path to the PDF or TXT file.")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    # Output to [PRODUCTIONS]_CHINESE in project root
    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "[PRODUCTIONS]_CHINESE"
    
    print(f"Reading: {input_path}")
    
    if input_path.suffix.lower() == ".pdf":
        text = extract_text_from_pdf(input_path)
    else:
        text = extract_text_from_txt(input_path)
    
    print(f"Extracted {len(text)} characters")
    
    sections = split_simple_by_verse_ranges(text)
    print(f"Split into {len(sections)} sections")
    
    for start, end, content in sections:
        print(f"  Verses {start}-{end}: {len(content)} chars")
    
    print(f"\nWriting to {output_dir}")
    write_output(sections, output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
