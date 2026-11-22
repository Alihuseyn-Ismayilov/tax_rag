# Image for the web app. Works on Heroku (heroku.yml), Azure, or any Docker host.
# Needs GEMINI_API_KEY in the environment; listens on $PORT (default 8000).
FROM python:3.11-slim

RUN useradd -m -u 1000 user
ENV PYTHONUNBUFFERED=1 \
    SHOW_HISTORY=0 \
    ANONYMIZED_TELEMETRY=False

WORKDIR /home/user/tax_rag

COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY --chown=user app/ app/
COPY --chown=user data/db/chroma_gemini/ data/db/chroma_gemini/
# The app appends to data/logs/query_log.jsonl, so data/ must be writable by user.
RUN mkdir -p data/logs && chown -R user:user /home/user/tax_rag

USER user
# main.py uses paths relative to app/ (../data/...).
WORKDIR /home/user/tax_rag/app
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
