"""
compare_embeddings.py
---------------------
Compares retrieval quality of the two indexes:
    e5     : ../data/db/chroma         (intfloat/multilingual-e5-large, local)
    gemini : ../data/db/chroma_gemini  (gemini-embedding-001, API)

Test 1 — paraphrases. N random archive questions are rewritten by Gemini as
short, informal user questions (different wording, same meaning). For each
paraphrase we check whether the original record is found: hit@1, hit@5, MRR.
The paraphrases are cached in ../data/eval/paraphrases.json so both runs and
later re-runs use the same test set.

Test 2 — real queries from ../data/logs/query_log.jsonl: top-3 questions from
each index side by side, plus how many top-5 sources the two indexes share.
Output: ../data/eval/compare_report.md

Run from scripts/ (needs sentence-transformers for the e5 side):
    python compare_embeddings.py [N]
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import chromadb
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

CHUNKS_PATH = Path("../data/processed/chunks_simple.json")
LOG_PATH    = Path("../data/logs/query_log.jsonl")
EVAL_DIR    = Path("../data/eval")
PARA_PATH   = EVAL_DIR / "paraphrases.json"
REPORT_PATH = EVAL_DIR / "compare_report.md"

GEN_MODEL   = "gemini-2.5-flash"
GEMINI_EMBED = "gemini-embedding-001"
GEMINI_DIM  = 768
E5_MODEL    = "intfloat/multilingual-e5-large"
TOP_K       = 5
SEED        = 42

OFF_TOPIC = [
    "Bakıda sabah hava necə olacaq?",
    "Plov necə bişirilir?",
    "Ən yaxşı futbol komandası hansıdır?",
    "Python-da siyahını necə sıralamaq olar?",
    "Bu gün hansı filmə baxım?",
    "Ayın Yerdən məsafəsi nə qədərdir?",
    "Pişiyim yemək yemir, nə etməliyəm?",
    "Gitara çalmağı necə öyrənim?",
    "İngilis dilində 'salam' necə deyilir?",
    "Qış tətilində hara səyahət edim?",
]

PARA_PROMPT ="""Aşağıda vergi sualları var. Hər birini adi istifadəçinin \
chatbota yazacağı kimi qısa (1 cümlə, 6-20 söz), sadə dildə yenidən yazın. \
Mənanı saxlayın, amma orijinal ifadələri köçürməyin, şəxsi detalları atın.
Yalnız JSON massivi qaytarın: [{"id": <id>, "q": "<yeni sual>"}, ...]

