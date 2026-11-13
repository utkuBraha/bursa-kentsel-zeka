#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
directory=${1:-data/routing/city}
mkdir -p "$directory"
directory=$(cd "$directory" && pwd)
if [[ ! -s "$directory/bursa.osm.pbf" ]]; then
  printf 'OSM dosyası bulunamadı: %s/bursa.osm.pbf\n' "$directory" >&2
  exit 1
fi
image=ghcr.io/project-osrm/osrm-backend@sha256:e1929ae2818226284d7ef007329098a30851c11528ab3712bc9c8d68da78278b
for task in extract partition customize; do
  if [[ "$task" == extract ]]; then
    args=(-p /opt/car.lua /data/bursa.osm.pbf)
  else
    args=(/data/bursa.osrm)
  fi
  docker run --rm -v "$directory:/data" "$image" "osrm-$task" "${args[@]}"
done
