"use client";

import { useEffect, useRef, useState } from "react";
import type { Coverage } from "./Accessibility";

type Change = Coverage["neighborhoods"][number] & {
  newly_covered: number;
  newly_covered_population: number;
  newly_measured: number;
  faster: number;
  saved_seconds: number;
  baseline_adequate: number;
  baseline_missing: number;
  paired_homes: number;
  before_m: number;
  after_m: number;
  score_weight: number;
  before_score: number;
  after_score: number;
};
type Result = Omit<Coverage, "neighborhoods"> & {
  neighborhoods: Change[];
  score_threshold_m: number;
};
type Recommendations = {
  evaluated: number;
  recommendations: {
    name: string; lon: number; lat: number; newly_covered: number;
    population: number; saved_seconds: number;
  }[];
};
const number = (value: number) =>
  value.toLocaleString("tr-TR", { maximumFractionDigits: 1 });

export default function InvestmentScenario({
  districtCode,
  point,
  onPick,
  onPoint,
  onCoverage,
  onClose,
}: {
  districtCode: string;
  point: [number, number] | null;
  onPick: () => void;
  onPoint: (point: [number, number]) => void;
  onCoverage: (value: Coverage | null) => void;
  onClose: () => void;
}) {
  const [category, setCategory] = useState("fire");
  const [minutes, setMinutes] = useState("10");
  const [result, setResult] = useState<Result | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<AbortController | null>(null);
  const recommendationRequest = useRef<AbortController | null>(null);
  useEffect(() => () => pending?.abort(), [pending]);
  useEffect(() => () => recommendationRequest.current?.abort(), []);
  useEffect(() => {
    setResult(null);
    setError("");
    setPending(null);
  }, [point]);
  function reset() {
    setResult(null);
    setError("");
    onCoverage(null);
  }
  async function calculate(event: React.FormEvent) {
    event.preventDefault();
    if (!point) return;
    const controller = new AbortController();
    setPending(controller);
    reset();
    try {
      const query = new URLSearchParams({
        lon: String(point[0]),
        lat: String(point[1]),
        minutes,
        category,
        district_code: districtCode,
      });
      const response = await fetch(`/api/v1/accessibility/scenario?${query}`, {
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail ?? "Senaryo hesaplanamadı.");
      if (!controller.signal.aborted) {
        setResult(data);
        onCoverage(data);
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(
          error instanceof Error ? error.message : "Senaryo hesaplanamadı.",
        );
    } finally {
      if (!controller.signal.aborted) setPending(null);
    }
  }
  async function recommend() {
    recommendationRequest.current?.abort();
    const controller = new AbortController();
    recommendationRequest.current = controller;
    setSearching(true);
    setError("");
    setRecommendations(null);
    try {
      const query = new URLSearchParams({ category, minutes, district_code: districtCode });
      const response = await fetch(`/api/v1/accessibility/recommendations?${query}`, {
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Bölge analizi alınamadı.");
      if (!controller.signal.aborted) setRecommendations(data);
    } catch (error) {
      if (!controller.signal.aborted) {
        setError(error instanceof Error ? error.message : "Bölge analizi alınamadı.");
      }
    } finally {
      if (recommendationRequest.current === controller && !controller.signal.aborted) {
        recommendationRequest.current = null;
        setSearching(false);
      }
    }
  }
  const totals = result?.neighborhoods.reduce(
    (sum, row) => ({
      before: sum.before + row.baseline_adequate,
      after: sum.after + row.adequate,
      people: sum.people + row.newly_covered_population,
      faster: sum.faster + row.faster,
      saved: sum.saved + row.saved_seconds,
      missing: sum.missing + row.missing,
      paired: sum.paired + row.paired_homes,
      beforeM: sum.beforeM + row.before_m,
      afterM: sum.afterM + row.after_m,
    }),
    {
      before: 0,
      after: 0,
      people: 0,
      faster: 0,
      saved: 0,
      missing: 0,
      paired: 0,
      beforeM: 0,
      afterM: 0,
    },
  );
  return (
    <section
      className="geo-details access-panel"
      aria-label="Yatırım senaryosu"
    >
      <button className="inventory-link" onClick={onClose}>
        Senaryoyu kapat
      </button>
      <h2>Yatırım senaryosu</h2>
      <p>
        Mevcut hizmet ağına bir aday nokta ekleyip tahmini sürüş süresini
        karşılaştırın. Mevcut yerleşimler araç ağına bağlı varsayılır.
      </p>
      <form onSubmit={calculate}>
        <label>
          Hizmet türü
          <select
            value={category}
            disabled={!!pending || searching}
            onChange={(event) => {
              setCategory(event.target.value);
              setRecommendations(null);
              reset();
            }}
          >
            <option value="fire">İtfaiye</option>
            <option value="hospital">Hastane</option>
            <option value="school">Okul</option>
            <option value="park">Park</option>
            <option value="bus">Otobüs durağı</option>
          </select>
        </label>
        <label>
          Sürüş eşiği (dk)
          <input
            type="number"
            min="1"
            max="120"
            required
            disabled={!!pending || searching}
            value={minutes}
            onChange={(event) => {
              setMinutes(event.target.value);
              setRecommendations(null);
              reset();
            }}
          />
        </label>
        <button
          type="button"
          className="geo-focus"
          disabled={!!pending || searching}
          onClick={onPick}
        >
          Haritadan aday nokta seç
        </button>
        <p role="status">
          {point
            ? `${point[1].toFixed(5)}° K · ${point[0].toFixed(5)}° D`
            : "Seçili ilçede bir nokta seçin."}
        </p>
        <button className="geo-focus" disabled={!point || !!pending || searching}>
          {pending ? "Hesaplanıyor…" : "Senaryoyu karşılaştır"}
        </button>
      </form>
      <details className="geo-source-details">
        <summary>Koordinatla aday nokta seç</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const values = new FormData(event.currentTarget);
            onPoint([
              Number(values.get("longitude")),
              Number(values.get("latitude")),
            ]);
          }}
        >
          <label>
            Enlem
            <input
              name="latitude"
              type="number"
              step="any"
              min="39"
              max="41"
              required
              disabled={!!pending || searching}
            />
          </label>
          <label>
            Boylam
            <input
              name="longitude"
              type="number"
              step="any"
              min="28"
              max="30"
              required
              disabled={!!pending || searching}
            />
          </label>
          <button className="geo-focus" disabled={!!pending || searching}>
            Koordinatı kullan
          </button>
        </form>
      </details>
      <form onSubmit={(event) => { event.preventDefault(); void recommend(); }}>
        <button className="geo-focus" disabled={searching || !!pending}>
          {searching ? "Bölgeler analiz ediliyor…" : "Yatırım bölgelerini öner"}
        </button>
      </form>
      {recommendations && (
        <section aria-label="Önerilen yatırım bölgeleri">
          <p>{recommendations.evaluated} yoğun mahallede birer aday nokta araç ağıyla değerlendirildi.</p>
          {recommendations.recommendations.length ? (
            <ol>
              {recommendations.recommendations.map((proposal) => (
                <li key={proposal.name}>
                  <strong>{proposal.name}</strong> · +{number(proposal.newly_covered)} hane,
                  {" "}{number(proposal.population)} kişi eşik içine giriyor.
                  {proposal.saved_seconds > 0 && <> Toplam {number(proposal.saved_seconds / 60)} dk kazanç.</>}
                  <button className="inventory-link" onClick={() => onPoint([proposal.lon, proposal.lat])}>
                    Aday olarak seç
                  </button>
                </li>
              ))}
            </ol>
          ) : <p>İncelenen adaylarda kapsama veya süre iyileşmesi bulunamadı.</p>}
        </section>
      )}
      {error && <p role="alert">{error}</p>}
      {result && totals && (
        <>
          <dl
            className="analysis-metrics"
            aria-label="Senaryo sonucu"
            aria-live="polite"
          >
            <div>
              <dt>Eşik içindeki hane</dt>
              <dd>
                {number(totals.before)} → {number(totals.after)}
              </dd>
            </div>
            <div
              className={
                totals.after > totals.before ? "positive-metric" : undefined
              }
            >
              <dt>Yeni kapsanan hane</dt>
              <dd>+{number(totals.after - totals.before)}</dd>
            </div>
            <div>
              <dt>Yeni kapsanan nüfus</dt>
              <dd>
                +{number(totals.people)} kişi
              </dd>
            </div>
            <div>
              <dt>Sürüş süresi kısalan hane</dt>
              <dd>{number(totals.faster)}</dd>
            </div>
          </dl>
          {totals.faster > 0 && (
            <p>
              Bu hanelerde ortalama {number(totals.saved / totals.faster / 60)}{" "}
              dakika kazanıldı.
            </p>
          )}
          {totals.after === totals.before && totals.faster === 0 && (
            <p>Bu aday, seçilen eşiğe yeni hane eklemiyor ve ölçülen sürüşleri kısaltmıyor.</p>
          )}
          {totals.paired > 0 && totals.beforeM !== totals.afterM && (
            <p>Ortalama araç yolu mesafesi {number(totals.beforeM / totals.paired / 1000)} → {number(totals.afterM / totals.paired / 1000)} km.</p>
          )}
          {totals.missing > 0 && <p>{number(totals.missing)} hane için yol ağı süre üretmedi.</p>}
          <div
            className="access-results"
            tabIndex={0}
            role="region"
            aria-label="Mahalle bazında senaryo sonuçları"
          >
            <table>
              <thead>
                <tr>
                  <th>Mahalle</th>
                  <th>Önce (hane)</th>
                  <th>Sonra (hane)</th>
                  <th>Yeni kapsama</th>
                  <th>Yeni kapsanan nüfus</th>
                </tr>
              </thead>
              <tbody>
                {result.neighborhoods
                  .filter((row) => row.newly_covered || row.faster)
                  .sort((a, b) => b.newly_covered - a.newly_covered)
                  .map((row) => (
                    <tr key={row.id}>
                      <th scope="row">{row.name}</th>
                      <td>{row.baseline_adequate}</td>
                      <td>{row.adequate}</td>
                      <td>{row.newly_covered}</td>
                      <td>{row.newly_covered_population}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