"""


def retry(fn, *a, **kw):
    wait = 5
    for _ in range(8):
        try:
            return fn(*a, **kw)
        except (errors.ClientError, errors.ServerError) as e:
            if isinstance(e, errors.ClientError) and "429" not in str(e) \
                    and "RESOURCE_EXHAUSTED" not in str(e):
                raise
            time.sleep(wait)
            wait = min(wait * 2, 120)
    raise RuntimeError("Gemini API kept failing")


def make_paraphrases(client, chunks, n):
    if PARA_PATH.exists():
        data = json.loads(PARA_PATH.read_text(encoding="utf-8"))
        if len(data) >= n:
            return data[:n]
    rnd = random.Random(SEED)
    sample = rnd.sample(chunks, n)
    out = []
    for i in range(0, n, 20):
        part = sample[i : i + 20]
        listing = "\n".join(
            json.dumps({"id": c["source_id"], "sual": c["question"][:700]},
                       ensure_ascii=False)
            for c in part
        )
        resp = retry(
            client.models.generate_content,
            model=GEN_MODEL,
            contents=PARA_PROMPT + listing,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        out += [{"source_id": int(x["id"]), "query": x["q"]}
                for x in json.loads(resp.text)]
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    PARA_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


class E5:
    name = "e5"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(E5_MODEL)
        self.col = chromadb.PersistentClient("../data/db/chroma").get_collection("taxes_az_qa")

    def embed(self, queries):
        return self.model.encode(["query: " + q for q in queries],
                                 normalize_embeddings=True).tolist()


class Gemini:
    name = "gemini"

    def __init__(self, client):
        self.client = client
        self.col = chromadb.PersistentClient("../data/db/chroma_gemini").get_collection("taxes_az_qa")

    def embed(self, queries):
        vecs = []
        for i in range(0, len(queries), 50):
            resp = retry(
                self.client.models.embed_content,
                model=GEMINI_EMBED,
                contents=queries[i : i + 50],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY",
                                                output_dimensionality=GEMINI_DIM),
            )
            arr = np.asarray([e.values for e in resp.embeddings], dtype=np.float32)
            vecs += (arr / np.linalg.norm(arr, axis=1, keepdims=True)).tolist()
        return vecs


def search(index, queries):
    vecs = index.embed(queries)
    res = index.col.query(query_embeddings=vecs, n_results=TOP_K,
                          include=["metadatas", "distances"])
    return [
        [(m["source_id"], d, m["question"]) for m, d in zip(ms, ds)]
        for ms, ds in zip(res["metadatas"], res["distances"])
    ]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    load_dotenv(Path("../.env"))
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))

    paras = make_paraphrases(client, chunks, n)
    log_q = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                q = json.loads(line)["query"].strip()
                if q and q not in log_q:
                    log_q.append(q)

    indexes = [E5(), Gemini(client)]
    lines = ["# e5 vs Gemini embeddings\n"]

    # ── Test 1 ────────────────────────────────────────────────────────────────
    lines.append(f"## Paraphrase test ({len(paras)} queries)\n")
    lines.append("| index | hit@1 | hit@5 | MRR | median top-1 distance |")
    lines.append("|---|---|---|---|---|")
    para_hits = {}
    for idx in indexes:
        res = search(idx, [p["query"] for p in paras])
        ranks = []
        for p, r in zip(paras, res):
            ids = [sid for sid, _, _ in r]
            ranks.append(ids.index(p["source_id"]) + 1 if p["source_id"] in ids else None)
        h1 = sum(r == 1 for r in ranks) / len(ranks)
        h5 = sum(r is not None for r in ranks) / len(ranks)
        mrr = sum(1 / r for r in ranks if r) / len(ranks)
        med = float(np.median([r[0][1] for r in res]))
        para_hits[idx.name] = ranks
        lines.append(f"| {idx.name} | {h1:.0%} | {h5:.0%} | {mrr:.3f} | {med:.3f} |")
    both = sum(a is not None and b is not None
               for a, b in zip(para_hits["e5"], para_hits["gemini"]))
    lines.append(f"\nBoth found within top-5: {both}/{len(paras)}\n")

    # ── Threshold calibration ─────────────────────────────────────────────────
    # Top-1 distance for paraphrases whose source was found (should pass the
    # threshold) vs off-topic questions (should be cut off).
    lines.append("## Threshold calibration (top-1 cosine distance)\n")
    lines.append("| index | on-topic hits: p10 / median / p90 | off-topic: min / median |")
    lines.append("|---|---|---|")
    for idx in indexes:
        on = search(idx, [p["query"] for p, r in zip(paras, para_hits[idx.name]) if r])
        off = search(idx, OFF_TOPIC)
        on_d = np.array([r[0][1] for r in on])
        off_d = np.array([r[0][1] for r in off])
        lines.append(
            f"| {idx.name} | {np.percentile(on_d, 10):.3f} / {np.median(on_d):.3f} / "
            f"{np.percentile(on_d, 90):.3f} | {off_d.min():.3f} / {np.median(off_d):.3f} |"
        )
    lines.append("")

    # ── Test 2 ────────────────────────────────────────────────────────────────
    if log_q:
        lines.append(f"## Real queries from the log ({len(log_q)})\n")
        res = {idx.name: search(idx, log_q) for idx in indexes}
        overlaps = []
        for i, q in enumerate(log_q):
            a = {s for s, _, _ in res["e5"][i]}
            b = {s for s, _, _ in res["gemini"][i]}
            overlaps.append(len(a & b))
            lines.append(f"### {q}\n\nShared top-5 sources: {len(a & b)}/5\n")
            for name in ("e5", "gemini"):
                lines.append(f"**{name}**")
                for sid, d, qq in res[name][i][:3]:
                    lines.append(f"- `{d:.3f}` [{sid}] {qq[:160].strip()}")
                lines.append("")
        lines.insert(1, f"Real queries: average shared top-5 = {np.mean(overlaps):.1f}/5\n")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"\nFull report: {REPORT_PATH.resolve()}")


if __name__ == "__main__":
    main()
