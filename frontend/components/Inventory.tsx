"use client";
import type { CoverageRow } from "./Accessibility";
import { inventorySymbol } from "./inventory-symbols";
import RoadRoute, { type VehicleRoute } from "./RoadRoute";
import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  HeartPulse,
  Bus,
  GraduationCap,
  Trees,
  ShieldAlert,
  Landmark,
  Leaf,
  MapPin,
} from "lucide-react";
import type { Feature, FeatureCollection, Geometry } from "geojson";

export type RecordProperties = {
  id: string;
  analysisOnly?: boolean;
  kind: string;
  name: string;
  neighborhood: string;
  data_type: string;
  method: string;
  source_record_id: string;
  category_code?: string;
  category?: string;
  population?: number;
  use?: string;
  household_type?: string;
  household_count?: number;
  building_code?: string;
  floors?: number;
  capacity?: number | null;
  source?: { name: string; key: string; license: string };
};
export type RecordFeature = Feature<Geometry, RecordProperties>;
export type Detail = RecordFeature & {
  profile?: {
    children: number;
    adults: number;
    seniors: number;
    has_disability: boolean;
    income_band: string;
  };
  accessibility?: {
    score: number | null;
    coverage: { known: number; total: number };
    services: {
      category_code: string;
      threshold_m: number;
      weight: number;
      status: string;
    }[];
  };
  neighboring_services?: {
    id: string;
    name: string;
    category_code: string;
    district: string;
  }[];
  nearby?: {
    id: string;
    name: string;
    category: string;
    category_code: string;
    distance_m: number;
    data_type: string;
  }[];
};
type LayerItem = [label: string, kind?: string, category?: string];
const groups: {
  name: string;
  icon: typeof MapPin;
  color: string;
  items: LayerItem[];
}[] = [
  {
    name: "Konut ve yapılaşma",
    icon: Building2,
    color: "#f9cc73",
    items: [
      ["Karma kullanım binaları", "buildings", "mixed"],
      ["Konut binaları", "buildings", "residential"],
      ["Müstakil yapılar", "buildings", "detached"],
      ["İş merkezleri"],
      ["Ofisler", "companies"],
      ["Ticari yapılar"],
      ["İşletmeler", "businesses"],
    ],
  },
  {
    name: "Sağlık",
    icon: HeartPulse,
    color: "#f18ea1",
    items: [
      ["Hastaneler", "services", "hospital"],
      ["Aile sağlığı merkezleri", "services", "family_health"],
      ["Poliklinikler", "services", "polyclinic"],
      ["Eczaneler", "services", "pharmacy"],
      ["Acil sağlık noktaları"],
    ],
  },
  {
    name: "Ulaşım",
    icon: Bus,
    color: "#77b8f2",
    items: [
      ["Otobüs durakları", "services", "bus"],
      ["Raylı sistem (tür belirtilmemiş)", "services", "rail"],
      ["Metro istasyonları", "services", "metro"],
      ["Tramvay durakları"],
      ["Taksi durakları", "services", "taxi"],
      ["Taksi dolmuş noktaları"],
      ["Bisiklet yolları", "cycleways"],
      ["Otoparklar", "services", "parking"],
      ["Ana ulaşım yolları"],
    ],
  },
  {
    name: "Eğitim",
    icon: GraduationCap,
    color: "#bbadff",
    items: [
      ["Okullar (kademe belirtilmemiş)", "services", "school"],
      ["Anaokulları"],
      ["İlkokullar"],
      ["Ortaokullar"],
      ["Liseler"],
      ["Üniversiteler", "services", "university"],
      ["Halk eğitim merkezleri", "services", "adult_education"],
    ],
  },
  {
    name: "Sosyal yaşam",
    icon: Trees,
    color: "#88d7a0",
    items: [
      ["Parklar", "services", "park"],
      ["Yeşil alanlar"],
      ["Spor tesisleri", "services", "sports"],
      ["Kültür merkezleri", "services", "culture"],
      ["Kütüphaneler", "services", "library"],
      ["Sosyal tesisler", "services", "social_facility"],
      ["Yaşlı bakım merkezleri"],
    ],
  },
  {
    name: "Acil durum",
    icon: ShieldAlert,
    color: "#f3a37c",
    items: [
      ["Acil toplanma alanları", "services", "assembly"],
      ["İtfaiye noktaları", "services", "fire"],
      ["Acil müdahale noktaları", "services", "emergency_aid"],
      ["Hastaneler", "services", "hospital"],
      ["Afet destek alanları"],
    ],
  },
  {
    name: "Kamu hizmetleri",
    icon: Landmark,
    color: "#81dfd9",
    items: [
      ["Belediye hizmet noktaları", "services", "municipal"],
      ["Belediye hizmet binaları"],
      ["Muhtarlıklar", "services", "local_office"],
      ["Kamu kurumları"],
      ["Zabıta noktaları"],
      ["Diğer belediye hizmet noktaları"],
    ],
  },
  {
    name: "Çevre ve altyapı",
    icon: Leaf,
    color: "#c9dc83",
    items: [
      ["Atık toplama noktaları", "services", "waste_collection"],
      ["Geri dönüşüm noktaları", "services", "recycling"],
      ["Su ve kanalizasyon altyapısı"],
      ["Çevresel risk alanları"],
      ["Gürültü veya hava kalitesi ölçüm noktaları", "services", "air_monitor"],
    ],
  },
];

