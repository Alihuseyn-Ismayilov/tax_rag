#!/usr/bin/env bash
# Pull the latest code of both apps and rebuild. Run on the VM:  bash update.sh
set -euo pipefail
git -C ~/apps/tax_rag pull --ff-only
git -C ~/apps/Home-Credit-Default-Risk pull --ff-only
cd ~/apps/tax_rag/deploy/azure
docker compose up -d --build
docker image prune -f
