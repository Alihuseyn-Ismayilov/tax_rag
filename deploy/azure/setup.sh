#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 22.04/24.04 Azure VM for both apps.
# Run on the VM:  bash setup.sh
set -euo pipefail

TAX_REPO="${TAX_REPO:-https://github.com/Alihuseyn-Ismayilov/tax_rag.git}"
CREDIT_REPO="${CREDIT_REPO:-https://github.com/Mekhty111/Home-Credit-Default-Risk.git}"
TAX_BRANCH="${TAX_BRANCH:-main}"
CREDIT_BRANCH="${CREDIT_BRANCH:-main}"

# 1. Swap: B1s has 1 GiB RAM, building and running two Python apps needs more.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 2. Docker Engine + compose plugin.
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# 3. Code.
mkdir -p ~/apps && cd ~/apps
[ -d tax_rag ] || git clone -b "$TAX_BRANCH" "$TAX_REPO" tax_rag
[ -d Home-Credit-Default-Risk ] || git clone -b "$CREDIT_BRANCH" "$CREDIT_REPO" Home-Credit-Default-Risk

cd ~/apps/tax_rag/deploy/azure
[ -f .env ] || cp .env.example .env

IP="$(curl -fsS https://api.ipify.org || true)"
echo
echo "Done. Next:"
echo "  1. nano ~/apps/tax_rag/deploy/azure/.env   (GEMINI_API_KEY, hosts; VM IP: ${IP:-unknown})"
echo "  2. Log out and back in (docker group), then:"
echo "     cd ~/apps/tax_rag/deploy/azure && docker compose up -d --build"