const layerKey = (kind: string, category?: string) =>
  category ? `${kind}:${category}` : kind;
const colors = new Map(
  groups.flatMap((group) =>
    group.items.flatMap(([, kind, category]) =>
      kind ? [[layerKey(kind, category), group.color] as const] : [],
    ),
  ),
);
colors.set("services:hospital", "#f18ea1");
export type InventoryProperties = RecordProperties & { color?: string };
export type InventoryCollection = FeatureCollection<
  Geometry,
  InventoryProperties
>;

async function readInventory<T>(
  route: string,
  params: URLSearchParams,
  signal?: AbortSignal,
): Promise<T> {
  const result = await fetch(`/api/v1/inventory/${route}?${params}`, {
    signal,
  });
  if (!result.ok) throw new Error("Envanter verisi yüklenemedi.");
  return result.json();
}

export function useInventory(
  active: boolean,
  districtCode: string,
  neighborhood: string | undefined,
  thresholds: Record<string, number>,
) {
  const [enabled, setEnabled] = useState<string[]>(["buildings:mixed", "buildings:residential", "buildings:detached"]);
  const [loaded, setLoaded] = useState<{
    scope: string;
    area: string;
    data: InventoryCollection;
  } | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<{ kind: string; id: string } | null>(
    null,
  );
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailError, setDetailError] = useState("");
  const [retry, setRetry] = useState(0);
  const area = JSON.stringify([districtCode, neighborhood]);
  const scope = JSON.stringify([area, enabled, retry]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    setError("");
    Promise.allSettled(
      enabled.map(async (key) => {
        const [kind, category] = key.split(":");
        const params = new URLSearchParams({
          kind,
          district_code: districtCode,
        });
        if (category) params.set("category", category);
        if (neighborhood) params.set("neighborhood", neighborhood);
        const data = await readInventory<InventoryCollection>(
          "features",
          params,
          controller.signal,
        );
        return data.features.map((item) => ({
          ...item,
          properties: {
            ...item.properties,
            color: colors.get(key) || "#f9cc73",
          },
        }));
      }),
    ).then((results) => {
      if (!controller.signal.aborted)
        setLoaded({
          scope,
          area,
          data: {
            type: "FeatureCollection",
            features: results.flatMap((result) =>
              result.status === "fulfilled" ? result.value : [],
            ),
          },
        });
      if (
        !controller.signal.aborted &&
        results.some((result) => result.status === "rejected")
      ) {
        setError("Bazı katmanlar yüklenemedi.");
      }
    });
    return () => controller.abort();
  }, [active, area, districtCode, enabled, neighborhood, scope]);
  useEffect(() => {
    if (!active || !chosen) return;
    const controller = new AbortController();
    const params = new URLSearchParams(chosen);
    if (chosen.kind === "households") {
      for (const [category, meters] of Object.entries(thresholds))
        params.append("threshold", `${category}:${meters}`);
    }
    readInventory<Detail>("detail", params, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setDetail(result);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setDetailError("Kayıt detayı yüklenemedi.");
      });
    return () => controller.abort();
  }, [active, chosen, thresholds]);
  const visible = useMemo(() => {
    if (!active || loaded?.area !== area) return undefined;
    const activeKeys = new Set(enabled);
    return {
      ...loaded.data,
      features: loaded.data.features.filter(({ properties }) =>
        activeKeys.has(properties.kind) ||
        activeKeys.has(layerKey(properties.kind, properties.category_code ?? properties.use)),
      ),
    };
  }, [active, area, enabled, loaded]);
  const filtered = useMemo(() => {
    if (!visible || !query.trim()) return visible;
    const term = query.trim().toLocaleLowerCase("tr");
    return {
      ...visible,
      features: visible.features.filter(({ properties: p }) =>
        `${p.name} ${p.source_record_id} ${p.neighborhood}`
          .toLocaleLowerCase("tr")
          .includes(term),
      ),
    };
  }, [visible, query]);
  function select(kind: string, id: string) {
    setDetail(null);
    setDetailError("");
    setChosen({ kind, id });
  }
  function close() {
    setChosen(null);
    setDetail(null);
    setDetailError("");
  }
  function toggle(key: string) {
    setEnabled((items) =>
      items.includes(key)
        ? items.filter((item) => item !== key)
        : [...items, key],
    );
    close();
  }
  function toggleGroup(keys: string[]) {
    setEnabled((items) => keys.every((key) => items.includes(key))
      ? items.filter((key) => !keys.includes(key))
      : [...new Set([...items, ...keys])]);
    close();
  }
  return {
    enabled,
    toggleGroup,
    toggle,
    query,
    setQuery,
    filtered,
    chosen,
    detail,
    detailError,
    select,
    close,
    error,
    loading: active && loaded?.scope !== scope && !error,
    retry: () => setRetry((n) => n + 1),
  };
}

