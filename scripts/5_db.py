"""
5_db.py
-------
Creates a ChromaDB vector database from embedded chunks and provides
helper functions for querying — used by the chatbot in 6_chatbot.py.

Input  : ../data/processed/chunks_embedded.json
Output : ../data/db/chroma/   (persistent ChromaDB directory)

Scalability notes
-----------------
- Uses upsert (not add) — safe to re-run. If you re-embed with a new model
  or add long chunks later, just run this file again. Existing records are
  updated, new ones are inserted. No duplicates.
- chunk_type field ("simple" | "paragraph") is stored in metadata so the
  chatbot can filter or weight by type if needed.
- Collection name is a config constant — swap it if you want separate
  collections per language or domain in the future.

ChromaDB distance metric
-------------------------
Using cosine similarity (hnsw:space = cosine). Our embeddings are L2
normalized (normalized=True in 4_embed.py), so cosine distance and dot
product are equivalent. Lower distance = more similar.
Score interpretation: 0.0 = identical, 2.0 = opposite.
Typical good match: distance < 0.3
"""

import json
import logging
import time
from pathlib import Path

import chromadb
from tqdm import tqdm

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_PATH      = Path("../data/processed/chunks_embedded.json")
DB_PATH         = Path("../data/db/chroma")
COLLECTION_NAME = "taxes_az_qa"

# How many chunks to upsert per batch — ChromaDB handles large batches fine
# but 500 is a safe default for memory
BATCH_SIZE = 500


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_chunks(path: Path) -> list[dict]:
    log.info(f"Loading embedded chunks from {path}")
    with open(path, encoding="utf-8") as f:
        chunks = json.load(f)
    log.info(f"Loaded {len(chunks):,} chunks")
    return chunks


def get_or_create_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """
    Get existing collection or create a new one.
    cosine distance is correct here because embeddings were L2-normalized
    in 4_embed.py (normalized=True).
    """
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    log.info(
        f"Collection '{COLLECTION_NAME}' ready — "
        f"existing docs: {collection.count():,}"
    )
    return collection


def build_record(chunk: dict, idx: int) -> tuple[str, list[float], str, dict]:
    """
    Extract the 4 components ChromaDB needs for each record:
      - id         : unique string identifier
      - embedding  : the vector
      - document   : the text that was embedded (used for display/debug)
      - metadata   : all filterable/retrievable fields (no embedding, no chunk_text)

    ID format: "src{source_id}_c{chunk_index}"
    Example  : "src10826_c0" for source_id=10826, chunk_index=0
    This format is:
      - Unique across simple AND future paragraph chunks
      - Human-readable for debugging
      - Stable across re-runs (same chunk always gets same ID → upsert works)
    """
    doc_id    = f"src{chunk['source_id']}_c{chunk['chunk_index']}"
    embedding = chunk["embedding"]
    document  = chunk["chunk_text"]   # what was embedded — stored for reference

    metadata  = {
        # ── Identity ──────────────────────────────────────────────────────
        "source_id":       chunk["source_id"],
        "source_url":      chunk["source_url"],
        "chunk_index":     chunk["chunk_index"],
        "total_chunks":    chunk["total_chunks"],
        "chunk_type":      chunk["chunk_type"],       # simple | paragraph

        # ── Content (stored for chatbot to return without re-reading JSON) ─
        "question":        chunk["question"],
        "answer":          chunk["answer"],

        # ── Quality signals ────────────────────────────────────────────────
        "answer_date":     chunk["answer_date"],
        "read_count":      chunk["read_count"],
        "average_rate":    chunk["average_rate"],
        "rate_count":      chunk["rate_count"],

        # ── Length info ────────────────────────────────────────────────────
        "question_len":    chunk["question_len"],
        "answer_len":      chunk["answer_len"],
        "combined_len":    chunk["combined_len"],

        # ── Embedding audit ────────────────────────────────────────────────
        "embedding_model": chunk["embedding_model"],
        "embedding_dim":   chunk["embedding_dim"],
        "embedded_at":     chunk["embedded_at"],
    }

    return doc_id, embedding, document, metadata


def upsert_chunks(collection: chromadb.Collection, chunks: list[dict]) -> int:
    """
    Upsert all chunks in batches with progress bar.
    Returns count of successfully upserted chunks.
    """
    batches = [chunks[i : i + BATCH_SIZE] for i in range(0, len(chunks), BATCH_SIZE)]
    log.info(f"Upserting {len(chunks):,} chunks in {len(batches):,} batches")

    total_upserted = 0

    for batch_num, batch in enumerate(tqdm(batches, desc="Inserting", unit="batch")):
        ids, embeddings, documents, metadatas = [], [], [], []

        for idx, chunk in enumerate(batch):
            global_idx = batch_num * BATCH_SIZE + idx
            doc_id, embedding, document, metadata = build_record(chunk, global_idx)
            ids.append(doc_id)
            embeddings.append(embedding)
            documents.append(document)
            metadatas.append(metadata)

        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            total_upserted += len(batch)
        except Exception as e:
            log.error(f"Batch {batch_num} failed: {e}")

    return total_upserted


def verify_collection(collection: chromadb.Collection) -> None:
    """Spot-check the collection after insertion."""
    count = collection.count()
    log.info(f"Collection count after upsert: {count:,}")

    # Fetch first record to verify structure
    sample = collection.get(limit=1, include=["documents", "metadatas", "embeddings"])
    if sample["ids"]:
        log.info("── Sample record ─────────────────────────────────────")
        log.info(f"  id            : {sample['ids'][0]}")
        log.info(f"  document[:80] : {sample['documents'][0][:80]}")
        meta = sample["metadatas"][0]
        log.info(f"  source_id     : {meta['source_id']}")
        log.info(f"  chunk_type    : {meta['chunk_type']}")
        log.info(f"  answer_date   : {meta['answer_date']}")
        log.info(f"  embedding dim : {len(sample['embeddings'][0])}")
        log.info("──────────────────────────────────────────────────────")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()

    # 1. Load embedded chunks
    chunks = load_chunks(INPUT_PATH)

    # 2. Validate — every chunk must have an embedding
    missing = [i for i, c in enumerate(chunks) if not c.get("embedding")]
    if missing:
        log.warning(f"{len(missing)} chunks have no embedding — they will be skipped")
        chunks = [c for c in chunks if c.get("embedding")]
        log.info(f"Proceeding with {len(chunks):,} chunks")

    # 3. Connect to ChromaDB
    DB_PATH.mkdir(parents=True, exist_ok=True)
    log.info(f"Connecting to ChromaDB at {DB_PATH}")
    client = chromadb.PersistentClient(path=str(DB_PATH))

    # 4. Get or create collection
    collection = get_or_create_collection(client)

    # 5. Upsert all chunks
    upserted = upsert_chunks(collection, chunks)

    # 6. Verify
    verify_collection(collection)

    # 7. Summary
    elapsed = time.time() - t_start
    log.info("═" * 54)
    log.info("  DATABASE READY")
    log.info("═" * 54)
    log.info(f"  Input chunks   : {len(chunks):,}")
    log.info(f"  Upserted       : {upserted:,}")
    log.info(f"  Collection     : {COLLECTION_NAME}")
    log.info(f"  DB path        : {DB_PATH.resolve()}")
    log.info(f"  Time elapsed   : {elapsed:.1f}s")
    log.info("═" * 54)
    log.info("Next step → 6_chatbot.py")


if __name__ == "__main__":
    main()
