# Deploying tax_rag and the credit scoring app

Both apps are Docker images that listen on `$PORT`:

| App | Repo | Image contents | RAM |
|---|---|---|---|
| tax_rag | this repo | `app/`, `data/db/chroma_gemini/`, `requirements-app.txt` | ~300 MB |
| Credit scoring | `Home-Credit-Default-Risk` (branch `deploy/docker`) | `app/`, `models/*.pkl`, `models/*.json`, `scorecard_table.csv` | ~220 MB |

tax_rag can't be built until `data/db/chroma_gemini/` exists (built by `scripts/4g_embed_gemini.py`).

## Option A: Heroku (Student Pack: $13/month for 24 months, card required)

$13 covers one Basic dyno ($7, always on) plus one Eco dyno ($5, sleeps after 30 min idle).
Two Basic dynos cost $14, which is $1/month above the credit.

```bash
heroku login
# --stack container makes Heroku build from heroku.yml + Dockerfile

# tax_rag
heroku create <tax-app-name> --stack container
heroku config:set GEMINI_API_KEY=... -a <tax-app-name>
git push heroku main
heroku ps:type web=basic -a <tax-app-name>

# credit scoring (run from the Home-Credit-Default-Risk repo)
heroku create <credit-app-name> --stack container
git push heroku deploy/docker:main
heroku ps:type web=eco -a <credit-app-name>   # or basic
```

## Option B: Azure for Students (no card, free B1s VM for 12 months)

Both apps and Caddy (automatic HTTPS) run on one B1s VM through `deploy/azure/docker-compose.yml`.

1. In the Azure portal, create a VM: Ubuntu 24.04, size **B1s**, SSH key auth.
   Open inbound ports 22, 80 and 443. Set a budget alert on the subscription.
2. Push both repos to GitHub. The setup script clones `main` by default.
   Override with `TAX_BRANCH=... CREDIT_BRANCH=...`.
3. On the VM:
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/<user>/tax_rag/main/deploy/azure/setup.sh
   bash setup.sh
   nano ~/apps/tax_rag/deploy/azure/.env    # GEMINI_API_KEY, TAX_HOST, CREDIT_HOST
   exit                                      # log back in so the docker group applies
   cd ~/apps/tax_rag/deploy/azure && docker compose up -d --build
   ```
4. To update later: `bash ~/apps/tax_rag/deploy/azure/update.sh`.

Without your own domain, `tax.<ip-with-dashes>.sslip.io` gives a working HTTPS name.
With a Student Pack domain (.me or .tech), point A records at the VM IP and put those names in `.env`.
