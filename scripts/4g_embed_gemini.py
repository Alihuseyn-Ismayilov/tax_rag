"""
4g_embed_gemini.py
------------------
Alternative to 4_embed.py + 5_db.py: embeds the chunks with the Gemini API
(gemini-embedding-001) and writes them to a separate ChromaDB index.

With API embeddings the web app needs no torch / sentence-transformers and
runs in ~300 MB of RAM, so it fits small free hosting (Heroku, Azure B1s).

Input  : ../data/processed/chunks_simple.json
Cache  : ../data/processed/chunks_embedded_gemini.json   (resumable)
Output : ../data/db/chroma_gemini/                       (collection taxes_az_qa)

Run from the scripts/ folder:
    python 4g_embed_gemini.py

Safe to stop and re-run: chunks already in the cache are not embedded again.
The free Gemini tier is rate limited, so a full run can take 30-60 minutes;
on HTTP 429 the script waits and retries.

Names and e-mail addresses of the askers are NOT stored in this index.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_PATH      = Path("../data/processed/chunks_simple.json")
CACHE_PATH      = Path("../data/processed/chunks_embedded_gemini.json")
DB_PATH         = Path("../data/db/chroma_gemini")
COLLECTION_NAME = "taxes_az_qa"

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM   = 768      # 768 / 1536 / 3072; smaller dims must be normalized by hand
BATCH_SIZE  = 50       # texts per API request (max 100)
MAX_WAIT    = 120      # seconds, cap for the 429 back-off

METADATA_FIELDS = [
    "source_id", "source_url", "chunk_index", "total_chunks", "chunk_type",
    "question", "answer", "answer_date", "read_count", "average_rate",
    "rate_count", "question_len", "answer_len", "combined_len",
]


def chunk_id(c: dict) -> str:
    return f"src{c['source_id']}_c{c['chunk_index']}"


def normalize(vecs: list[list[float]]) -> list[list[float]]:
    arr = np.asarray(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    return arr.tolist()


def embed_batch(client: genai.Client, texts: list[str]) -> list[list[float]]:
    wait = 5
    while True:
        try:
            resp = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBED_DIM,
                ),
            )
            return normalize([e.values for e in resp.embeddings])
        except (errors.ClientError, errors.ServerError) as e:
            retryable = isinstance(e, errors.ServerError) or "429" in str(e) \
                or "RESOURCE_EXHAUSTED" in str(e)
            if not retryable:
                raise
            if "PerDay" in str(e):
                raise SystemExit(
                    "Daily embedding quota used up (free tier: 1000 texts/day). "
                    "Progress is cached; run the script again after the quota resets."
                )
            log.warning(f"Rate limit / server error, waiting {wait}s: {str(e)[:120]}")
            time.sleep(wait)
            wait = min(wait * 2, MAX_WAIT)


def main() -> None:
    load_dotenv(Path("../.env"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not set (../.env)")
    client = genai.Client(api_key=api_key)

    chunks = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    log.info(f"Loaded {len(chunks):,} chunks")

    cache: dict[str, list[float]] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        log.info(f"Cache: {len(cache):,} chunks already embedded")

    todo = [c for c in chunks if chunk_id(c) not in cache]
    log.info(f"To embed: {len(todo):,}")

    t0 = time.time()
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        vecs = embed_batch(client, [c["chunk_text"] for c in batch])
        for c, v in zip(batch, vecs):
            cache[chunk_id(c)] = v
        CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
        log.info(f"Embedded {min(i + BATCH_SIZE, len(todo)):,}/{len(todo):,} "
                 f"({time.time() - t0:.0f}s)")

    # ── Build the ChromaDB index ──────────────────────────────────────────────
    DB_PATH.mkdir(parents=True, exist_ok=True)
    db = chromadb.PersistentClient(path=str(DB_PATH))
    try:
        db.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    col = db.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    ts = datetime.now(timezone.utc).isoformat()
    unique = {chunk_id(c): c for c in chunks}       # guard against duplicate ids
    ids = list(unique)
    for i in range(0, len(ids), 500):
        part = ids[i : i + 500]
        col.add(
            ids=part,
            embeddings=[cache[k] for k in part],
            documents=[unique[k]["chunk_text"] for k in part],
            metadatas=[
                {**{f: unique[k][f] for f in METADATA_FIELDS},
                 "embedding_model": EMBED_MODEL,
                 "embedding_dim": EMBED_DIM,
                 "embedded_at": ts}
                for k in part
            ],
        )
    log.info(f"Index ready: {col.count():,} docs → {DB_PATH}")


if __name__ == "__main__":
    main()
