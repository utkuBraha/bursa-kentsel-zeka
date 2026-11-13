"use client";

import { useEffect, useRef, useState } from "react";

type Category = { code: string; name: string };
export type CoverageRow = {
  id: string;
  name: string;
  households: number;
  adequate: number;
  borderline: number;
  insufficient: number;
  missing: number;
  adequate_population: number;
};
export type Coverage = {
  category?: string;
  threshold_m?: number;
  threshold_s?: number;
  service_count?: number;
  station_set?: "demo" | "matched";
  service_locations?: { id: string; name: string; lon: number; lat: number }[];
  source_url?: string;
  neighborhoods: CoverageRow[];
  bands?: [number, number];
};
export const coverageColors = {
  low: "#b96263",
  medium: "#c79850",
  high: "#5a8966",
  missing: "#6d8193",
};

export function coverageColor(
  row: CoverageRow,
  bands: [number, number] = [50, 80],
) {
  const known = row.households - row.missing;
  if (!known) return coverageColors.missing;
  const share = row.adequate / known;
  return share * 100 < bands[0]
    ? coverageColors.low
    : share * 100 < bands[1]
      ? coverageColors.medium
      : coverageColors.high;
}

export default function Accessibility({
  districtCode,
  onCoverage,
  onThresholds,
  showResults = true,
}: {
  districtCode: string;
  showResults?: boolean;
  onCoverage: (data: Coverage | null) => void;
  onThresholds: (values: Record<string, number>) => void;
}) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [defaults, setDefaults] = useState<Record<string, number>>({});
  const [category, setCategory] = useState("fire");
  const [roadAvailable, setRoadAvailable] = useState(false);
  const [mode, setMode] = useState<"road" | "air">("air");
  const [minutes, setMinutes] = useState("10");
  const [meters, setMeters] = useState("3000");
  const [thresholds, setThresholds] = useState<Record<string, number>>({});
  const [result, setResult] = useState<Coverage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [bands, setBands] = useState<[number, number]>([50, 80]);
  const coverageRequest = useRef<AbortController | null>(null);
  useEffect(() => () => coverageRequest.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/accessibility/settings", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw Error();
        return response.json();
      })
      .then((data) => {
        setCategories(data.categories);
        setDefaults(data.thresholds);
        setRoadAvailable(data.road_available);
        if (data.road_available) setMode("road");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Hizmet ayarları yüklenemedi.");
      });
    return () => controller.abort();
  }, []);
  async function calculate(event: React.FormEvent) {
    event.preventDefault();
    coverageRequest.current?.abort();
    const controller = new AbortController();
    coverageRequest.current = controller;
    setBusy(true);
    setError("");
    setResult(null);
    onCoverage(null);
    try {
      const query = new URLSearchParams(
        mode === "road"
          ? {
              category,
              minutes,
            }
          : { category, meters, map_only: "true" },
      );
      query.set("district_code", districtCode);
      const response = await fetch(`/api/v1/accessibility/coverage?${query}`, {
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Kapsama hesabı alınamadı.");
      if (controller.signal.aborted) return;
      setResult(data);
      onCoverage({ ...data, bands });
    } catch (error) {
      if (controller.signal.aborted) return;
      setError(
        error instanceof Error ? error.message : "Kapsama hesabı alınamadı.",
      );
    } finally {
      if (coverageRequest.current === controller) {
        coverageRequest.current = null;
        if (!controller.signal.aborted) setBusy(false);
      }
    }
  }
  function clearCoverage() {
    setResult(null);
    onCoverage(null);
  }
  const totals = result?.neighborhoods.reduce(
    (sum, row) => ({
      households: sum.households + row.households,
      adequate: sum.adequate + row.adequate,
      missing: sum.missing + row.missing,
      population: sum.population + row.adequate_population,
    }),
    { households: 0, adequate: 0, missing: 0, population: 0 },
  );
  return (
    <div className="geo-details access-panel">
      <h2>Hizmet kapsaması</h2>
      <p>
        {mode === "road"
          ? "Standart araç profiliyle tahmini sürüş. İtfaiye ve hastane için hizmetten haneye hesaplanır."
          : "Hizmet noktalarının çevresinde kuş uçuşu kapsama halkaları."}
      </p>
      <form onSubmit={calculate}>
        <label>
          Hizmet
          <select
            value={category}
            disabled={busy}
            onChange={(event) => {
              setCategory(event.target.value);
              setMeters(
                String(
                  defaults[event.target.value] ??
                    (event.target.value === "fire" ? 3000 : 1000),
                ),
              );
              clearCoverage();
            }}
          >
            {categories.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Hesap yöntemi
          <select
            value={mode}
            disabled={busy}
            onChange={(event) => {
              setMode(event.target.value === "road" ? "road" : "air");
              clearCoverage();
            }}
          >
            <option value="air">Kuş uçuşu</option>
            <option value="road" disabled={!roadAvailable}>
              Yol ağı · araç
            </option>
          </select>
        </label>
        {mode === "road" ? (
          <label>
            Sürüş süresi eşiği (dk)
            <input
              type="number"
              min="1"
              max="120"
              required
              value={minutes}
              disabled={busy}
              onChange={(event) => {
                setMinutes(event.target.value);
                clearCoverage();
              }}
            />
          </label>
        ) : (
          <label>
            Kapsama yarıçapı (m)
            <input
              type="number"
              min="50"
              max="10000"
              required
              value={meters}
              disabled={busy}
              onChange={(event) => {
                setMeters(event.target.value);
                clearCoverage();
              }}
            />
          </label>
        )}
        <button className="geo-focus" disabled={busy || !categories.length}>
          {busy ? "Hesaplanıyor…" : "Kapsamayı hesapla"}
        </button>
      </form>
      {mode === "road" && (
        <p>
          <a href="https://www.openstreetmap.org/copyright">
            © OpenStreetMap katkıda bulunanlar
          </a>{" "}
          · OSRM. Hane ve mevcut hizmet noktaları araç ağına bağlı varsayılır. Süre en yakın ağ noktaları arasında hesaplanır. Canlı trafik ve ekip çıkış süresi hariç.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {result?.threshold_m && (
        <p role="status">
          {result.service_locations?.length ?? 0} hizmet noktası. Yeşil ilk {result.threshold_m} m,
          sarı {result.threshold_m * 1.5} m’ye, kırmızı {result.threshold_m * 2} m’ye kadar.
          Sürüş süresi ve yol mesafesi için araç ağı kullanılır.
        </p>
      )}
      {result?.threshold_s && totals && (
        <>
          {result.source_url && (
            <p>
              {result.service_count} eşleştirilmiş istasyon ile kısmi kapsama.{" "}
              <a href={result.source_url}>Belediye istasyon listesi</a>
            </p>
          )}
          <p role="status">
            <strong>
              {totals.adequate.toLocaleString("tr-TR")} /{" "}
              {totals.households.toLocaleString("tr-TR")}
            </strong>{" "}
            hane eşik içinde. Eşik içindeki sentetik nüfus{" "}
            {totals.population.toLocaleString("tr-TR")}.
          </p>
          {totals.missing > 0 && (
            <p>
              <strong>
                {totals.missing.toLocaleString("tr-TR")} hanede{" "}
                {result.threshold_s
                  ? "sürüş süresi hesaplanamadı"
                  : "hizmet mesafesi hesaplanamadı"}
                .
              </strong>{" "}
              {result.threshold_s
                ? "Yol ağında bu haneler için geçerli bir rota bulunamadı."
                : "Seçili ilçede bu türde bir hizmet noktası bulunması gerekir."}
            </p>
          )}
          <p>
            Harita rengi, ölçümü olan hanelerin ne kadarının seçilen eşiğe
            girdiğini gösterir. Bir hizmet noktasının mahallede bulunması tek
            başına rengi belirlemez.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onCoverage({ ...result, bands });
            }}
          >
            <label>
              Sarı başlangıcı (%)
              <input
                type="number"
                min="1"
                max={bands[1] - 1}
                required
                value={bands[0]}
                onChange={(event) =>
                  setBands([event.target.valueAsNumber, bands[1]])
                }
              />
            </label>
            <label>
              Yeşil başlangıcı (%)
              <input
                type="number"
                min={bands[0] + 1}
                max="100"
                required
                value={bands[1]}
                onChange={(event) =>
                  setBands([bands[0], event.target.valueAsNumber])
                }
              />
            </label>
            <button className="geo-focus">Renk eşiklerini uygula</button>
          </form>
          <p>
            Alt eşiğin altı kırmızı, iki eşik arası sarı, üst eşikten itibaren
            yeşil. Veri olmayan mahalleler gri.
          </p>
          {showResults && (
            <div className="access-results">
              <table>
                <thead>
                  <tr>
                    <th>Mahalle</th>
                    <th>Eşik içi</th>
                    <th>Sınırda</th>
                    <th>Yetersiz</th>
                    <th>{result.threshold_s ? "Rota yok" : "Mesafe yok"}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.neighborhoods.map((row) => (
                    <tr key={row.id}>
                      <th scope="row">{row.name}</th>
                      <td>
                        {row.adequate}/{row.households}
                      </td>
                      <td>{row.borderline}</td>
                      <td>{row.insufficient}</td>
                      <td>{row.missing}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <details>
        <summary>Hane skoru eşikleri</summary>
        <p>
          Bu oturumda hane skorunu yeniden hesaplamak için metre cinsinden
          eşikleri uygulayın.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onThresholds(thresholds);
          }}
        >
          {Object.entries(defaults).map(([code, value]) => (
            <label key={code}>
              {categories.find((item) => item.code === code)?.name ?? code}
              <input
                type="number"
                min="50"
                max="10000"
                required
                value={thresholds[code] ?? value}
                onChange={(event) =>
                  setThresholds((previous) => ({
                    ...previous,
                    [code]: event.target.valueAsNumber,
                  }))
                }
              />
            </label>
          ))}
          <button className="geo-focus">Hane eşiklerini uygula</button>
          <button
            type="button"
            className="inventory-link"
            onClick={() => {
              setThresholds({});
              onThresholds({});
            }}
          >
            Varsayılanlara dön
          </button>
        </form>
      </details>
    </div>
  );
}
