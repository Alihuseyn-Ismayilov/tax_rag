"""
3_chunk_simple.py
-----------------
Step 1 of chunking pipeline (Agile Sprint 1):
Filters Q&A pairs that are short enough to be embedded as a single chunk
(combined question + answer <= 1500 chars), formats them, attaches metadata,
and saves to data/processed/chunks_simple.json.

Next step: 3_chunk_long.py will handle records that need paragraph splitting.
"""

import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_PATH  = Path("../data/processed/clean_data.csv")
OUTPUT_PATH = Path("../data/processed/chunks_simple.json")

# Combined Q+A character limit — records at or below this are kept as one chunk.
# Based on analysis: ~1500 chars ≈ 350-400 tokens, safely fits most embedding
# model windows (512 tokens). Records above this go to 3_chunk_long.py.
CHUNK_THRESHOLD = 1500

# Source label embedded in every chunk for traceability
SOURCE_SITE = "https://www.taxes.gov.az/az/page/suallar-ve-cavablar"


# ── Helpers ───────────────────────────────────────────────────────────────────
def build_chunk_text(question: str, answer: str) -> str:
    """
    Combine question and answer into a single embedding-ready string.
    Labelling both parts helps multilingual embedding models (e.g.
    paraphrase-multilingual-mpnet) understand the semantic roles.
    """
    return f"Sual: {question.strip()}\nCavab: {answer.strip()}"


def make_chunk(row: pd.Series, chunk_text: str) -> dict:
    """
    Build a chunk dict with all metadata fields.
    chunk_index and total_chunks are both 0 for single-chunk records —
    this makes it easy to filter/identify them later in the DB.
    """
    return {
        # ── Retrieval content ──────────────────────────────────────────────
        "chunk_text":    chunk_text,       # what gets embedded
        "question":      row["question"].strip(),
        "answer":        row["answer"].strip(),

        # ── Identity & traceability ────────────────────────────────────────
        "source_id":     int(row["id"]),   # original row ID from taxes.gov.az
        "source_url":    SOURCE_SITE,
        "chunk_index":   0,                # first (and only) chunk of this record
        "total_chunks":  1,                # single-chunk record marker
        "chunk_type":    "simple",         # simple | paragraph (set by long chunker)

        # ── Quality signals (usable for DB filtering / re-ranking) ─────────
        "answer_date":   row["answer_date"],
        "read_count":    int(row["read_count"]),
        "average_rate":  int(row["average_rate"]),
        "rate_count":    int(row["rate_count"]),

        # ── Length info (useful for debugging / future analysis) ───────────
        "question_len":  len(row["question"]),
        "answer_len":    len(row["answer"]),
        "combined_len":  len(row["question"]) + len(row["answer"]),

        # ── Pipeline audit ─────────────────────────────────────────────────
        "chunked_at":    datetime.now(timezone.utc).isoformat(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # 1. Load
    log.info(f"Reading {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH)
    log.info(f"Loaded {len(df):,} total records")

    # 2. Compute combined length and filter
    df["_combined_len"] = df["question"].str.len() + df["answer"].str.len()
    simple_df  = df[df["_combined_len"] <= CHUNK_THRESHOLD].copy()
    skipped_df = df[df["_combined_len"] >  CHUNK_THRESHOLD].copy()

    log.info(
        f"Simple chunks (≤ {CHUNK_THRESHOLD} chars): {len(simple_df):,} "
        f"({len(simple_df)/len(df)*100:.1f}%)"
    )
    log.info(
        f"Skipped for long chunker (> {CHUNK_THRESHOLD} chars): {len(skipped_df):,} "
        f"({len(skipped_df)/len(df)*100:.1f}%)"
    )

    # 3. Build chunks
    chunks = []
    for _, row in simple_df.iterrows():
        chunk_text = build_chunk_text(row["question"], row["answer"])
        chunks.append(make_chunk(row, chunk_text))

    log.info(f"Built {len(chunks):,} chunks")

    # 4. Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    log.info(f"Saved → {OUTPUT_PATH}")

    # 5. Quick sanity summary
    lengths = [c["combined_len"] for c in chunks]
    log.info(
        f"Chunk length summary — "
        f"min: {min(lengths)}, "
        f"max: {max(lengths)}, "
        f"mean: {sum(lengths)//len(lengths)}"
    )

    # 6. Preview first chunk
    log.info("─── First chunk preview ───")
    preview = chunks[0]
    for k, v in preview.items():
        val = str(v)[:120] + "..." if len(str(v)) > 120 else v
        print(f"  {k:<16}: {val}")


if __name__ == "__main__":
    main()
