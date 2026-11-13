FROM debian:bookworm-slim AS extract
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl osmium-tool \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 3 -o /tmp/turkey.osm.pbf \
    https://download.geofabrik.de/europe/turkey-latest.osm.pbf \
    && osmium extract -s smart -b 28.0,39.53,30.05,40.66 /tmp/turkey.osm.pbf -o /bursa.osm.pbf \
    && rm /tmp/turkey.osm.pbf

FROM ghcr.io/project-osrm/osrm-backend@sha256:e1929ae2818226284d7ef007329098a30851c11528ab3712bc9c8d68da78278b
WORKDIR /data
COPY --from=extract /bursa.osm.pbf .
RUN \
    osrm-extract -p /opt/car.lua bursa.osm.pbf \
    && osrm-partition bursa.osrm \
    && osrm-customize bursa.osrm