export type InventoryState = ReturnType<typeof useInventory>;

export function InventoryLayers({
  state,
  districtActive,
  baseLayers,
  baseAllSelected,
  toggleBaseLayers,
  neighborhood,
  clearNeighborhood,
}: {
  state: InventoryState;
  districtActive: boolean;
  baseLayers: React.ReactNode;
  baseAllSelected: boolean;
  toggleBaseLayers: () => void;
  neighborhood?: string;
  clearNeighborhood: () => void;
}) {
  const [activeTab, setActiveTab] = useState(1);
  const tab = districtActive ? activeTab : 0;
  const group = groups[tab - 1];
  const keys = group?.items.flatMap(([, kind, category]) =>
    kind ? [layerKey(kind, category)] : [],
  ) ?? [];
  const allSelected = tab === 0 ? baseAllSelected : keys.every((key) => state.enabled.includes(key));
  const tabs = districtActive
    ? ["Harita", ...groups.map((item) => item.name)]
    : ["Harita"];
  const results = state.filtered?.features ?? [];
  const homes = results.filter((item) => item.properties.kind === "buildings");
  const households = homes.reduce((sum, item) => sum + (item.properties.household_count ?? 0), 0);
  const people = homes.reduce(
    (sum, item) => sum + (item.properties.population ?? 0),
    0,
  );
  return (
    <section
      className="inventory-layers map-layer-toolbar"
      aria-label="Harita katmanları"
    >
      <div className="map-layer-toolbar-header">
        <h2>Harita katmanları</h2>
        {districtActive && neighborhood && (
          <button className="inventory-link" onClick={clearNeighborhood}>
            Tüm ilçe kayıtlarını göster
          </button>
        )}
      </div>
      <div
        className="map-layer-tabs"
        role="tablist"
        aria-label="Katman kategorileri"
      >
        {tabs.map((name, index) => (
          <button
            type="button"
            role="tab"
            key={name}
            id={`layer-tab-${index}`}
            aria-controls="layer-options"
            aria-selected={tab === index}
            tabIndex={tab === index ? 0 : -1}
            onClick={() => setActiveTab(index)}
            onKeyDown={(event) => {
              const next = {
                ArrowRight: (index + 1) % tabs.length,
                ArrowLeft: (index + tabs.length - 1) % tabs.length,
                Home: 0,
                End: tabs.length - 1,
              }[event.key];
              if (next === undefined) return;
              event.preventDefault();
              setActiveTab(next);
              document.getElementById(`layer-tab-${next}`)?.focus();
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <div
        id="layer-options"
        role="tabpanel"
        aria-labelledby={`layer-tab-${tab}`}
        tabIndex={0}
        className="map-layer-options"
      >
        <button
          type="button"
          className="inventory-link map-layer-select-all"
          onClick={() => tab === 0 ? toggleBaseLayers() : state.toggleGroup(keys)}
        >
          {allSelected ? "Tüm seçimi kaldır" : "Tümünü seç"}
        </button>
        {tab === 0 ? (
          baseLayers
        ) : (
          <>
            {group?.items.map(([name, kind, category]) => {
              const key = layerKey(kind || "", category);
              return (
                <label key={name} className="inventory-toggle">
                  <input
                    type="checkbox"
                    disabled={!kind}
                    checked={!!kind && state.enabled.includes(key)}
                    onChange={() => state.toggle(key)}
                  />
                  <span>
                    {kind && (
                      <span aria-hidden="true">
                        {inventorySymbol(kind, category)[0]}{" "}
                      </span>
                    )}
                    {name}
                    <small>
                      {category === "university"
                        ? "Gerçek · BUÜ yerleşke kaynağı"
                        : kind
                          ? "Sentetik · demo-seed-v1"
                          : "Bu tür için veri yok"}
                    </small>
                  </span>
                </label>
              );
            })}
          </>
        )}
      </div>
      {districtActive && homes.length > 0 && (
        <p className="map-household-count">
          <strong>{homes.length.toLocaleString("tr-TR")} bina · {households.toLocaleString("tr-TR")} hane</strong>
          {" · "}
          {people.toLocaleString("tr-TR")} sentetik nüfus
        </p>
      )}
      {districtActive && (
        <details
          className="map-layer-search"
          onToggle={(event) => {
            if (!event.currentTarget.open) state.setQuery("");
          }}
        >
          <summary>
            Envanterde ara · {results.length.toLocaleString("tr-TR")} kayıt
          </summary>
          <label className="search inventory-search">
            <input
              aria-label="Envanterde ara"
              value={state.query}
              placeholder="Envanterde ara…"
              onChange={(event) => state.setQuery(event.target.value)}
            />
          </label>
          {state.query.trim() && (
            <div className="inventory-results">
              {results.slice(0, 12).map((item) => (
                <button
                  key={item.properties.id}
                  className="geo-place"
                  onClick={() =>
                    state.select(item.properties.kind, item.properties.id)
                  }
                >
                  <MapPin size={13} />
                  {item.properties.name}
                </button>
              ))}
              {results.length > 12 && (
                <p>İlk 12 sonuç gösteriliyor. Aramayı daraltabilirsiniz.</p>
              )}
            </div>
          )}
        </details>
      )}
      {districtActive && state.loading && (
        <p role="status">Katmanlar yükleniyor…</p>
      )}
      {districtActive && state.error && (
        <p role="alert">
          {state.error}{" "}
          <button className="inventory-link" onClick={state.retry}>
            Yeniden dene
          </button>
        </p>
      )}
    </section>
  );
}

const householdTypes: Record<string, string> = {
  single: "Tek kişilik",
  with_children: "Çocuklu",
  adults: "Çocuksuz",
};
const incomeBands: Record<string, string> = {
  low: "Düşük",
  middle: "Orta",
  high: "Yüksek",
};

export function InventoryDetail({
  state,
  onRoute,
  neighborhoodCoverage,
}: {
  state: InventoryState;
  neighborhoodCoverage?: CoverageRow;
  onRoute: (route: VehicleRoute | null) => void;
}) {
  const record = state.detail;
  const p = record?.properties;
  const profile = record?.profile;
  const panelTitle =
    state.chosen?.kind === "households" ? "Hane bilgisi" : "Kayıt bilgisi";
  return (
    <section
      className="geo-details inventory-detail inventory-map-panel"
      aria-label={panelTitle}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          state.close();
        }
      }}
    >
      <header className="inventory-panel-header">
        <strong>{panelTitle}</strong>
        <button className="inventory-link" onClick={state.close}>
          Detayı kapat
        </button>
      </header>
      {!p ? (
        <p role={state.detailError ? "alert" : "status"}>
          {state.detailError || "Kayıt yükleniyor…"}
        </p>
      ) : (
        <>
          <h2>
            <span aria-hidden="true">
              {inventorySymbol(p.kind, p.category_code)[0]}
            </span>{" "}
            {p.name}
          </h2>
          <span className="pill">{p.data_type}</span>
          <dl>
            <div>
              <dt>Mahalle</dt>
              <dd>{p.neighborhood}</dd>
            </div>
            {p.building_code && (
              <div>
                <dt>Bina</dt>
                <dd>{p.building_code}</dd>
              </div>
            )}
            {p.population !== undefined && (
              <div>
                <dt>{p.kind === "buildings" ? "Bina nüfusu" : "Hane nüfusu"}</dt>
                <dd>{p.population}</dd>
              </div>
            )}
            {p.household_count !== undefined && (
              <div><dt>Hane sayısı</dt><dd>{p.household_count}</dd></div>
            )}
            {p.household_type && (
              <div>
                <dt>Hane tipi</dt>
                <dd>{householdTypes[p.household_type] || p.household_type}</dd>
              </div>
            )}
            {p.use && (
              <div>
                <dt>Kullanım</dt>
                <dd>
                  {{
                    mixed: "Karma",
                    residential: "Konut",
                    detached: "Müstakil",
                  }[p.use] || p.use}
                </dd>
              </div>
            )}
            {p.floors !== undefined && (
              <div>
                <dt>Kat</dt>
                <dd>{p.floors}</dd>
              </div>
            )}
            {p.category && (
              <div>
                <dt>Kategori</dt>
                <dd>{p.category}</dd>
              </div>
            )}
            {p.kind === "services" && (
              <div>
                <dt>Kapasite</dt>
                <dd>{p.capacity ?? "Belirtilmemiş"}</dd>
              </div>
            )}
            {profile && (
              <>
                <div>
                  <dt>Çocuk / yetişkin / yaşlı</dt>
                  <dd>
                    {profile.children} / {profile.adults} / {profile.seniors}
                  </dd>
                </div>
                <div>
                  <dt>Engelli birey</dt>
                  <dd>{profile.has_disability ? "Var" : "Yok"}</dd>
                </div>
                <div>
                  <dt>Gelir grubu</dt>
                  <dd>{incomeBands[profile.income_band]}</dd>
                </div>
              </>
            )}
            <div>
              <dt>Kaynak</dt>
              <dd>{p.source?.name}</dd>
            </div>
            <div>
              <dt>Kaynak kimliği</dt>
              <dd>{p.source_record_id}</dd>
            </div>
          </dl>
          {neighborhoodCoverage &&
            (() => {
              const { adequate, households, missing } = neighborhoodCoverage;
              const measured = households - missing;
              return (
                <p>
                  <strong>Mahalle kapsaması</strong>
                  <br />
                  {measured > 0
                    ? `${adequate.toLocaleString("tr-TR")} / ${measured.toLocaleString("tr-TR")} ölçülen hane eşik içinde (%${((100 * adequate) / measured).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}).`
                    : "Bu mahallede ölçülen hane yok."}
                  {missing > 0 &&
                    ` ${missing.toLocaleString("tr-TR")} hane için ölçüm alınamadı.`}
                </p>
              );
            })()}
          <p>{p.method}</p>
          {record?.nearby && (
            <>
              {record.accessibility && (
                <>
                  <h3>
                    Demo erişilebilirlik skoru:{" "}
                    {record.accessibility.score ?? "—"} / 100
                  </h3>
                  <p>
                    {record.accessibility.coverage.known}/
                    {record.accessibility.coverage.total} ölçüt · Kuş uçuşu ·
                    Süre verisi yok
                  </p>
                </>
              )}
              <RoadRoute
                key={p.id}
                household={p.id}
                services={record.nearby}
                neighboringServices={record.neighboring_services ?? []}
                onRoute={onRoute}
              />
              <h3>Kategoriye göre kuş uçuşu en yakın hizmet</h3>
              <ul className="inventory-nearby">
                {record.nearby.map((service) => (
                  <li key={service.id}>
                    <button
                      className="inventory-link"
                      onClick={() => state.select("services", service.id)}
                    >
                      {service.name}
                    </button>
                    <small>
                      {service.distance_m.toLocaleString("tr-TR", {
                        maximumFractionDigits: 0,
                      })}{" "}
                      m · {service.data_type}
                    </small>
                    {record.accessibility?.services
                      .filter(
                        (rule) => rule.category_code === service.category_code,
                      )
                      .map((rule) => (
                        <small key={rule.category_code}>
                          Eşik {rule.threshold_m} m · Ağırlık {rule.weight} ·{" "}
                          {
                            (
                              {
                                adequate: "Uygun",
                                borderline: "Sınırda",
                                insufficient: "Yetersiz",
                              } as Record<string, string>
                            )[rule.status]
                          }
                        </small>
                      ))}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
