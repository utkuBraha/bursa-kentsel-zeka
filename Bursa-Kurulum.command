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
compose=(docker compose -f docker-compose.yml -f compose.desktop.yml)

# Free this project's own ports first, then pick a free host port for each service.
"${compose[@]}" stop >/dev/null 2>&1 || true
docker_ports="$(docker ps --format '{{.Ports}}')"
port_busy() {
  grep -Eq "(:|^)$1->" <<<"$docker_ports" && return 0
  nc -z -G 1 127.0.0.1 "$1" >/dev/null 2>&1
}
env_port() {
  grep -E "^$1=[0-9]+$" .env | tail -n 1 | cut -d= -f2 || true
}
choose_port() {
  local port
  port="${3:-$(env_port "$1")}"
  port="${port:-$2}"
  for ((attempt=0; attempt<50; attempt++)); do
    if ! port_busy "$port"; then
      if [[ "$port" != "$(env_port "$1")" ]]; then
        grep -v -E "^$1=" .env >.env.tmp || true
        echo "$1=$port" >>.env.tmp
        mv .env.tmp .env
      fi
      export "$1=$port"
      return
    fi
    echo "Port $port kullanımda, sonraki port deneniyor..."
    port=$((port + 1))
  done
  echo "$1 için boş port bulunamadı."
  exit 1
}
choose_port BURSA_APP_PORT 3016
choose_port BURSA_API_PORT 8000
choose_port BURSA_DB_PORT 5433

echo "Uygulama ve demo verisi hazırlanıyor. İlk açılış birkaç dakika sürebilir."
# Docker can hold a port that no host tool shows; move to the next port and retry.
log="$(mktemp)"
started=0
for ((try=0; try<5; try++)); do
  if "${compose[@]}" up --build -d --wait --wait-timeout 600 2>&1 | tee "$log"; then
    started=1
    break
  fi
  busy="$(sed -nE -e 's/.*Bind for [^ ]*:([0-9]+) failed: port is already allocated.*/\1/p' -e 's/.*exposing port TCP [^ :]*:([0-9]+).*/\1/p' "$log" | head -n 1)"
  name=""
  for candidate in BURSA_APP_PORT BURSA_API_PORT BURSA_DB_PORT; do
    if [[ -n "$busy" && "${!candidate}" == "$busy" ]]; then name="$candidate"; fi
  done
  [[ -n "$name" ]] || break
  echo "Port $busy Docker tarafından kullanılıyor, sonraki port deneniyor..."
  choose_port "$name" "$busy" "$((busy + 1))"
done
rm -f "$log"
if [[ $started != 1 ]]; then
  "${compose[@]}" ps -a
  "${compose[@]}" logs --tail 40 api frontend osrm
  exit 1
fi
"${compose[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=15)"
"${compose[@]}" exec -T api python -c "import json, urllib.request; result = json.load(urllib.request.urlopen('http://osrm:5000/nearest/v1/driving/28.9427163,40.2103735', timeout=15)); assert result['code'] == 'Ok' and result['waypoints']"
echo "Uygulama hazır: http://127.0.0.1:$BURSA_APP_PORT/"
open "http://127.0.0.1:$BURSA_APP_PORT/"
