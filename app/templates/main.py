"""
7_app.py
--------
FastAPI web frontend for the taxes.gov.az RAG chatbot.

Run:
    uvicorn 7_app:app --reload --port 8000

Then open: http://localhost:8000

Structure:
    7_app.py              ← this file (FastAPI routes)
    templates/index.html  ← Jinja2 chat UI
    static/style.css      ← styles
    static/app.js         ← frontend logic

Routes:
    GET  /          → chat UI page
    POST /ask       → query endpoint (JSON in, JSON out)
    GET  /history   → last N queries from query_log.jsonl
    GET  /health    → DB + model status check
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# ── Bootstrap ─────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH         = Path("../../data/db/chroma")
COLLECTION_NAME = "taxes_az_qa"
LOG_PATH        = Path("../../data/logs/query_log.jsonl")

EMBED_MODEL      = "intfloat/multilingual-e5-large"
E5_QUERY_PREFIX  = "query: "

GEMINI_MODEL      = "gemini-2.5-flash"
TOP_K             = 5
DISTANCE_THRESHOLD = 0.5
MAX_OUTPUT_TOKENS  = 1024
TEMPERATURE        = 0.2
THINKING_BUDGET    = 0

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

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Vergi Chatbotu", docs_url=None, redoc_url=None)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── Global resources (loaded once at startup) ─────────────────────────────────
embed_model: SentenceTransformer = None
collection: chromadb.Collection  = None
gemini_client: genai.Client      = None


@app.on_event("startup")
async def startup():
    global embed_model, collection, gemini_client

    log.info("Loading embedding model...")
    embed_model = SentenceTransformer(EMBED_MODEL)
    log.info(f"Embedding model ready — dim: {embed_model.get_sentence_embedding_dimension()}")

    log.info("Connecting to ChromaDB...")
    db_client  = chromadb.PersistentClient(path=str(DB_PATH))
    collection = db_client.get_collection(name=COLLECTION_NAME)
    log.info(f"Collection '{COLLECTION_NAME}' — {collection.count():,} docs")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set — add it to .env file")
    gemini_client = genai.Client(api_key=api_key)
    log.info(f"Gemini client ready — model: {GEMINI_MODEL}")

    log.info("All resources loaded. Ready at http://localhost:8000")


# ── Request / Response models ─────────────────────────────────────────────────
class AskRequest(BaseModel):
    query: str


class Source(BaseModel):
    rank:        int
    source_id:   int
    similarity:  float
    answer_date: str
    question:    str
    answer:      str
    source_url:  str


class AskResponse(BaseModel):
    query:        str
    answer:       str
    sources:      list[Source]
    retrieval_ms: float
    llm_ms:       float


# ── Pipeline functions ────────────────────────────────────────────────────────
def embed_query(query: str) -> list[float]:
    vec = embed_model.encode(
        [E5_QUERY_PREFIX + query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec[0].tolist()


def search(query: str) -> list[dict]:
    query_vec = embed_query(query)
    raw = collection.query(
        query_embeddings=[query_vec],
        n_results=TOP_K,
        include=["metadatas", "distances"],
    )
    results = []
    for i in range(len(raw["ids"][0])):
        distance = raw["distances"][0][i]
        if distance > DISTANCE_THRESHOLD:
            continue
        meta = raw["metadatas"][0][i]
        results.append({
            "rank":        i + 1,
            "distance":    round(distance, 4),
            "similarity":  round(1 - distance / 2, 4),
            "source_id":   meta["source_id"],
            "chunk_type":  meta["chunk_type"],
            "answer_date": meta["answer_date"],
            "read_count":  meta["read_count"],
            "question":    meta["question"],
            "answer":      meta["answer"],
            "source_url":  meta["source_url"],
        })
    return results


def build_context(results: list[dict]) -> str:
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


def call_llm(context: str, query: str, retries: int = 3) -> str:
    if context:
        user_text = f"Kontekst məlumatları:\n{context}\n\nSualım: {query}"
    else:
        user_text = (
            f"Kontekst məlumatları: Heç bir uyğun nəticə tapılmadı.\n\n"
            f"Sualım: {query}"
        )

    messages = [types.Content(role="user", parts=[types.Part(text=user_text)])]
    config   = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
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
            if "429" in str(e) or "quota" in str(e).lower():
                wait = 2 ** attempt
                log.warning(f"Rate limit (attempt {attempt}/{retries}), waiting {wait}s...")
                time.sleep(wait)
            else:
                raise HTTPException(status_code=400, detail=str(e))
        except errors.ServerError as e:
            wait = 2 ** attempt
            log.warning(f"Server error (attempt {attempt}/{retries}), waiting {wait}s...")
            time.sleep(wait)

    raise HTTPException(status_code=503, detail="LLM unavailable after retries")


def log_query(query, results, answer_text, retrieval_ms, llm_ms):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":             datetime.now(timezone.utc).isoformat(),
        "query":          query,
        "n_results":      len(results),
        "top_distances":  [r["distance"] for r in results[:3]],
        "source_ids":     [r["source_id"] for r in results],
        "answer_preview": answer_text[:200],
        "retrieval_ms":   round(retrieval_ms),
        "llm_ms":         round(llm_ms),
        "model":          GEMINI_MODEL,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    # Retrieve
    t0      = time.time()
    results = search(query)
    retrieval_ms = (time.time() - t0) * 1000

    # Generate
    context = build_context(results)
    t1      = time.time()
    answer  = call_llm(context, query)
    llm_ms  = (time.time() - t1) * 1000

    # Log
    log_query(query, results, answer, retrieval_ms, llm_ms)

    log.info(
        f"[/ask] retrieval={retrieval_ms:.0f}ms "
        f"llm={llm_ms:.0f}ms "
        f"sources={len(results)}"
    )

    return AskResponse(
        query=query,
        answer=answer,
        sources=[Source(**r) for r in results],
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
    )


@app.get("/history")
async def history(n: int = 20):
    """Return last n queries from the log file."""
    if not LOG_PATH.exists():
        return JSONResponse(content={"queries": []})

    with open(LOG_PATH, encoding="utf-8") as f:
        lines = [l for l in f.readlines() if l.strip()]

    last_n = lines[-n:]
    entries = [json.loads(l) for l in last_n]
    entries.reverse()  # newest first
    return JSONResponse(content={"queries": entries})


@app.get("/health")
async def health():
    """Quick status check for all components."""
    status = {
        "embed_model": embed_model is not None,
        "db":          collection is not None,
        "db_docs":     collection.count() if collection else 0,
        "llm":         gemini_client is not None,
        "model":       GEMINI_MODEL,
        "ts":          datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(content=status)