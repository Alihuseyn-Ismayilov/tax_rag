"""
6_chatbot.py
------------
RAG chatbot for taxes.gov.az Q&A using:
  - ChromaDB        : vector retrieval
  - multilingual-e5-large : query embedding
  - Gemini 2.5 Flash      : answer generation

Usage:
    python 6_chatbot.py

Setup:
    pip install google-genai sentence-transformers chromadb
    set GEMINI_API_KEY=your_key_here   (Windows)
    export GEMINI_API_KEY=your_key_here (Mac/Linux)

Pipeline per query:
    user query
        → embed_query()       — "query: " + e5-large → 1024-dim vector
        → search()            — ChromaDB cosine search → top-k chunks
        → distance filter     — drop chunks above threshold
        → build_context()     — format retrieved Q&A pairs
        → build_messages()    — system prompt + context + user question
        → call_llm()          — Gemini 2.5 Flash API
        → log_query()         — append to query_log.jsonl
        → return answer + sources
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from google import genai
from google.genai import errors, types
from sentence_transformers import SentenceTransformer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# Paths — must match 4_embed.py and 5_db.py
DB_PATH         = Path("../data/db/chroma")
COLLECTION_NAME = "taxes_az_qa"
LOG_PATH        = Path("../data/logs/query_log.jsonl")

# Embedding model — must be identical to the one used in 4_embed.py
EMBED_MODEL    = "intfloat/multilingual-e5-large"
E5_QUERY_PREFIX = "query: "   # IMPORTANT: passage: was used at index time

# Gemini config
GEMINI_MODEL   = "gemini-2.5-flash"

# Retrieval config
TOP_K               = 5     # how many chunks to retrieve
DISTANCE_THRESHOLD  = 0.5   # cosine distance — drop results above this
                             # 0.0 = identical, 2.0 = opposite
                             # good match is typically < 0.35

# LLM config
MAX_OUTPUT_TOKENS   = 1024
TEMPERATURE         = 0.2   # low = more factual, less creative — right for tax Q&A
THINKING_BUDGET     = 0     # 0 = disable thinking mode for speed
                             # increase to 1024+ for complex multi-step questions

# System prompt — instructs LLM behaviour strictly
SYSTEM_PROMPT = """Siz Azərbaycan Respublikasının Dövlət Vergi Xidmətinin rəsmi \
saytı olan taxes.gov.az-ın sual-cavab məlumat bazasına əsaslanan köməkçi \
chatbotsunuz.

Qaydalar:
1. Yalnız Azərbaycan dilində cavab verin.
2. Cavabınızı YALNIZ verilmiş kontekst məlumatlarına əsaslandırın.
3. Kontekstdə cavab yoxdursa — "Bu sual barədə məlumat bazamda məlumat tapılmadı." \
deyin. Heç vaxt uydurmayın.
4. Mənbə nömrəsinə istinad edin (məsələn: [Mənbə 1]).
5. Vergi Məcəlləsinə istinadlar varsa, onları cavabda qoruyun.
6. Qısa və aydın cavab verin."""


# ── Initialise resources (runs once at startup) ───────────────────────────────

def init_embed_model() -> SentenceTransformer:
    log.info(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    log.info(f"Embedding model ready — dim: {model.get_sentence_embedding_dimension()}")
    return model


def init_db() -> chromadb.Collection:
    log.info(f"Connecting to ChromaDB at {DB_PATH}")
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_collection(name=COLLECTION_NAME)
    log.info(f"Collection '{COLLECTION_NAME}' — {collection.count():,} docs")
    return collection


def init_gemini() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set.\n"
            "  Windows : set GEMINI_API_KEY=your_key\n"
            "  Mac/Linux: export GEMINI_API_KEY=your_key"
        )
    client = genai.Client(api_key=api_key)
    log.info(f"Gemini client ready — model: {GEMINI_MODEL}")
    return client


# ── Core pipeline functions ───────────────────────────────────────────────────

def embed_query(query: str, embed_model: SentenceTransformer) -> list[float]:
    """
    Embed user query with E5 query prefix.
    Must use 'query: ' prefix — 'passage: ' was used at index time.
    Asymmetric prefixes are what makes E5 good at retrieval.
    """
    prefixed = E5_QUERY_PREFIX + query
    vec = embed_model.encode(
        [prefixed],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec[0].tolist()


def search(
    query: str,
    embed_model: SentenceTransformer,
    collection: chromadb.Collection,
    top_k: int = TOP_K,
    threshold: float = DISTANCE_THRESHOLD,
) -> list[dict]:
    """
    Embed query, search ChromaDB, filter by distance threshold.
    Returns list of result dicts sorted by relevance.
    Empty list means nothing relevant found — LLM will say so.
    """
    query_vec = embed_query(query, embed_model)

    raw = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        include=["metadatas", "distances", "documents"],
    )

    results = []
    for i in range(len(raw["ids"][0])):
        distance = raw["distances"][0][i]
        if distance > threshold:
            continue  # too far — not relevant

        meta = raw["metadatas"][0][i]
        results.append({
            "rank":        i + 1,
            "id":          raw["ids"][0][i],
            "distance":    round(distance, 4),
            "similarity":  round(1 - distance / 2, 4),  # 1.0=identical, 0.0=opposite
            "source_id":   meta["source_id"],
            "chunk_type":  meta["chunk_type"],
            "answer_date": meta["answer_date"],
            "read_count":  meta["read_count"],
            "question":    meta["question"],
            "answer":      meta["answer"],
            "source_url":  meta["source_url"],
        })

    log.info(
        f"Search: {len(results)}/{top_k} results passed threshold "
        f"(threshold={threshold})"
    )
    return results


def build_context(results: list[dict]) -> str:
    """
    Format retrieved chunks into a clean context block for the LLM.
    Each source is numbered so the LLM can cite them.
    """
    if not results:
        return ""

    parts = []
    for r in results:
        parts.append(
            f"[Mənbə {r['rank']}] (uyğunluq: {r['similarity']:.0%})\n"
            f"Sual: {r['question'].strip()}\n"
            f"Cavab: {r['answer'].strip()}"
        )

    return "\n\n".join(parts)


def build_messages(user_query: str, context: str) -> list[types.Content]:
    """
    Build the messages list for Gemini API.
    Context is injected into the user message — Gemini 2.5 Flash
    uses system_instruction separately in GenerateContentConfig.
    """
    if context:
        user_text = f"Kontekst məlumatları:\n{context}\n\nSualım: {user_query}"
    else:
        user_text = (
            f"Kontekst məlumatları: Heç bir uyğun nəticə tapılmadı.\n\n"
            f"Sualım: {user_query}"
        )

    return [
        types.Content(
            role="user",
            parts=[types.Part(text=user_text)],
        )
    ]


def call_llm(
    messages: list[types.Content],
    gemini_client: genai.Client,
    retries: int = 3,
) -> str:
    """
    Call Gemini 2.5 Flash with retry on transient errors.
    thinking_budget=0 disables chain-of-thought for speed.
    Increase thinking_budget for harder questions if needed.
    """
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=types.ThinkingConfig(
            thinking_budget=THINKING_BUDGET,
        ),
    )

    for attempt in range(1, retries + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=messages,
                config=config,
            )
            return response.text

        except errors.ClientError as e:
            # 429 = rate limit — wait and retry
            if "429" in str(e) or "quota" in str(e).lower():
                wait = 2 ** attempt  # 2s, 4s, 8s
                log.warning(f"Rate limit hit (attempt {attempt}/{retries}). Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise  # other client errors (bad key, bad request) — don't retry

        except errors.ServerError as e:
            wait = 2 ** attempt
            log.warning(f"Server error (attempt {attempt}/{retries}): {e}. Waiting {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"LLM call failed after {retries} retries.")


def log_query(
    query: str,
    results: list[dict],
    answer: str,
    retrieval_ms: float,
    llm_ms: float,
) -> None:
    """
    Append one line to query_log.jsonl for every query.
    JSONL = one JSON object per line — easy to load with pandas later.
    Useful for: spotting bad retrievals, tuning threshold, usage stats.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts":            datetime.now(timezone.utc).isoformat(),
        "query":         query,
        "n_results":     len(results),
        "top_distances": [r["distance"] for r in results[:3]],
        "source_ids":    [r["source_id"] for r in results],
        "answer_preview": answer[:200],
        "retrieval_ms":  round(retrieval_ms),
        "llm_ms":        round(llm_ms),
        "model":         GEMINI_MODEL,
    }

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Main answer function ──────────────────────────────────────────────────────

