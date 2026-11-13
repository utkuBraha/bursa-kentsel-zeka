"use client";

import { useEffect, useState } from "react";
import type { LineString } from "geojson";

export type VehicleRoute = {
  geometry: LineString;
  distance_m: number;
  duration_s: number;
  direction: "service_to_household" | "household_to_service";
  snap_distances_m: number[];
};

export default function RoadRoute({
  household,
  services,
  neighboringServices,
  onRoute,
}: {
  household: string;
  services: { id: string; name: string; category_code: string }[];
  neighboringServices: { id: string; name: string; district: string }[];
  onRoute: (route: VehicleRoute | null) => void;
}) {
  const [selected, setSelected] = useState(
    services.find((s) => s.category_code === "fire")?.id ??
      services[0]?.id ??
      "",
  );
  const [result, setResult] = useState<VehicleRoute | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<AbortController | null>(null);
  useEffect(() => () => pending?.abort(), [pending]);
  async function calculate() {
    const controller = new AbortController();
    setPending(controller);
    setError("");
    setResult(null);
    onRoute(null);
    try {
      const params = new URLSearchParams({
        household_id: household,
        service_id: selected,
      });
      const response = await fetch(`/api/v1/accessibility/route?${params}`, {
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok) throw Error(payload.detail ?? "Araç rotası alınamadı.");
      if (!controller.signal.aborted) {
        setResult(payload);
        onRoute(payload);
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(
          error instanceof Error ? error.message : "Araç rotası alınamadı.",
        );
    } finally {
      if (!controller.signal.aborted) setPending(null);
    }
  }
  return (
    <div className="access-panel">
      <h3>Yol ağı · Araç rotası</h3>
      <label>
        Rota için hizmet
        <select
          value={selected}
          disabled={!!pending}
          onChange={(event) => {
            setSelected(event.target.value);
            setResult(null);
            setError("");
            onRoute(null);
          }}
        >
          <optgroup label="Seçili ilçe">
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </optgroup>
          {neighboringServices.length > 0 && (
            <optgroup label="Komşu ilçeler · 8 km içinde">
              {neighboringServices.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.district} · {s.name}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </label>
      <button
        className="geo-focus"
        disabled={!!pending || !selected}
        onClick={() => void calculate()}
      >
        {pending ? "Rota hesaplanıyor…" : "Araç rotasını hesapla"}
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <div role="status">
          <dl className="analysis-metrics">
            <div>
              <dt>Yol mesafesi</dt>
              <dd>
                {(result.distance_m / 1000).toLocaleString("tr-TR", {
                  maximumFractionDigits: 2,
                })}{" "}
                <small>km</small>
              </dd>
            </div>
            <div>
              <dt>Tahmini sürüş</dt>
              <dd>
                {(result.duration_s / 60).toLocaleString("tr-TR", {
                  maximumFractionDigits: 1,
                })}{" "}
                <small>dk</small>
              </dd>
            </div>
          </dl>
          <p>
            {result.direction === "service_to_household"
              ? "Hizmetten haneye"
              : "Haneden hizmete"}{" "}
            · Mesafe ve süre araç ağı üzerinde ölçülür.
          </p>
        </div>
      )}
      <p>
        Standart araç profili. Canlı trafik, çıkış hazırlığı ve müdahale süresi
        hesaba katılmaz.{" "}
        <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a>
        {" · "}
        <a href="https://routing.openstreetmap.de/about.html">FOSSGIS / OSRM</a>
        {" · "}
        <a href="https://www.openstreetmap.org/fixthemap">Haritayı düzelt</a>
      </p>
    </div>
  );
}
