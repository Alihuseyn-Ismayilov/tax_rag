#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 Azure VM for both apps.
# Run on the VM:  bash setup.sh
set -euo pipefail

TAX_REPO="${TAX_REPO:-https://github.com/Alihuseyn-Ismayilov/tax_rag.git}"
CREDIT_REPO="${CREDIT_REPO:-https://github.com/Mekhty111/Home-Credit-Default-Risk.git}"
TAX_BRANCH="${TAX_BRANCH:-deploy/server-setup}"
CREDIT_BRANCH="${CREDIT_BRANCH:-deploy/docker}"

# 1. Swap: the VM has 1 GiB RAM, building and running two Python apps needs more.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 2. Docker Engine + compose plugin from the Ubuntu repositories.
if ! command -v docker >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose-v2 git
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
fi

# 3. Code.
mkdir -p ~/apps && cd ~/apps
[ -d tax_rag ] || git clone -b "$TAX_BRANCH" "$TAX_REPO" tax_rag
[ -d Home-Credit-Default-Risk ] || git clone -b "$CREDIT_BRANCH" "$CREDIT_REPO" Home-Credit-Default-Risk

# 4. .env with sslip.io hostnames for this VM's public IP.
cd ~/apps/tax_rag/deploy/azure
if [ ! -f .env ]; then
  IP="$(curl -fsS https://api.ipify.org || true)"
  cp .env.example .env
  if [ -n "$IP" ]; then
    sed -i "s/20-1-2-3/${IP//./-}/g" .env
  fi
fi

echo
echo "Done. Next:"
echo "  1. Check ~/apps/tax_rag/deploy/azure/.env (hosts; GEMINI_API_KEY once tax_rag is ready)"
echo "  2. Log out and back in (docker group), then:"
echo "     cd ~/apps/tax_rag/deploy/azure && docker compose up -d --build"
