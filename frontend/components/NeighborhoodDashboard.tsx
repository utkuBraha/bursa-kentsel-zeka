"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { Coverage } from "./Accessibility";

type Row = {
  id: string;
  name: string;
  area_km2: number;
  households: number;
  population: number | null;
  buildings: number;
  services: number;
};
type ServiceCount = {
  neighborhood_id: string;
  code: string;
  name: string;
  count: number;
};
type Summary = { neighborhoods: Row[]; service_categories: ServiceCount[] };
const format = (value: number | null | undefined) =>
  value?.toLocaleString("tr-TR") ?? "—";

export default function NeighborhoodDashboard({
  districtCode,
  districtName,
  selected,
  onSelect,
  onClear,
  coverage,
  controls,
}: {
  districtCode: string;
  districtName: string;
  selected?: string;
  onSelect: (id: string) => void;
  onClear: () => void;
  coverage: Coverage | null;
  controls: ReactNode;
}) {
  const [summary, setSummary] = useState<Summary>();
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/v1/dashboard/summary?district_code=${districtCode}`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw Error();
        return response.json();
      })
      .then(setSummary)
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, [districtCode]);
  const rows = summary?.neighborhoods;
  const scope = rows?.filter((row) => !selected || row.id === selected);
  const coverageById = new Map(
    coverage?.neighborhoods.map((row) => [row.id, row]),
  );
  const totals = scope?.reduce(
    (sum, row) => ({
      area: sum.area + row.area_km2,
      households: sum.households + row.households,
      population: sum.population + (row.population ?? 0),
      buildings: sum.buildings + row.buildings,
      services: sum.services + row.services,
      adequate: sum.adequate + (coverageById.get(row.id)?.adequate ?? 0),
      measured:
        sum.measured +
        (coverageById.has(row.id)
          ? row.households - (coverageById.get(row.id)?.missing ?? 0)
          : 0),
    }),
    {
      area: 0,
      households: 0,
      population: 0,
      buildings: 0,
      services: 0,
      adequate: 0,
      measured: 0,
    },
  );
  const distribution = new Map<string, { name: string; count: number }>();
  for (const item of summary?.service_categories ?? []) {
    if (selected && item.neighborhood_id !== selected) continue;
    distribution.set(item.code, {
      name: item.name,
      count: (distribution.get(item.code)?.count ?? 0) + item.count,
    });
  }
  const categories = [...distribution.values()].sort(
    (a, b) => b.count - a.count,
  );
  return (
    <section
      className="geo-details access-panel"
      aria-label="Mahalle karşılaştırması"
    >
      <h2>Mahalle karşılaştırması</h2>
      <p>{districtName} demo envanteri. Hane ve nüfus değerleri sentetiktir.</p>
      <details>
        <summary>Kapsama hesabını ayarla</summary>
        {controls}
      </details>
      {error ? (
        <p role="alert">Mahalle özeti yüklenemedi.</p>
      ) : !rows ? (
        <p role="status">Özet yükleniyor…</p>
      ) : (
        <>
          <h3>
            {scope?.length === 1 ? scope[0].name : `${districtName} geneli`}
          </h3>
          {selected && (
            <button className="inventory-link" onClick={onClear}>
              Tüm ilçeyi göster
            </button>
          )}
          {totals && (
            <dl>
              <div>
                <dt>Hane</dt>
                <dd>{format(totals.households)}</dd>
              </div>
              <div>
                <dt>Sentetik nüfus</dt>
                <dd>
                  {format(
                    scope?.some((row) => row.population !== null)
                      ? totals.population
                      : null,
                  )}
                </dd>
              </div>
              <div>
                <dt>Sentetik örneklem yoğunluğu</dt>
                <dd>
                  {format(
                    totals.area > 0
                      ? Math.round((10 * totals.population) / totals.area) / 10
                      : null,
                  )}{" "}
                  kişi/km²
                </dd>
              </div>
              <div>
                <dt>Bina</dt>
                <dd>{format(totals.buildings)}</dd>
              </div>
              <div>
                <dt>Hizmet noktası</dt>
                <dd>{format(totals.services)}</dd>
              </div>
              {coverage && (
                <>
                  <div>
                    <dt>Eşik içindeki hane</dt>
                    <dd>
                      {format(totals.adequate)} / {format(totals.households)}
                    </dd>
                  </div>
                  <div>
                    <dt>Ölçüm bulunan hane</dt>
                    <dd>
                      {format(totals.measured)} / {format(totals.households)}
                    </dd>
                  </div>
                </>
              )}
            </dl>
          )}
          {coverage && (
            <p>
              {coverage.threshold_s
                ? `Araçla ${coverage.threshold_s / 60} dk`
                : `Kuş uçuşu ${coverage.threshold_m} m`}
              .
              {coverage.source_url && (
                <>
                  {" "}
                  Kısmi istasyon kümesi.{" "}
                  <a href={coverage.source_url}>İstasyon kaynağı</a>
                </>
              )}
            </p>
          )}
          <div
            className="access-results"
            tabIndex={0}
            role="region"
            aria-label="Mahalle göstergeleri"
          >
            <table>
              <thead>
                <tr>
                  <th>Mahalle</th>
                  <th>Hane</th>
                  <th>Sentetik nüfus</th>
                  <th>Sentetik kişi/km²</th>
                  <th>Bina</th>
                  <th>Hizmet</th>
                  {coverage && (
                    <>
                      <th>Eşik içi</th>
                      <th>Ölçüm</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const result = coverageById.get(row.id);
                  return (
                    <tr
                      key={row.id}
                      className={
                        selected === row.id ? "dashboard-selected" : undefined
                      }
                    >
                      <th scope="row">
                        <button
                          className="inventory-link"
                          aria-pressed={selected === row.id}
                          onClick={() => onSelect(row.id)}
                        >
                          {row.name}
                        </button>
                      </th>
                      <td>{format(row.households)}</td>
                      <td>{format(row.population)}</td>
                      <td>
                        {format(
                          row.area_km2 > 0 && row.population !== null
                            ? Math.round((10 * row.population) / row.area_km2) /
                                10
                            : null,
                        )}
                      </td>
                      <td>{format(row.buildings)}</td>
                      <td>{format(row.services)}</td>
                      {coverage && (
                        <>
                          <td>{format(result?.adequate)}</td>
                          <td>
                            {format(
                              result
                                ? result.households - result.missing
                                : null,
                            )}
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <details open>
            <summary>Hizmet türü dağılımı</summary>
            {categories.length ? (
              <ul className="dashboard-bars">
                {categories.map((item) => (
                  <li key={item.name}>
                    <span>{item.name}</span>
                    <strong>{format(item.count)}</strong>
                    <meter
                      min={0}
                      max={categories[0].count}
                      value={item.count}
                      aria-label={item.name}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <p>Bu alanda hizmet kaydı yok.</p>
            )}
          </details>
        </>
      )}
    </section>
  );
}
