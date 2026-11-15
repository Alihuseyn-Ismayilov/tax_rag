# Vergi Köməkçisi — tax Q&A assistant for Azerbaijan

A retrieval-augmented (RAG) chatbot that answers questions about Azerbaijani taxes
using the public question-and-answer archive of the State Tax Service
([taxes.gov.az → Suallar və cavablar](https://www.taxes.gov.az/az/page/suallar-ve-cavablar)).

The model does not answer from memory. For every question it first finds the most
similar official answers in the archive, then writes a reply based only on them and
cites each one as `[Mənbə N]`. If nothing relevant is found, it says so instead of
guessing.

> **Research purpose only.** This is not an official service of the State Tax Service,
> and its answers are not legal or tax advice. Always check the linked source.

![Asking a question: retrieval, answer with numbered sources, and the project panel](docs/screenshots/demo.gif)

<sub>Recorded from the running app with the real index and Gemini, no edits to the answer.</sub>

| Start screen | Answer with sources |
|---|---|
| ![Start screen with topic cards](docs/screenshots/home.png) | ![Answer with footnotes; hovering footnote 1 highlights source 1](docs/screenshots/answer.png) |
| **Dark theme** | **Project panel** |
| ![The same answer in the dark theme](docs/screenshots/answer-dark.png) | ![Info panel with model settings and the pipeline](docs/screenshots/about.png) |

<p align="center">
  <img src="docs/screenshots/mobile-home.png" alt="Start screen on a phone" width="300">
</p>

---

## How it works

```
                 ┌──────────────────── built once ────────────────────┐
 taxes.gov.az ─► scrape ─► clean ─► chunk ─► embed ("passage:") ─► ChromaDB
                                                                    │
                 ┌──────────────────── every question ──────────────┼─┐
 question ─► embed ("query:") ─► cosine search, top-5, distance ≤ 0.5 ◄┘ │
          ─► number hits as [Mənbə 1..n] ─► Gemini 2.5 Flash ─► answer + sources
                 └──────────────────────────────────────────────────────┘
```

| Stage | What happens | Where |
|---|---|---|
| Scrape | Pages of the Q&A section are fetched with `requests` + BeautifulSoup: asker name, e-mail, ID, question, answer, date, read count, rating. | `scripts/scraper.ipynb` |
| Clean | Records without an answer are dropped, text is trimmed, ID and metadata are parsed. 5,772 → 5,771 records. | `scripts/cleaning.ipynb` |
| Chunk | Each record becomes one chunk `Sual: … / Cavab: …` if question + answer ≤ 1,500 characters. 3,549 chunks. | `scripts/3_chunk_simple.py` |
| Embed | `intfloat/multilingual-e5-large` (1024-dim), `passage:` prefix, L2-normalised. | `scripts/4_embed.py` |
| Index | ChromaDB persistent collection `taxes_az_qa`, HNSW with cosine distance. | `scripts/5_db.py` |
| Answer | Query embedded with `query:` prefix → top-5 → drop hits with distance > 0.5 → context → Gemini. | `app/main.py`, `scripts/6_chatbot.py` |

Generation settings: `gemini-2.5-flash`, temperature 0.2, max 1,024 output tokens,
thinking disabled. The system prompt (Azerbaijani) tells the model to answer only in
Azerbaijani, only from the context, to cite sources and to keep Tax Code references.

The web UI has the same diagram under **Layihə haqqında** (top right), filled with the
live settings from the server:

<p align="center">
  <img src="docs/screenshots/about-pipeline.png" alt="Pipeline diagram in the project panel" width="720">
</p>

---

## Quick start

The ChromaDB index is committed in `data/db/chroma`, so you can run the app without
rebuilding anything. It currently holds 3,558 vectors: 9 more than the current
`chunks_embedded.json` (3,549), left over from an earlier build. Rebuilding the index
(below) brings the two back in sync.

**Requirements:** Python 3.11, a [Gemini API key](https://aistudio.google.com/apikey),
about 2.2 GB free disk for the embedding model (downloaded on first start).

```bash
git clone https://github.com/Alihuseyn-Ismayilov/tax_rag.git
cd tax_rag
python -m venv venv
```

Activate the environment — Windows:

```bash
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` pins `torch==2.7.1+cu118` (CUDA 11.8). On a machine without an
NVIDIA GPU, install the CPU build first and then the rest:

```bash
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

Run the web app. Paths in the code are relative (`../data/...`), so start it **from the
`app/` folder**:

```bash
cd app
uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>. The first start takes a while because
`multilingual-e5-large` is downloaded and loaded.

### Command-line chatbot

The same pipeline without the UI, from the `scripts/` folder:

```bash
cd scripts
python 6_chatbot.py
```

---

## Web app

FastAPI backend + a plain HTML/CSS/JS frontend (no build step).

- Ask a question, or click one of the topic cards on the start screen.
- Each answer shows numbered footnotes. Hover or focus a footnote to highlight its
  source in the right column; click it to jump there. Every source links to the
  original answer on taxes.gov.az.
- **Son sorğular** (left) lists recent questions from the query log. Click one to put
  it back in the input.
- Clicking the **Vergi Köməkçisi** logo returns to the start screen.
- **Layihə haqqında** opens a panel with the model settings and the pipeline diagram.
- Works on phones (the sidebar becomes a drawer), follows the system light/dark theme,
  is keyboard-accessible and respects reduced-motion settings.

### API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/` | The chat page. |
| `POST` | `/ask` | Body `{"query": "..."}` → `answer`, `sources[]` (rank, similarity, question, answer, date, source URL…), `retrieval_ms`, `llm_ms`. |
| `GET` | `/history?n=20` | Last *n* entries of the query log, newest first. |
| `GET` | `/health` | Whether the embedding model, database and LLM client are loaded, plus document count. |
| `GET` | `/about` | Read-only settings for the info panel: models, embedding size, document count, top-k, threshold, temperature. No secrets. |

Example:

```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\": \"ƏDV qeydiyyatı üçün dövriyyə həddi nə qədərdir?\"}"
```

Every `/ask` call is appended to `data/logs/query_log.jsonl` (query, source IDs,
distances, answer preview, timings).

---

## Rebuilding the index

Only needed if you re-scrape or change chunking or the embedding model. Run the steps
in order from the `scripts/` folder:

1. `scraper.ipynb` — scrape the Q&A pages. It writes to `../output/scraped/raw_data.csv`;
   move the file to `data/scraped/raw_data.csv` (the path the next step reads).
2. `cleaning.ipynb` — writes `data/processed/clean_data.csv`.
3. `python 3_chunk_simple.py` — writes `data/processed/chunks_simple.json`.
4. `python 4_embed.py` — writes `data/processed/chunks_embedded.json` (GPU recommended).
5. `python 5_db.py` — loads the vectors into `data/db/chroma`.

If you change `EMBED_MODEL`, change it in `4_embed.py`, `6_chatbot.py` and
`app/main.py` together; queries and documents must use the same model.

---

## Project layout

```
tax_rag/
├── app/
│   ├── main.py              FastAPI app: retrieval, generation, API routes
│   ├── templates/index.html chat page
│   └── static/              style.css, app.js
├── scripts/
│   ├── scraper.ipynb        1. scrape taxes.gov.az
│   ├── cleaning.ipynb       2. clean
│   ├── 3_chunk_simple.py    3. chunk
│   ├── 4_embed.py           4. embed (+ .ipynb version)
│   ├── 5_db.py              5. build ChromaDB (+ .ipynb version)
│   ├── 6_chatbot.py         CLI chatbot (+ .ipynb version)
│   └── analyze_chunks.ipynb chunk-length analysis
├── data/
│   ├── scraped/             raw scrape (csv, xlsx)
│   ├── processed/           clean data, chunks, embeddings
│   ├── db/chroma/           vector index
│   └── logs/                query log (/ask appends here)
├── requirements.txt
└── .env                     GEMINI_API_KEY (git-ignored)
```

---

## Settings

All in the config block at the top of `app/main.py` (mirrored in `scripts/6_chatbot.py`):

| Setting | Value | Meaning |
|---|---|---|
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | Query embedding model; must match the one used for the index. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Answer model. |
| `TOP_K` | 5 | Chunks retrieved per question. |
| `DISTANCE_THRESHOLD` | 0.5 | Cosine distance cut-off; weaker matches are dropped. |
| `TEMPERATURE` | 0.2 | Low, for factual answers. |
| `MAX_OUTPUT_TOKENS` | 1024 | Answer length limit. |
| `THINKING_BUDGET` | 0 | Gemini thinking mode off, for speed. |

---

## Limitations

- **Only short records are indexed.** 3,549 of 5,771 records fit the 1,500-character
  limit. The longer ~2,200 answers are not searchable yet; a paragraph-level chunker
  (`3_chunk_long.py`) is planned but not written.
- **Snapshot data.** The archive reflects the site on the scrape date. Tax rules change;
  older answers may be outdated even when they match well.
- **Answers are only as good as retrieval.** If the right answer is not among the top 5,
  the model will say it found nothing, or answer from a weaker match.
- **The source data contains askers' names and e-mail addresses** as published on
  taxes.gov.az. Both are stored in the index metadata and returned by `/ask`, but the
  UI does not display them.
