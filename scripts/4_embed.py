"""
4_embed.py
----------
Embeds chunked Q&A pairs using intfloat/multilingual-e5-large.

Input  : ../data/processed/chunks_simple.json   (Sprint 1 — simple chunks)
         ../data/processed/chunks_all.json       (Future — after long chunker is added)
Output : ../data/processed/chunks_embedded.json
         ../data/processed/embed_failures.json   (only created if failures occur)

Scalability notes
-----------------
- INPUT_PATH is a single config constant. When chunks_all.json is ready,
  change one line and re-run — nothing else changes.
- chunk_type field ("simple" | "paragraph") is preserved so downstream DB
  can filter or weight chunk types independently.
- Model is swappable via MODEL_NAME constant. All E5 variants share the
  same prefix convention so switching e.g. to multilingual-e5-base or
  multilingual-e5-small requires only changing MODEL_NAME.
- Batch size is tunable. On GPU, increase to 128+. On CPU keep at 32.

E5 prefix convention (important)
---------------------------------
multilingual-e5 models require specific prefixes at inference time:
  - Documents (chunks being indexed) → "passage: {text}"
  - Queries (user questions at search time) → "query: {text}"
This asymmetric design is what makes E5 outperform mpnet on retrieval tasks.
The prefix is added here at embed time so the DB stores correctly prefixed vectors.
At query time, your chatbot must also prepend "query: " before embedding.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# INPUT: change to chunks_all.json once long chunker (Sprint 2) is complete
INPUT_PATH   = Path("../data/processed/chunks_simple.json")
OUTPUT_PATH  = Path("../data/processed/chunks_embedded.json")
FAILURE_PATH = Path("../data/processed/embed_failures.json")

# Model — swap to multilingual-e5-base or multilingual-e5-small if RAM is tight
MODEL_NAME = "intfloat/multilingual-e5-large"

# Batch size — 32 is safe for CPU; increase to 64-128 on GPU
BATCH_SIZE = 32

# E5 document prefix — must match what the model was trained with
E5_DOC_PREFIX = "passage: "

# Normalize vectors to unit length — required for cosine similarity search
NORMALIZE = True


# ── Core functions ────────────────────────────────────────────────────────────

def load_model(model_name: str) -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"Loading model: {model_name}  (device: {device})")
    model = SentenceTransformer(model_name, device=device)
    log.info(
        f"Model ready — dim: {model.get_sentence_embedding_dimension()}, "
        f"max_seq_len: {model.max_seq_length}"
    )
    return model


def prepare_texts(chunks: list[dict]) -> list[str]:
    """
    Prepend E5 document prefix to every chunk_text.
    chunk_text already contains 'Sual: ... Cavab: ...' formatting
    from the chunking step, so we get: 'passage: Sual: ... Cavab: ...'
    """
    return [E5_DOC_PREFIX + c["chunk_text"] for c in chunks]


def embed_in_batches(
    model: SentenceTransformer,
    texts: list[str],
    batch_size: int,
    normalize: bool,
) -> tuple[list[list[float]], list[int]]:
    """
    Embed texts in batches with progress bar and per-batch error handling.

    Returns:
        vectors      : list of embedding vectors (float lists), None for failed batches
        failed_indices: flat list of chunk indices that failed
    """
    vectors = [None] * len(texts)
    failed_indices = []

    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
    log.info(f"Embedding {len(texts):,} chunks in {len(batches):,} batches (batch_size={batch_size})")

    for batch_num, (batch_texts) in enumerate(tqdm(batches, desc="Embedding", unit="batch")):
        start_idx = batch_num * batch_size
        try:
            vecs = model.encode(
                batch_texts,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            for i, vec in enumerate(vecs):
                vectors[start_idx + i] = vec.tolist()

        except Exception as e:
            log.warning(f"Batch {batch_num} failed: {e}. Marking {len(batch_texts)} chunks as failed.")
            for i in range(len(batch_texts)):
                failed_indices.append(start_idx + i)

    return vectors, failed_indices


def attach_embeddings(
    chunks: list[dict],
    vectors: list[list[float]],
    failed_indices: set[int],
    model_name: str,
    embedding_dim: int,
) -> tuple[list[dict], list[dict]]:
    """
    Attach embedding vectors and metadata to each chunk.
    Splits into successful and failed lists.
    """
    embedded = []
    failed   = []
    ts = datetime.now(timezone.utc).isoformat()

    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        if idx in failed_indices or vec is None:
            failed.append({
                "source_id":   chunk["source_id"],
                "chunk_index": chunk["chunk_index"],
                "chunk_type":  chunk["chunk_type"],
                "reason":      "embedding_failed",
            })
            continue

        embedded.append({
            **chunk,                          # all original fields preserved
            "embedding":       vec,           # the vector itself
            "embedding_model": model_name,    # traceability: which model produced it
            "embedding_dim":   embedding_dim, # sanity check field for DB schema
            "e5_prefix_used":  E5_DOC_PREFIX, # document prefix used at embed time
            "normalized":      NORMALIZE,     # was cosine normalization applied
            "embedded_at":     ts,            # UTC timestamp
        })

    return embedded, failed


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()

    # 1. Load chunks
    log.info(f"Loading chunks from {INPUT_PATH}")
    with open(INPUT_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    log.info(f"Loaded {len(chunks):,} chunks")

    # Log chunk type breakdown for visibility
    from collections import Counter
    type_counts = Counter(c["chunk_type"] for c in chunks)
    log.info(f"Chunk types: {dict(type_counts)}")

    # 2. Load model
    model = load_model(MODEL_NAME)
    embedding_dim = model.get_sentence_embedding_dimension()

    # 3. Prepare texts with E5 prefix
    texts = prepare_texts(chunks)
    log.info(f"Sample prefixed text: {texts[0][:120]}...")

    # 4. Embed
    vectors, failed_indices = embed_in_batches(model, texts, BATCH_SIZE, NORMALIZE)
    failed_set = set(failed_indices)

    # 5. Attach embeddings + metadata
    embedded, failed = attach_embeddings(
        chunks, vectors, failed_set, MODEL_NAME, embedding_dim
    )

    # 6. Save embedded chunks
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(embedded, f, ensure_ascii=False)  # no indent — keeps file smaller
    log.info(f"Saved {len(embedded):,} embedded chunks → {OUTPUT_PATH}")

    # 7. Save failures if any
    if failed:
        with open(FAILURE_PATH, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        log.warning(f"Saved {len(failed):,} failures → {FAILURE_PATH}")
    else:
        log.info("No failures — all chunks embedded successfully")

    # 8. Summary
    elapsed = time.time() - t_start
    log.info("─── Embedding Summary ───────────────────────────────")
    log.info(f"  Total input chunks : {len(chunks):,}")
    log.info(f"  Successfully embedded: {len(embedded):,}")
    log.info(f"  Failed             : {len(failed):,}")
    log.info(f"  Embedding model    : {MODEL_NAME}")
    log.info(f"  Embedding dim      : {embedding_dim}")
    log.info(f"  Normalized         : {NORMALIZE}")
    log.info(f"  Time elapsed       : {elapsed:.1f}s")
    log.info(f"  Output             : {OUTPUT_PATH}")
    log.info("─────────────────────────────────────────────────────")

    # 9. Spot-check first embedded chunk
    if embedded:
        sample = embedded[0]
        log.info("─── First chunk spot-check ──────────────────────────")
        log.info(f"  source_id      : {sample['source_id']}")
        log.info(f"  chunk_type     : {sample['chunk_type']}")
        log.info(f"  embedding_dim  : {sample['embedding_dim']}")
        log.info(f"  vector[:5]     : {[round(v, 6) for v in sample['embedding'][:5]]}")
        log.info(f"  vector norm    : {round(sum(v**2 for v in sample['embedding'])**0.5, 6)}")
        log.info("─────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
