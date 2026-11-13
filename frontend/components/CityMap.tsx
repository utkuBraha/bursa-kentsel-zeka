"use client";
import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { GeoJSONSource, Map as LibreMap, Marker } from "maplibre-gl";
import { Minus, Plus, Maximize2, Minimize2, Crosshair } from "lucide-react";
import type { Feature, FeatureCollection, MultiPolygon } from "geojson";

export type Place = Feature<
  MultiPolygon,
  {
    id: string;
    code: string;
    name: string;
    active?: boolean;
    data_type: string;
    method: string;
    bbox: [number, number, number, number];
    label_point: [number, number];
    area_km2?: number;
    population_2025?: number;
    synthetic_population?: number;
    population_density_2025?: number;
    outside_area_m2?: number;
  }
>;
export type Collection = FeatureCollection<
  MultiPolygon,
  Place["properties"]
> & { total: number; quality_notice: string; display_tolerance_m: number };
import { coverageColor, type Coverage } from "./Accessibility";
import type { VehicleRoute } from "./RoadRoute";
import type {
  Detail,
  InventoryCollection,
  InventoryProperties,
} from "./Inventory";
import {
  inventoryIconId,
  inventorySymbol,
  markerImage,
} from "./inventory-symbols";

type InventoryMapProps = {
  candidate: [number, number] | null;
  onCandidatePick: ((point: [number, number]) => void) | null;
  route: VehicleRoute | null;
  coverage: Coverage | null;
  developmentScores?: Record<string, number>;
  inventory?: InventoryCollection;
  inventoryDetail: Detail | null;
  inventoryPanel: React.ReactNode;
  onInventorySelect: (kind: string, id: string) => void;
};
const inventoryLayers = [
  "inventory-cycleways",
  "inventory-points",
  "inventory-buildings",
];
const empty: FeatureCollection = { type: "FeatureCollection", features: [] };
export function title(s: string) {
  return s
    .toLocaleLowerCase("tr")
    .replace(/(^|\s)\S/g, (c) => c.toLocaleUpperCase("tr"));
}
export default function CityMap({
  districtName,
  districtCode,
  districts,
  neighborhoods,
  mode,
  selected,
  showDistricts,
  showNeighborhoods,
  showLabels,
  showBase,
  focus,
  onSelect,
  onReady,
  candidate,
  onCandidatePick,
  route,
  coverage,
  developmentScores,
  inventory,
  inventoryDetail,
  inventoryPanel,
  onInventorySelect,
}: {
  districtName: string;
  districtCode: string;
  districts: Collection;
  neighborhoods: Collection | null;
  mode: "bursa" | "district";
  selected: Place | null;
  showDistricts: boolean;
  showNeighborhoods: boolean;
  showLabels: boolean;
  showBase: boolean;
  focus: number;
  onSelect: (feature: Place, kind: "district" | "neighborhood") => void;
  onReady: () => void;
} & InventoryMapProps) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<LibreMap | null>(null),
    callback = useRef(onSelect),
    readyCallback = useRef(onReady);
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [tileError, setTileError] = useState(false),
    [zoom, setZoom] = useState(8),
    [center, setCenter] = useState("40.20° K · 28.95° D");
  const [openGroup, setOpenGroup] = useState<InventoryProperties[]>([]);
  const groups = useRef<InventoryProperties[][]>([]);
  const refreshMarkers = useRef<() => void>(() => {});
  const showNeighborhoodLabels = zoom >= 11;
  const candidateCallback = useRef(onCandidatePick);
  candidateCallback.current = onCandidatePick;
  const inventoryCallback = useRef(onInventorySelect);
  inventoryCallback.current = onInventorySelect;
  callback.current = onSelect;
  readyCallback.current = onReady;
  const dataRef = useRef({ districts, neighborhoods, mode });
  dataRef.current = { districts, neighborhoods, mode };
  function extent(place?: Place) {
    const m = map.current;
    if (!m) return;
    const f = place
      ? [place]
      : mode === "district"
        ? districts.features.filter((x) => x.properties.code === districtCode)
        : districts.features;
    const b = f.map((x) => x.properties.bbox);
    if (!b.length) return;
    m.fitBounds(
      [
        [Math.min(...b.map((x) => x[0])), Math.min(...b.map((x) => x[1]))],
        [Math.max(...b.map((x) => x[2])), Math.max(...b.map((x) => x[3]))],
      ],
      { padding: 50, duration: 650, maxZoom: 13 },
    );
  }
  useEffect(() => {
    if (!container.current) return;
    maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
    let m: LibreMap;
    try {
      m = new LibreMap({
        container: container.current,
        center: [28.95, 40.2],
        zoom: 8,
        attributionControl: false,
        renderWorldCopies: false,
        maxZoom: 18,
        minZoom: 6,
        maxBounds: [
          [26.8, 38.7],
          [31.2, 42],
        ],
        dragRotate: false,
        pitchWithRotate: false,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              maxzoom: 19,
              attribution: "© OpenStreetMap contributors",
            },
          },
          layers: [
            {
              id: "background",
              type: "background",
              paint: { "background-color": "#eaf2f7" },
            },
            {
              id: "osm",
              type: "raster",
              source: "osm",
              layout: { visibility: "none" },
              paint: {
                "raster-opacity": 0.55,
                "raster-saturation": -0.8,
                "raster-brightness-max": 1,
              },
            },
          ],
        },
      });
    } catch {
      setError(
        "Harita başlatılamadı. WebGL destekli bir tarayıcı kullanın. Bölge listesiyle seçim yapabilirsiniz.",
      );
      return;
    }
    map.current = m;
    m.touchZoomRotate.disableRotation();
    m.addControl(
      new maplibregl.ScaleControl({ unit: "metric" }),
      "bottom-left",
    );
    m.on("styleimagemissing", ({ id }) => {
      if (!id.startsWith("inventory-") || m.hasImage(id)) return;
      const image = markerImage(id);
      if (image) m.addImage(id, image, { pixelRatio: 2 });
    });
    m.on("load", () => {
      for (const id of ["districts", "neighborhoods", "selection"])
        m.addSource(id, { type: "geojson", data: empty });
      m.addLayer({
        id: "district-fill",
        type: "fill",
        source: "districts",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "active"], true],
            "#d6e4ed",
            "#dce7ed",
          ],
          "fill-opacity": 0.72,
        },
      });
      m.addLayer({
        id: "district-line",
        type: "line",
        source: "districts",
        paint: {
          "line-color": [
            "case",
            ["==", ["get", "active"], true],
            "#7e98aa",
            "#7e98aa",
          ],
          "line-width": 1.2,
        },
      });
      m.addLayer({
        id: "neighborhood-fill",
        type: "fill",
        source: "neighborhoods",
        paint: { "fill-color": "#6d9abb", "fill-opacity": 0.3 },
      });
      m.addLayer({
        id: "neighborhood-line",
        type: "line",
        source: "neighborhoods",
        paint: { "line-color": "#527f9d", "line-width": 1 },
      });
      m.addLayer({
        id: "selected-fill",
        type: "fill",
        source: "selection",
        paint: { "fill-color": "#27618a", "fill-opacity": 0.25 },
      });
      m.addLayer({
        id: "selected-line",
        type: "line",
        source: "selection",
        paint: { "line-color": "#123b60", "line-width": 2.5 },
      });
      m.addSource("air-coverage", { type: "geojson", data: empty });
      for (const [index, color] of ["#b96263", "#c79850", "#5a8966"].entries()) {
        m.addLayer({
          id: `air-coverage-${index}`,
          source: "air-coverage",
          type: "fill",
          filter: ["==", ["get", "band"], index],
          paint: { "fill-color": color, "fill-opacity": 1 },
        });
      }
      m.addSource("inventory", { type: "geojson", data: empty });
      m.addSource("inventory-markers", { type: "geojson", data: empty });
      m.addSource("inventory-selection", { type: "geojson", data: empty });
      m.addLayer({
        id: "inventory-buildings",
        type: "fill",
        source: "inventory",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#c49652", "fill-opacity": 0.65 },
      });
      m.addLayer({
        id: "inventory-cycleways",
        type: "line",
        source: "inventory",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": "#306747",
          "line-width": 4,
          "line-dasharray": [2, 1],
        },
      });
      m.addLayer({
        id: "inventory-highlight-line",
        type: "line",
        source: "inventory-selection",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: { "line-color": "#ffffff", "line-width": 5 },
      });
      m.addLayer({
        id: "inventory-points",
        type: "symbol",
        source: "inventory-markers",
        layout: {
          "icon-image": ["get", "icon"],
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      });
      m.addLayer({
        id: "inventory-highlight-point",
        type: "circle",
        source: "inventory-selection",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-color": "#123b60",
          "circle-opacity": 0.12,
          "circle-radius": 17,
          "circle-stroke-color": "#123b60",
          "circle-stroke-width": 3,
        },
      });
      m.addLayer({
        id: "inventory-highlight-polygon",
        type: "line",
        source: "inventory-selection",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "line-color": "#ffffff", "line-width": 3 },
      });
      m.addSource("vehicle-route", { type: "geojson", data: empty });
      m.addLayer({
        id: "vehicle-route",
        type: "line",
        source: "vehicle-route",
        paint: { "line-color": "#185a91", "line-width": 5 },
      });
      setReady(true);
      readyCallback.current();
    });
    const hitLayers = [
      ...inventoryLayers,
      "neighborhood-fill",
      "district-fill",
    ];
    m.on("click", (event) => {
      if (candidateCallback.current) {
        candidateCallback.current([event.lngLat.lng, event.lngLat.lat]);
        return;
      }
      const hit = m.queryRenderedFeatures(event.point, {
        layers: hitLayers.filter((id) => !!m.getLayer(id)),
      })[0];
      if (!hit) return;
      const members = groups.current[hit.properties.group];
      if (
        hit.layer.id === "inventory-points" &&
        members &&
        (members.length > 1 || hit.properties.analysisOnly)
      ) {
        setOpenGroup(members);
        return;
      }
      setOpenGroup([]);
      if (inventoryLayers.includes(hit.layer.id)) {
        inventoryCallback.current(hit.properties.kind, hit.properties.id);
        return;
      }
      const kind =
        hit.layer.id === "neighborhood-fill" ? "neighborhood" : "district";
      const source =
        kind === "district"
          ? dataRef.current.districts
          : dataRef.current.neighborhoods;
      const feature = source?.features.find(
        (item) => item.properties.id === hit.properties.id,
      );
      if (feature) callback.current(feature, kind);
    });
    const hover = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: true,
      offset: 18,
      className: "inventory-map-tooltip",
    });
    m.getCanvas().addEventListener("mouseleave", () => hover.remove());
    m.on("movestart", () => hover.remove());
    m.on("mousemove", (event) => {
      const hits = m.queryRenderedFeatures(event.point, {
        layers: hitLayers.filter((id) => !!m.getLayer(id)),
      });
      const hit = hits[0];
      if (
        !candidateCallback.current &&
        hit &&
        inventoryLayers.includes(hit.layer.id)
      ) {
        const properties = hit.properties;
        const label =
          properties.count > 1
            ? `${Number(properties.count).toLocaleString("tr-TR")} kayıt · listeyi aç`
            : properties.analysisOnly
              ? properties.name
              : inventorySymbol(properties.kind, properties.category_code)[1];
        hover.setLngLat(event.lngLat).setText(label);
        if (!hover.isOpen()) hover.addTo(m);
      } else {
        hover.remove();
      }
      m.getCanvas().style.cursor = candidateCallback.current
        ? "crosshair"
        : hits.length
          ? "pointer"
          : "";
    });
    m.on("moveend", () => {
      refreshMarkers.current();
      setZoom(m.getZoom());
      const c = m.getCenter();
      setCenter(`${c.lat.toFixed(3)}° K · ${c.lng.toFixed(3)}° D`);
    });
    m.on("error", (e) => {
      if ("sourceId" in e && e.sourceId === "osm") setTileError(true);
    });
    const observer = new ResizeObserver(() => {
      m.resize();
      refreshMarkers.current();
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("districts") as GeoJSONSource).setData(districts);
    (map.current.getSource("neighborhoods") as GeoJSONSource).setData(
      neighborhoods || empty,
    );
  }, [ready, districts, neighborhoods]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    for (const id of ["district-fill", "district-line"])
      m.setLayoutProperty(id, "visibility", showDistricts ? "visible" : "none");
    for (const id of ["neighborhood-fill", "neighborhood-line"])
      m.setLayoutProperty(
        id,
        "visibility",
        mode === "district" && showNeighborhoods ? "visible" : "none",
      );
    m.setLayoutProperty("osm", "visibility", showBase ? "visible" : "none");
  }, [ready, mode, showDistricts, showNeighborhoods, showBase]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const visible =
      selected &&
      (selected.properties.active !== undefined
        ? showDistricts
        : showNeighborhoods && mode === "district");
    (map.current.getSource("selection") as GeoJSONSource).setData(
      visible ? { type: "FeatureCollection", features: [selected] } : empty,
    );
  }, [ready, selected, mode, showDistricts, showNeighborhoods]);
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const markers: Marker[] = [];
    if (showLabels && (mode === "bursa" || showNeighborhoodLabels)) {
      const fs =
        mode === "district"
          ? showNeighborhoods
            ? neighborhoods?.features || []
            : []
          : showDistricts
            ? districts.features
            : [];
      for (const f of fs) {
        const el = document.createElement("button");
        el.className = `geo-map-label ${mode === "district" ? "neighborhood-label" : ""}`;
        el.textContent = title(f.properties.name);
        el.setAttribute(
          "aria-label",
          `${title(f.properties.name)} ${mode === "district" ? "mahallesini seç" : "ilçesini seç"}`,
        );
        el.onclick = (e) => {
          e.stopPropagation();
          callback.current(
            f,
            mode === "district" ? "neighborhood" : "district",
          );
        };
        markers.push(
          new Marker({ element: el })
            .setLngLat(f.properties.label_point)
            .addTo(m),
        );
      }
    }
    return () => markers.forEach((x) => x.remove());
  }, [
    ready,
    mode,
    districts,
    neighborhoods,
    showLabels,
    showDistricts,
    showNeighborhoods,
    showNeighborhoodLabels,
  ]);
  useEffect(() => {
    if (ready) extent();
  }, [ready, mode, districts, districtCode]); // Extent changes only with district/mode; selection has its own action.
  useEffect(() => {
    if (!ready || !map.current || !selected || focus === 0) return;
    const b = selected.properties.bbox;
    map.current.fitBounds(
      [
        [b[0], b[1]],
        [b[2], b[3]],
      ],
      { padding: 65, duration: 650, maxZoom: 15 },
    );
  }, [focus, ready]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const features = mode === "district" ? (inventory?.features ?? []) : [];
    const sources = coverage?.service_locations;
    const analyzedIds = new Set(sources?.map((point) => point.id));
    const displayFeatures = sources
      ? features.filter(
          (item) =>
            item.properties.category_code !== coverage?.category ||
            analyzedIds.has(item.properties.id),
        )
      : features;
    setOpenGroup([]);
    const locations = displayFeatures.flatMap(({ geometry, properties }) => {
      if (geometry.type === "Point") {
        return [
          { coordinates: geometry.coordinates as [number, number], properties },
        ];
      }
      const points =
        geometry.type === "MultiPolygon"
          ? geometry.coordinates.flat(2)
          : geometry.type === "Polygon"
            ? geometry.coordinates.flat()
            : geometry.type === "LineString"
              ? geometry.coordinates
              : [];
      if (!points.length) return [];
      const bounds = new maplibregl.LngLatBounds();
      for (const point of points) bounds.extend(point as [number, number]);
      return [{ coordinates: bounds.getCenter().toArray(), properties }];
    });
    const visibleIds = new Set(locations.map((item) => item.properties.id));
    for (const point of sources ?? []) {
      if (visibleIds.has(point.id)) continue;
      locations.push({
        coordinates: [point.lon, point.lat],
        properties: {
          id: point.id,
          name: point.name,
          kind: "services",
          category_code: coverage?.category,
          neighborhood: "",
          data_type: coverage?.station_set === "matched" ? "REAL" : "SYNTHETIC",
          method: "",
          source_record_id: point.id,
          analysisOnly: coverage?.station_set === "matched",
        },
      });
    }
    (m.getSource("inventory") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: features.filter((item) => item.geometry.type !== "Point"),
    });
    refreshMarkers.current = () => {
      const { clientWidth: width, clientHeight: height } = m.getContainer();
      if (!width || !height) return;
      const columns = Math.max(1, Math.floor(width / 156));
      const rows = Math.max(1, Math.floor(height / 68));
      const cellWidth = width / columns;
      const cellHeight = height / rows;
      const buckets = new Map<string, typeof locations>();
      for (const location of locations) {
        const { x, y } = m.project(location.coordinates);
        if (x < 0 || y < 0 || x >= width || y >= height) continue;
        const cell =
          Math.floor(y / cellHeight) * columns + Math.floor(x / cellWidth);
        const { kind, category_code } = location.properties;
        const key = `${cell}:${inventoryIconId(kind, category_code ?? location.properties.use)}`;
        const bucket = buckets.get(key);
        if (bucket) bucket.push(location);
        else buckets.set(key, [location]);
      }
      groups.current = [];
      const cellGroups = new Map<number, string[]>();
      for (const key of buckets.keys()) {
        const cell = Number(key.split(":")[0]);
        const keys = cellGroups.get(cell);
        if (keys) keys.push(key);
        else cellGroups.set(cell, [key]);
      }
      const markers = Array.from(buckets, ([key, members]) => {
        const { properties } = members[0];
        const icon = inventoryIconId(properties.kind, properties.category_code ?? properties.use);
        const count = members.length;
        const group =
          groups.current.push(members.map((item) => item.properties)) - 1;
        const cell = Number(key.split(":")[0]);
        const keys = cellGroups.get(cell)!;
        const slot = keys.indexOf(key);
        const left = (cell % columns) * cellWidth;
        const top = Math.floor(cell / columns) * cellHeight;
        const { x, y } = m.project(members[0].coordinates);
        const slotColumns = Math.min(2, keys.length);
        const slotRows = Math.ceil(keys.length / slotColumns);
        const coordinates = m
          .unproject(
            keys.length > 1
              ? [
                  left +
                    (cellWidth * ((slot % slotColumns) + 0.5)) / slotColumns,
                  top +
                    (cellHeight * (Math.floor(slot / slotColumns) + 0.5)) /
                      slotRows,
                ]
              : count > 1
                ? [left + cellWidth / 2, top + cellHeight / 2]
                : [
                    Math.max(left + 16, Math.min(left + cellWidth - 16, x)),
                    Math.max(top + 16, Math.min(top + cellHeight - 16, y)),
                  ],
          )
          .toArray();
        const imageId =
          count === 1 ? icon : `inventory-group-${icon.slice(10)}-${count}`;
        if (!m.hasImage(imageId)) {
          const image = markerImage(imageId);
          if (image) m.addImage(imageId, image, { pixelRatio: 2 });
        }
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates },
          properties: { ...properties, group, count, icon: imageId },
        };
      });
      (m.getSource("inventory-markers") as GeoJSONSource).setData({
        type: "FeatureCollection",
        features: markers,
      });
    };
    refreshMarkers.current();
  }, [ready, mode, inventory, coverage]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const item = mode === "district" ? inventoryDetail : null;
    (m.getSource("inventory-selection") as GeoJSONSource).setData(
      item ? { type: "FeatureCollection", features: [item] } : empty,
    );
    if (item?.geometry.type === "Point") {
      m.panTo(item.geometry.coordinates as [number, number]);
    } else if (item) {
      const points =
        item.geometry.type === "MultiPolygon"
          ? item.geometry.coordinates.flat(2)
          : item.geometry.type === "Polygon"
            ? item.geometry.coordinates.flat()
            : item.geometry.type === "LineString"
              ? item.geometry.coordinates
              : [];
      if (points.length) {
        const bounds = new maplibregl.LngLatBounds();
        for (const point of points) bounds.extend(point as [number, number]);
        m.panTo(bounds.getCenter());
      }
    }
  }, [ready, mode, inventoryDetail]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const roadCoverage = coverage?.threshold_s ? coverage : null;
    const colors = Object.fromEntries(
      roadCoverage?.neighborhoods.map((row) => [
        row.id,
        coverageColor(row, roadCoverage.bands),
      ]) ?? [],
    );
    m.setPaintProperty(
      "neighborhood-fill",
      "fill-color",
      roadCoverage
        ? ["coalesce", ["get", ["get", "id"], ["literal", colors]], "#6d8193"]
        : "#6d9abb",
    );
    m.setPaintProperty(
      "neighborhood-fill",
      "fill-opacity",
      roadCoverage ? 0.72 : 0.3,
    );
    if (developmentScores) {
      const color: maplibregl.ExpressionSpecification = [
        "interpolate", ["linear"],
        ["coalesce", ["get", ["get", "id"], ["literal", developmentScores]], -1],
        -1, "#d9e2e9", 0, "#cfe3f3", 50, "#5b97be", 100, "#123b60",
      ];
      m.setPaintProperty(mode === "bursa" ? "district-fill" : "neighborhood-fill", "fill-color", color);
      if (mode === "district") m.setPaintProperty("neighborhood-fill", "fill-opacity", 0.76);
    }
    if (!developmentScores || mode === "district") {
      m.setPaintProperty("district-fill", "fill-color", [
        "case", ["==", ["get", "active"], true], "#d6e4ed", "#dce7ed",
      ]);
    }
    const radius = coverage?.threshold_m;
    (m.getSource("air-coverage") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: radius ? (coverage?.service_locations ?? []).flatMap(({lon, lat}) =>
        [2, 1.5, 1].map((factor, band) => {
          const radians = Math.PI / 180;
          const center = lat * radians;
          const arc = radius * factor / 6371008.8;
          const ring = Array.from({length: 73}, (_, index) => {
            const bearing = (index % 72) * Math.PI / 36;
            const latitude = Math.asin(Math.sin(center) * Math.cos(arc) +
              Math.cos(center) * Math.sin(arc) * Math.cos(bearing));
            const longitude = Math.atan2(Math.sin(bearing) * Math.sin(arc) * Math.cos(center),
              Math.cos(arc) - Math.sin(center) * Math.sin(latitude));
            return [lon + longitude / radians, latitude / radians];
          });
          return {type: "Feature", properties: {band}, geometry: {type: "Polygon", coordinates: [ring]}};
        })
      ) : [],
    });
  }, [ready, coverage, developmentScores, mode]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    (m.getSource("vehicle-route") as GeoJSONSource).setData(
      route
        ? { type: "Feature", geometry: route.geometry, properties: {} }
        : empty,
    );
    if (route && route.geometry.coordinates.length > 1) {
      const bounds = new maplibregl.LngLatBounds();
      for (const point of route.geometry.coordinates)
        bounds.extend(point as [number, number]);
      m.fitBounds(bounds, { padding: 65, maxZoom: 17 });
    }
  }, [ready, route]);
  useEffect(() => {
    if (!ready || !map.current || !candidate) return;
    const pin = document.createElement("div");
    pin.className = "candidate-pin";
    pin.textContent = "Aday";
    const marker = new Marker({ element: pin })
      .setLngLat(candidate)
      .addTo(map.current);
    return () => {
      marker.remove();
    };
  }, [candidate, ready]);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!expanded) return;
    function close(event: KeyboardEvent) {
      if (event.key === "Escape") setExpanded(false);
    }
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [expanded]);
  return (
    <div
      className={`geo-map-frame ${onCandidatePick ? "picking-candidate" : ""} ${expanded ? "geo-map-expanded" : ""}`}
    >
      <div
        ref={container}
        className="geo-map-canvas"
        aria-label="Bursa etkileşimli sınır haritası"
        data-testid="city-map"
      />
      <div className="geo-map-badge">
        <span className="status-dot" />
        {onCandidatePick
          ? "Haritada aday konumu işaretleyin"
          : mode === "bursa" ? "Bursa ilçeleri" : `${districtName} mahalleleri`}
        {developmentScores && <small>Sentetik hizmet puanı · koyu mavi daha yüksek</small>}
      </div>
      <div className="geo-map-controls">
        <button
          aria-label="Yakınlaştır"
          disabled={!ready}
          onClick={() => map.current?.zoomIn()}
        >
          <Plus size={18} />
        </button>
        <button
          aria-label="Uzaklaştır"
          disabled={!ready}
          onClick={() => map.current?.zoomOut()}
        >
          <Minus size={18} />
        </button>
        <button
          aria-label="Bölgeyi sığdır"
          disabled={!ready}
          onClick={() => extent(selected ?? undefined)}
        >
          <Crosshair size={17} />
        </button>
        <button
          aria-label={expanded ? "Haritayı küçült" : "Haritayı büyüt"}
          aria-pressed={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
        </button>
      </div>
      {(!ready || error) && (
        <div className="geo-map-loading" role="status">
          {error || "Harita hazırlanıyor…"}
        </div>
      )}
      {tileError && showBase && (
        <div className="geo-tile-error" role="status">
          OSM altlığına erişilemiyor. Resmî sınırlar kullanılabilir.
        </div>
      )}
      {openGroup.length === 0 && inventoryPanel}
      {openGroup.length > 0 && (
        <section
          className="geo-details inventory-map-panel"
          aria-label="Küme kayıtları"
        >
          <header className="inventory-panel-header">
            <strong>{openGroup.length.toLocaleString("tr-TR")} kayıt</strong>
            <button className="inventory-link" onClick={() => setOpenGroup([])}>
              Kapat
            </button>
          </header>
          {openGroup.map((item) => {
            const [icon, label] = inventorySymbol(
              item.kind,
              item.category_code,
            );
            if (item.analysisOnly) {
              return (
                <p key={item.id}>
                  {icon} {item.name} · Hesaba katılan eşleştirilmiş istasyon
                </p>
              );
            }
            return (
              <button
                key={item.id}
                className="geo-place"
                onClick={() => {
                  setOpenGroup([]);
                  inventoryCallback.current(item.kind, item.id);
                }}
              >
                <span aria-hidden="true">{icon}</span>
                <span>
                  {label} · {item.name}
                </span>
              </button>
            );
          })}
        </section>
      )}
      <div className="geo-map-readout" aria-live="polite">
        <span>{center}</span>
        <span>Yakınlık {zoom.toFixed(1)}</span>
      </div>
      <div className="geo-map-attribution">
        <a
          href="https://acikyesil.bursa.bel.tr/license"
          target="_blank"
          rel="noreferrer"
        >
          Bursa Açık Yeşil · Lisans
        </a>
        {showBase && (
          <>
            {" "}
            ·{" "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
            >
              © OpenStreetMap
            </a>
          </>
        )}
      </div>
    </div>
  );
}