def answer(
    query: str,
    embed_model: SentenceTransformer,
    collection: chromadb.Collection,
    gemini_client: genai.Client,
) -> dict:
    """
    Full RAG pipeline: query → retrieve → generate → return.

    Returns dict with:
        answer      : str   — LLM response in Azerbaijani
        sources     : list  — retrieved chunk metadata
        retrieval_ms: float — time for embed + search
        llm_ms      : float — time for LLM call
        query       : str   — original query
    """
    # 1. Retrieve
    t0 = time.time()
    results = search(query, embed_model, collection)
    retrieval_ms = (time.time() - t0) * 1000

    # 2. Build prompt
    context  = build_context(results)
    messages = build_messages(query, context)

    # 3. Generate
    t1 = time.time()
    llm_answer = call_llm(messages, gemini_client)
    llm_ms = (time.time() - t1) * 1000

    # 4. Log
    log_query(query, results, llm_answer, retrieval_ms, llm_ms)

    log.info(
        f"Done — retrieval: {retrieval_ms:.0f}ms, "
        f"LLM: {llm_ms:.0f}ms, "
        f"sources: {len(results)}"
    )

    return {
        "query":        query,
        "answer":       llm_answer,
        "sources":      results,
        "retrieval_ms": retrieval_ms,
        "llm_ms":       llm_ms,
    }


# ── CLI interactive loop ──────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    print()
    print("─" * 60)
    print("Cavab:")
    print(result["answer"])
    print()
    if result["sources"]:
        print("Mənbələr:")
        for s in result["sources"]:
            print(
                f"  [{s['rank']}] source_id={s['source_id']} | "
                f"uyğunluq={s['similarity']:.0%} | "
                f"tarix={s['answer_date']}"
            )
    print(f"\n⏱  Retrieval: {result['retrieval_ms']:.0f}ms | "
          f"LLM: {result['llm_ms']:.0f}ms")
    print("─" * 60)


def main():
    # Initialise all resources once
    embed_model   = init_embed_model()
    collection    = init_db()
    gemini_client = init_gemini()

    print()
    print("═" * 60)
    print("  taxes.gov.az Vergi Chatbotu")
    print("  Çıxmaq üçün 'çıx' və ya 'exit' yazın")
    print("═" * 60)

    while True:
        print()
        try:
            query = input("Sualınızı yazın: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBağlandı.")
            break

        if not query:
            continue

        if query.lower() in ("çıx", "exit", "quit", "q"):
            print("Bağlandı.")
            break

        try:
            result = answer(query, embed_model, collection, gemini_client)
            print_result(result)
        except Exception as e:
            log.error(f"Query failed: {e}")
            print(f"Xəta baş verdi: {e}")


if __name__ == "__main__":
    main()
