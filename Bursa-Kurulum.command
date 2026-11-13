#!/bin/bash
set -euo pipefail

temporary=""
cleanup() {
  status=$?
  if [[ -n "$temporary" ]]; then rm -rf "$temporary"; fi
  if [[ $status != 0 ]]; then
    echo "Kurulum durdu (kod: $status)."
    read -r -p "Kapatmak için Enter..." || true
  fi
}
trap cleanup EXIT

base="$HOME/Library/Application Support/Bursa Kentsel Zeka"
here="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$here/compose.desktop.yml" ]]; then
  project="$here"
else
  project="$base/bursa-kentsel-zeka-osrm"
  if [[ ! -f "$project/compose.desktop.yml" ]]; then
    mkdir -p "$base"
    temporary="$(mktemp -d)"
    echo "Bursa Kentsel Zekâ indiriliyor..."
    curl --fail --location --retry 3 --output "$temporary/project.zip" \
      https://codeload.github.com/utkuBraha/bursa-kentsel-zeka/zip/refs/heads/main
    ditto -x -k "$temporary/project.zip" "$temporary"
    test -f "$temporary/bursa-kentsel-zeka-main/compose.desktop.yml"
    mv "$temporary/bursa-kentsel-zeka-main" "$project"
  fi
fi

export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
if ! docker info >/dev/null 2>&1 && [[ ! -d /Applications/Docker.app ]]; then
  case "$(uname -m)" in
    arm64) architecture=arm64 ;;
    x86_64) architecture=amd64 ;;
    *) echo "Bu Mac işlemcisi desteklenmiyor."; exit 1 ;;
  esac
  installer="$base/Docker.dmg"
  mkdir -p "$base"
  echo "Docker Desktop indiriliyor..."
  curl --fail --location --retry 3 --output "$installer" \
    "https://desktop.docker.com/mac/main/$architecture/Docker.dmg"
  open "$installer"
  echo "Docker'ı Applications klasörüne taşıyın ve Docker Desktop'ı açın."
  read -r -p "İlk açılış adımları tamamlanınca Enter'a basın..."
fi

if ! docker info >/dev/null 2>&1; then
  open -a Docker
  echo "Docker'ın hazır olması bekleniyor..."
  for ((attempt=0; attempt<90; attempt++)); do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 2
  done
fi
docker info >/dev/null
docker compose version >/dev/null

cd "$project"
[[ -f .env ]] || cp .env.example .env
echo "Uygulama ve demo verisi hazırlanıyor. İlk açılış birkaç dakika sürebilir."
docker compose -f docker-compose.yml -f compose.desktop.yml up --build -d --wait --wait-timeout 600
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready >/dev/null
docker compose -f docker-compose.yml -f compose.desktop.yml exec -T api python -c "import json, urllib.request; result = json.load(urllib.request.urlopen('http://osrm:5000/nearest/v1/driving/28.9427163,40.2103735', timeout=15)); assert result['code'] == 'Ok' and result['waypoints']"
open http://127.0.0.1:3016/
