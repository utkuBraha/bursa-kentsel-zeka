"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowUpRight,
  Check,
  ChevronRight,
  Database,
  Layers3,
  Map,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  TriangleAlert,
  X,
  Crosshair,
  SlidersHorizontal,
} from "lucide-react";
import {
  InventoryDetail,
  InventoryLayers,
  useInventory,
} from "../components/Inventory";
import type { VehicleRoute } from "../components/RoadRoute";
import InvestmentScenario from "../components/InvestmentScenario";
import NeighborhoodDashboard from "../components/NeighborhoodDashboard";
import Accessibility, {
  coverageColors,
  type Coverage,
} from "../components/Accessibility";
import type { Collection, Place } from "../components/CityMap";
type Development = { districts: Record<string, number>; neighborhoods: Record<string, number> };
const CityMap = dynamic(() => import("../components/CityMap"), {
  ssr: false,
  loading: () => <div className="geo-start">Harita motoru yükleniyor…</div>,
});
function title(s: string) {
  return s
    .toLocaleLowerCase("tr")
    .replace(/(^|\s)\S/g, (c) => c.toLocaleUpperCase("tr"));
}
export default function Home() {
  const [districts, setDistricts] = useState<Collection | null>(null),
    [neighborhoods, setNeighborhoods] = useState<Collection | null>(null),
    [mode, setMode] = useState<"bursa" | "district">("bursa"),
    [selected, setSelected] = useState<Place | null>(null),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(true),
    [nBusy, setNBusy] = useState(false),
    [error, setError] = useState(""),
    [nError, setNError] = useState(""),
    [showDistricts, setShowDistricts] = useState(true),
    [showNeighborhoods, setShowNeighborhoods] = useState(true),
    [showLabels, setShowLabels] = useState(true),
    [showBase, setShowBase] = useState(false),
    [focus, setFocus] = useState(0),
    [sources, setSources] = useState(false),
    [ready, setReady] = useState(false),
    [retry, setRetry] = useState(0);
  const [development, setDevelopment] = useState<Development | null>(null);
  const [developmentError, setDevelopmentError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/dashboard/development", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Gösterge alınamadı.");
        return response.json();
      })
      .then(setDevelopment)
      .catch(() => {
        if (!controller.signal.aborted) setDevelopmentError(true);
      });
    return () => controller.abort();
  }, []);
  const [districtCode, setDistrictCode] = useState("1829");
  const district = districts?.features.find(
    (f) => f.properties.code === districtCode,
  );
  const districtName = title(district?.properties.name ?? "Nilüfer");
  const [inventoryNeighborhood, setInventoryNeighborhood] = useState<string>();
  const [vehicleRoute, setVehicleRoute] = useState<VehicleRoute | null>(null);
  const [scenario, setScenario] = useState(false);
  const [candidate, setCandidate] = useState<[number, number] | null>(null);
  const [picking, setPicking] = useState(false);
  function closeScenario() {
    setScenario(false);
    setPicking(false);
    setCandidate(null);
    setCoverage(null);
  }
  function openScenario() {
    inventory.close();
    setAnalysis(false);
    setDashboard(false);
    setCoverage(null);
    setMode("district");
    setShowNeighborhoods(true);
    setScenario(true);
  }
  const [analysis, setAnalysis] = useState(false);
  const [dashboard, setDashboard] = useState(false);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [thresholds, setThresholds] = useState<Record<string, number>>({});
  const inventory = useInventory(
    mode === "district",
    districtCode,
    inventoryNeighborhood,
    thresholds,
  );
  useEffect(() => {
    setVehicleRoute(null);
  }, [mode, districtCode, inventory.chosen]);
  function openAnalysis() {
    if (scenario) closeScenario();
    setDashboard(false);
    inventory.close();
    setMode("district");
    setShowNeighborhoods(true);
    setAnalysis(true);
  }
  async function load() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/geography/districts/geojson");
      if (!response.ok)
        throw Error(
          "Coğrafi veri servisine erişilemiyor. Lütfen yeniden deneyin.",
        );
      const d = await response.json();
      setDistricts(d);
      if (!d.features.length)
        setError("İlçe geometrisi bulunamadı. Veri aktarımını kontrol edin.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Veri yüklenemedi.");
      setDistricts(null);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (mode !== "district") return;
    const controller = new AbortController();
    setNBusy(true);
    setNError("");
    setNeighborhoods(null);
    fetch(
      `/api/v1/geography/neighborhoods?district_code=${districtCode}&limit=500`,
      { signal: controller.signal },
    )
      .then(async (r) => {
        if (!r.ok) throw Error("İlçe mahalleleri yüklenemedi.");
        return r.json();
      })
      .then((d) => setNeighborhoods(d))
      .catch((e) => {
        if (e.name !== "AbortError") setNError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setNBusy(false);
      });
    return () => controller.abort();
  }, [mode, retry, districtCode]);
  useEffect(() => {
    if (!sources) return;
    function close(e: KeyboardEvent) {
      if (e.key === "Escape") setSources(false);
    }
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [sources]);
  const select = (feature: Place, kind: "district" | "neighborhood") => {
    inventory.close();
    setInventoryNeighborhood(
      kind === "neighborhood" ? feature.properties.id : undefined,
    );
    setSelected(feature);
    if (kind === "district") {
      if (feature.properties.code !== districtCode) {
        setCoverage(null);
        setCandidate(null);
        setPicking(false);
        setNeighborhoods(null);
      }
      setDistrictCode(feature.properties.code);
      setMode("district");
      setQuery("");
      setShowNeighborhoods(true);
    } else {
      setFocus((x) => x + 1);
    }
  };
  function back() {
    closeScenario();
    setDashboard(false);
    setAnalysis(false);
    setCoverage(null);
    inventory.close();
    setInventoryNeighborhood(undefined);
    setMode("bursa");
    setNBusy(false);
    setNError("");
    setNeighborhoods(null);
    setSelected(null);
    setQuery("");
  }
  const populationScope =
    mode === "district"
      ? district
        ? [district]
        : undefined
      : districts?.features;
  const officialPopulation = populationScope?.reduce(
    (sum, feature) => sum + (feature.properties.population_2025 ?? 0),
    0,
  );
  const syntheticPopulation = populationScope?.every(
    (feature) => feature.properties.synthetic_population !== undefined,
  )
    ? populationScope.reduce(
        (sum, feature) => sum + (feature.properties.synthetic_population ?? 0),
        0,
      )
    : undefined;
  const current = mode === "bursa" ? districts : neighborhoods;
  const filtered = (current?.features || []).filter((f) =>
    f.properties.name
      .toLocaleLowerCase("tr")
      .includes(query.toLocaleLowerCase("tr")),
  );
  const p = (selected ?? (mode === "district" ? district : undefined))
    ?.properties;
  const cityView = !scenario && !dashboard && !analysis;
  const developmentScores = useMemo(() => {
    if (!development) return undefined;
    if (mode === "bursa") return development.districts;
    return Object.fromEntries((neighborhoods?.features ?? []).flatMap(({ properties }) => {
      const score = development.neighborhoods[properties.id];
      return score === undefined ? [] : [[properties.id, score]];
    }));
  }, [development, mode, neighborhoods]);
  const rankedAreas = [...(current?.features ?? [])].sort(
    (a, b) => (developmentScores?.[b.properties.id] ?? -1) - (developmentScores?.[a.properties.id] ?? -1),
  );
  const baseAllSelected = showDistricts && showLabels && showBase &&
    (mode === "bursa" || showNeighborhoods);
  const panelTitle = scenario
    ? "Yatırım senaryosu"
    : dashboard
      ? "Mahalle analizi"
      : analysis
        ? "Hizmet erişimi"
        : "Kent haritası";
  function chooseCandidate(point: [number, number]) {
    setCandidate(point);
    setPicking(false);
    setCoverage(null);
  }
  function scrollToMap() {
    document
      .getElementById("kent-haritasi")
      ?.focus({ preventScroll: true });
  }
  return (
    <div className="shell geo-shell">
      <header className="civic-masthead">
        <a className="brand" href="/">
          <span className="brand-icon">
            <Layers3 size={23} />
          </span>
          <span>
            Bursa Kentsel Zekâ<small>Kentsel karar destek platformu</small>
          </span>
        </a>
        <button
          className="civic-data-button"
          aria-expanded={sources}
          aria-haspopup="dialog"
          onClick={() => setSources(true)}
        >
          <Database size={17} />
          Veri yönetimi
        </button>
      </header>
      <main>
        <header className="topbar">
          <div>
            <button className="geo-crumb" onClick={back}>
              Bursa
            </button>
            <ChevronRight size={14} />
            <strong>{mode === "bursa" ? "İlçe haritası" : districtName}</strong>
            {mode === "district" && (
              <>
                <ChevronRight size={14} />
                <span>Mahalleler</span>
              </>
            )}
          </div>
        </header>
        <div className="geo-content">
          <section className="geo-heading">
            <div>
              <h1>
                {mode === "bursa"
                  ? "Bursa ilçe haritası"
                  : `${districtName} mahalleleri`}
              </h1>
            </div>
            <div className="geo-actions">
              {mode === "district" && (
                <button className="refresh" onClick={back}>
                  <ArrowLeft size={15} />
                  Bursa’ya dön
                </button>
              )}
              <button
                className="refresh"
                disabled={busy || nBusy}
                onClick={() => {
                  void load();
                  if (mode === "district") setRetry((x) => x + 1);
                }}
                aria-label="Verileri yenile"
              >
                <RefreshCw size={15} />
                Yenile
              </button>
            </div>
          </section>
          <div className="geo-summary">
            <span>
              <i className="legend-dot district-color" />
              <strong>{districts?.total ?? "—"}</strong> ilçe
            </span>
            {mode === "district" && (
              <span>
                <i className="legend-dot neighborhood-color" />
                <strong>{neighborhoods?.total ?? "—"}</strong> mahalle
              </span>
            )}
            <span>
              <strong>
                {officialPopulation?.toLocaleString("tr-TR") ?? "—"}
              </strong>{" "}
              {mode === "district" ? "ilçe" : "Bursa"} resmî nüfusu (2025)
            </span>
            <span>
              <strong>
                {syntheticPopulation?.toLocaleString("tr-TR") ?? "—"}
              </strong>{" "}
              sentetik nüfus
            </span>
            <span className="geo-real">
              <Check size={12} />
              Resmî sınırlar ve analiz alanları
            </span>
          </div>
          <div className="geo-work-area">
            <div className="geo-navigation">
              <label htmlFor="district-select">İlçe seç</label>
              <select
                id="district-select"
                value={mode === "district" ? districtCode : ""}
                disabled={!districts?.features.length}
                onChange={(event) => {
                  const next = districts?.features.find(
                    (f) => f.properties.code === event.target.value,
                  );
                  if (next) select(next, "district");
                  else back();
                }}
              >
                <option value="">Bursa geneli</option>
                {districts?.features.map((f) => (
                  <option key={f.properties.code} value={f.properties.code}>
                    {title(f.properties.name)}
                  </option>
                ))}
              </select>
              <a
                className="geo-skip"
                href="#bolgeler"
                onClick={(event) => {
                  if (!window.matchMedia("(min-width: 850px)").matches) return;
                  event.preventDefault();
                  document.getElementById("bolgeler")?.focus({ preventScroll: true });
                }}
              >
                Bölge listesi
              </a>
              <a
                className="geo-skip"
                href="#analiz-paneli"
                onClick={(event) => {
                  if (!window.matchMedia("(min-width: 850px)").matches) return;
                  event.preventDefault();
                  document.getElementById("analiz-paneli")?.focus({ preventScroll: true });
                }}
              >
                {panelTitle}
              </a>
            </div>
            {(error || nError) && (
              <div className="geo-status" role="alert">
                <TriangleAlert size={15} />
                <span>{error || nError}</span>
              </div>
            )}
            <div className="geo-workspace">
              <aside className="geo-left">
                <div className="geo-catalog-head" id="bolgeler" tabIndex={-1}>
                  <h2>{mode === "bursa" ? "İlçeler" : "Mahalleler"}</h2>
                  <span>{filtered.length}</span>
                </div>
                <label className="search">
                  <Search size={15} />
                  <input
                    aria-label="Bölge ara"
                    placeholder={mode === "bursa" ? "İlçe ara…" : "Mahalle ara…"}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                {mode === "district" && (
                  <p className="geo-population-note">
                    Parantez içindeki değerler sentetik mahalle nüfusudur.
                  </p>
                )}
                <div className="geo-place-list">
                  {filtered.map((f) => (
                    <button
                      key={f.properties.id}
                      className={`geo-place ${selected?.properties.id === f.properties.id ? "chosen" : ""}`}
                      aria-pressed={selected?.properties.id === f.properties.id}
                      onClick={() =>
                        select(f, mode === "bursa" ? "district" : "neighborhood")
                      }
                    >
                      <MapPin size={14} />
                      <span>
                        {title(f.properties.name)}
                        {mode === "district" &&
                          f.properties.synthetic_population !== undefined && (
                            <small
                              className="geo-place-population"
                              aria-label={`${f.properties.synthetic_population.toLocaleString("tr-TR")} sentetik nüfus`}
                            >
                              {" "}
                              (
                              {f.properties.synthetic_population.toLocaleString(
                                "tr-TR",
                              )}
                              )
                            </small>
                          )}
                      </span>
                      <ChevronRight size={12} />
                    </button>
                  ))}
                  {!filtered.length && (
                    <p className="empty">
                      {busy || nBusy
                        ? "Yükleniyor…"
                        : error || nError
                          ? "Veri yüklenemedi. Yenile düğmesini kullanın."
                          : query
                            ? "Aramanıza uygun bölge bulunamadı."
                            : "Bu görünümde bölge verisi bulunamadı."}
                    </p>
                  )}
                </div>
              </aside>
              <section
                className="geo-map-column"
                id="kent-haritasi"
                tabIndex={-1}
                aria-label="Harita görünümü"
              >
                <InventoryLayers
                  state={inventory}
                  districtActive={mode === "district"}
                  baseAllSelected={baseAllSelected}
                  toggleBaseLayers={() => {
                    const next = !baseAllSelected;
                    setShowDistricts(next);
                    if (mode === "district") setShowNeighborhoods(next);
                    setShowLabels(next);
                    setShowBase(next);
                  }}
                  baseLayers={
                    <div className="geo-layer-group">
                      <label className="geo-toggle">
                        <input
                          type="checkbox"
                          checked={showDistricts}
                          onChange={(e) => setShowDistricts(e.target.checked)}
                        />
                        <span className="legend-dot pilot-color" />
                        <span>
                          İlçe sınırları<small>Bursa Açık Yeşil</small>
                        </span>
                      </label>
                      <label className="geo-toggle">
                        <input
                          type="checkbox"
                          checked={showNeighborhoods && mode === "district"}
                          disabled={mode === "bursa"}
                          onChange={(e) => setShowNeighborhoods(e.target.checked)}
                        />
                        <span className="legend-dot neighborhood-color" />
                        <span>
                          Mahalle sınırları
                          <small>
                            {mode === "bursa"
                              ? "İlçe seçildiğinde açılır"
                              : "Analiz alanı"}
                          </small>
                        </span>
                      </label>
                      <label className="geo-toggle compact">
                        <input
                          type="checkbox"
                          checked={showLabels}
                          onChange={(e) => setShowLabels(e.target.checked)}
                        />
                        Bölge adları
                      </label>
                      <label className="geo-toggle compact">
                        <input
                          type="checkbox"
                          checked={showBase}
                          onChange={(e) => setShowBase(e.target.checked)}
                        />
                        OSM altlık <small>İnternet</small>
                      </label>
                    </div>
                  }
                  neighborhood={inventoryNeighborhood}
                  clearNeighborhood={() => {
                    inventory.close();
                    setInventoryNeighborhood(undefined);
                  }}
                />
                {districts?.features.length ? (
                  <CityMap
                    districtName={districtName}
                    districtCode={districtCode}
                    districts={districts}
                    neighborhoods={neighborhoods}
                    mode={mode}
                    selected={selected}
                    showDistricts={showDistricts}
                    showNeighborhoods={showNeighborhoods}
                    showLabels={showLabels}
                    showBase={showBase}
                    focus={focus}
                    candidate={candidate}
                    onCandidatePick={
                      picking
                        ? (point) => {
                            chooseCandidate(point);
                            document
                              .getElementById("analiz-paneli")
                              ?.focus({ preventScroll: true });
                          }
                        : null
                    }
                    route={vehicleRoute}
                    coverage={coverage}
                    developmentScores={cityView ? developmentScores : undefined}
                    inventory={inventory.filtered}
                    inventoryDetail={inventory.detail}
                    inventoryPanel={
                      inventory.chosen ? (
                        <InventoryDetail
                          state={inventory}
                          onRoute={setVehicleRoute}
                          neighborhoodCoverage={
                            inventory.detail?.properties.category_code ===
                            coverage?.category &&
                            coverage?.service_locations?.some(
                              (point) => point.id === inventory.detail?.properties.id,
                            )
                              ? coverage.neighborhoods.find(
                                  (row) =>
                                    row.name ===
                                    inventory.detail?.properties.neighborhood,
                                )
                              : undefined
                          }
                        />
                      ) : null
                    }
                    onInventorySelect={inventory.select}
                    onSelect={select}
                    onReady={() => setReady(true)}
                  />
                ) : (
                  <div className="geo-start">
                    <Map size={38} />
                    <h2>
                      {error
                        ? "Harita verisi alınamadı"
                        : busy
                          ? "Sınırlar yükleniyor…"
                          : "Henüz geometri yok"}
                    </h2>
                    <p>
                      {error ||
                        "Gerçek coğrafi veriler hazır olduğunda harita görüntülenecek."}
                    </p>
                    {error && (
                      <button className="refresh" onClick={() => void load()}>
                        Yeniden dene
                      </button>
                    )}
                  </div>
                )}
                <div className="geo-legend">
                  <span>
                    <i className="legend-dot pilot-color" />
                    İlçe sınırı
                  </span>
                  <span>
                    <i className="legend-dot neighborhood-color" />
                    Mahalle
                  </span>
                  <span>
                    <i className="legend-outline" />
                    Seçili bölge
                  </span>
                  {mode === "district" && (
                    <span>
                      <span aria-hidden="true">🏠</span>
                      Sayı, kümedeki kayıt adedidir
                    </span>
                  )}
                </div>
                {coverage && showNeighborhoods && (
                  <div
                    className="geo-legend coverage-legend"
                    aria-label="Kapsama renkleri"
                  >
                    <strong>Ölçülen hanelerde kapsama</strong>
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: coverageColors.low }}
                      />
                      %{coverage.bands?.[0] ?? 50} altı
                    </span>
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: coverageColors.medium }}
                      />
                      %{coverage.bands?.[0] ?? 50} – %{coverage.bands?.[1] ?? 80}{" "}
                      altı
                    </span>
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: coverageColors.high }}
                      />
                      %{coverage.bands?.[1] ?? 80} ve üzeri
                    </span>
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: coverageColors.missing }}
                      />
                      Ölçüm yok
                    </span>
                  </div>
                )}
              </section>
              <aside className="geo-right" id="analiz-paneli" tabIndex={-1}>
                <nav className="geo-panel-switcher" aria-labelledby="analysis-tools-title">
                  <h2 id="analysis-tools-title" className="geo-panel-switcher-title">
                    <SlidersHorizontal size={16} aria-hidden="true" />
                    Analiz araçları
                  </h2>
                  <button
                    className="nav"
                    aria-label="Kent haritası"
                    aria-pressed={!analysis && !dashboard && !scenario}
                    onClick={() => {
                      if (scenario) closeScenario();
                      setAnalysis(false);
                      setDashboard(false);
                      setCoverage(null);
                    }}
                  >
                    <Map size={18} />
                    Kent haritası
                  </button>
                  <button
                    className="nav"
                    aria-label="Hizmet erişimi"
                    aria-pressed={analysis}
                    onClick={openAnalysis}
                  >
                    <Activity size={18} />
                    Hizmet erişimi
                  </button>
                  <button
                    className="nav"
                    aria-label="Mahalle analizi"
                    aria-pressed={dashboard}
                    onClick={() => {
                      if (scenario) closeScenario();
                      inventory.close();
                      setAnalysis(false);
                      setMode("district");
                      setShowNeighborhoods(true);
                      setDashboard(true);
                    }}
                  >
                    <Layers3 size={18} />
                    Mahalle analizi
                  </button>
                  <button
                    className="nav"
                    aria-label="Yatırım senaryoları"
                    aria-pressed={scenario}
                    onClick={openScenario}
                  >
                    <Sparkles size={18} />
                    Yatırım senaryoları
                  </button>
                </nav>
                <div className="geo-panel-content" key={panelTitle}>
                  <div className="geo-panel-head">
                    <MapPin size={16} />
                    <h2>{panelTitle}</h2>
                  </div>
                  {analysis && (
                    <div className="access-close">
                      <button
                        className="inventory-link"
                        onClick={() => {
                          setAnalysis(false);
                          setCoverage(null);
                        }}
                      >
                        Analizi kapat
                      </button>
                    </div>
                  )}
                  {scenario && (
                    <InvestmentScenario
                      key={districtCode}
                      districtCode={districtCode}
                      point={candidate}
                      onPoint={chooseCandidate}
                      onPick={() => {
                        setPicking(true);
                        scrollToMap();
                      }}
                      onCoverage={setCoverage}
                      onClose={closeScenario}
                    />
                  )}
                  {dashboard && (
                    <NeighborhoodDashboard
                      key={districtCode}
                      districtCode={districtCode}
                      districtName={districtName}
                      selected={inventoryNeighborhood}
                      coverage={coverage}
                      controls={
                        <Accessibility
                          key={districtCode}
                          districtCode={districtCode}
                          showResults={false}
                          onCoverage={setCoverage}
                          onThresholds={setThresholds}
                        />
                      }
                      onClear={() => {
                        inventory.close();
                        setInventoryNeighborhood(undefined);
                        setSelected(null);
                      }}
                      onSelect={(id) => {
                        const item = neighborhoods?.features.find(
                          (feature) => feature.properties.id === id,
                        );
                        if (item) select(item, "neighborhood");
                      }}
                    />
                  )}
                  {analysis && (
                    <Accessibility
                      key={districtCode}
                      districtCode={districtCode}
                      onCoverage={setCoverage}
                      onThresholds={setThresholds}
                    />
                  )}{" "}
                  {cityView && (
                    <section className="geo-details" aria-label="Sentetik hizmet gelişmişliği">
                      <h2>Sentetik hizmet gelişmişliği</h2>
                      <p>Yedi hizmet grubundaki tesis türü çeşitliliği. İlçe puanı mahallelerin sentetik nüfusuna göre ağırlıklandırılır.</p>
                      {developmentError ? <p role="alert">Gösterge yüklenemedi.</p> :
                        !developmentScores ? <p role="status">Gösterge yükleniyor…</p> : (
                          <div className="access-results">
                            <table>
                              <thead><tr><th>{mode === "bursa" ? "İlçe" : "Mahalle"}</th><th>Puan</th></tr></thead>
                              <tbody>{rankedAreas.map((area) => {
                                const score = developmentScores[area.properties.id];
                                return <tr key={area.properties.id}>
                                  <th scope="row"><button className="inventory-link" onClick={() => select(area, mode === "bursa" ? "district" : "neighborhood")}>{title(area.properties.name)}</button></th>
                                  <td>{score === undefined ? "—" : `%${score.toLocaleString("tr-TR")}`}</td>
                                </tr>;
                              })}</tbody>
                            </table>
                          </div>
                        )}
                    </section>
                  )}
                  {analysis || dashboard || scenario ? null : p ? (
                    <div className="geo-details">
                      <span className="eyebrow">
                        {p.active !== undefined ? "İLÇE" : "MAHALLE"}
                      </span>
                      <h2>{title(p.name)}</h2>
                      <div className="geo-detail-tags">
                        <span className="pill">
                          {p.active !== undefined ? "Resmî sınır" : "Analiz alanı"}
                        </span>
                        <span className="muted-pill">
                          {p.active !== undefined
                            ? "2025 nüfus verisi"
                            : districtName}
                        </span>
                      </div>
                      {p.population_2025 !== undefined && (
                        <dl className="analysis-metrics">
                          <div>
                            <dt>2025 resmî ilçe nüfusu</dt>
                            <dd>{p.population_2025.toLocaleString("tr-TR")}</dd>
                          </div>
                          <div>
                            <dt>Resmî ilçe nüfus yoğunluğu</dt>
                            <dd>
                              {p.population_density_2025?.toLocaleString("tr-TR")}{" "}
                              <small>kişi/km²</small>
                            </dd>
                          </div>
                        </dl>
                      )}
                      <details className="geo-source-details">
                        <summary>Coğrafi veri ve yöntem</summary>
                        <dl>
                          <div>
                            <dt>Kaynak kimliği</dt>
                            <dd>{p.code}</dd>
                          </div>
                          <div>
                            <dt>Koordinat sistemi</dt>
                            <dd>WGS 84 · EPSG:4326</dd>
                          </div>
                          {p.area_km2 !== undefined && (
                            <div>
                              <dt>Geometri alanı</dt>
                              <dd>{p.area_km2.toLocaleString("tr-TR")} km²</dd>
                            </div>
                          )}
                          <div>
                            <dt>Veri kaynağı</dt>
                            <dd>Bursa Açık Yeşil</dd>
                          </div>
                        </dl>
                        <p className="geo-method">{p.method}</p>
                      </details>
                      {
                        <button
                          className="geo-focus"
                          disabled={!ready}
                          onClick={() => {
                            if (!selected && district) setSelected(district);
                            setFocus((x) => x + 1);
                            scrollToMap();
                          }}
                        >
                          <Crosshair size={16} />
                          Seçili bölgeye odaklan
                        </button>
                      }
                      <button
                        className="inventory-link geo-analysis-link"
                        onClick={openAnalysis}
                      >
                        Hizmet erişimini incele <ChevronRight size={14} />
                      </button>
                    </div>
                  ) : (
                    <div className="geo-unselected">
                      <div>
                        <Crosshair size={34} strokeWidth={1} />
                      </div>
                      <h3>Bir bölge seçin</h3>
                      <p>
                        Haritaya veya bölge listesine tıklayarak kaynak ve sınır
                        bilgilerini görüntüleyin.
                      </p>
                      <button
                        className="geo-focus"
                        onClick={() => {
                          const n = districts?.features.find(
                            (f) => f.properties.code === districtCode,
                          );
                          if (n) select(n, "district");
                        }}
                        disabled={!districts?.features.length}
                      >
                        {districtName} ilçesini aç
                        <ArrowUpRight size={15} />
                      </button>
                    </div>
                  )}
                </div>
              </aside>
            </div>
          </div>
          <footer>
            <span>BURSA · KENTSEL ZEKÂ / Yerel belediyecilik prototipi</span>
            <span>Kaynak snapshot · 12 Kasım 2026</span>
          </footer>
        </div>
      </main>
      {sources && (
        <div className="geo-modal-backdrop">
          <section
            className="geo-source-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Veri kaynakları"
          >
            <button
              className="geo-modal-close"
              autoFocus
              onClick={() => setSources(false)}
              aria-label="Kaynak penceresini kapat"
            >
              <X size={20} />
            </button>
            <span className="eyebrow">VERİ KAYNAKLARI VE YÖNTEM</span>
            <h2>Gerçek sınırlar, izlenebilir dönüşüm.</h2>
            <p>
              12 Kasım 2026’da alınan resmî açık veri snapshot’ı. İlçe nüfusları
              2025 resmî değerleridir. Demo haneleri sentetiktir.
            </p>
            <h3>İlçe sınırları</h3>
            <p>
              17 ilçe, kaynak EPSG:4326. Nilüfer dış hattı kaynak geometrisinden
              çizilir. Diğer ilçelerde harita için 20 m sadeleştirme uygulanır.
            </p>
            <a
              href="https://acikyesil.bursa.bel.tr/dataset/ilce-bazli-nufus-verisi"
              target="_blank"
              rel="noreferrer"
            >
              İlçe veri kaynağı ↗
            </a>
            <h3>Mahalle sınırları</h3>
            <p>
              {" "}
              Kaynak EPSG:2320 (ED50 / TM30), PyProj ile EPSG:4326’ya
              dönüştürüldü. Alan hesapları EPSG:32635. Mahalle analiz alanları
              resmî ilçe dış hattına uyarlanır.
            </p>
            <a
              href="https://acikyesil.bursa.bel.tr/dataset/mahalle-sinirlari"
              target="_blank"
              rel="noreferrer"
            >
              Mahalle veri kaynağı ↗
            </a>
            <h3>Sentetik envanter</h3>
            <p>
              Yeni ilçelerde hane örneklemi resmî ilçe nüfusuna göre ölçeklenir.
              Yerleşim dağılımı OpenStreetMap yerleşim merkezleriyle
              ağırlıklandırılır.
            </p>
            <h3>Mahalle analiz alanı</h3>
            <p>
              İlçe dışına taşan kısımlar kesilir. İlçe içindeki boşluklar ortak
              sınırı en uzun olan mahalleye eklenir. Keles ve Harmancık
              mahallelerinin ilçe etiketleri resmî ilçe poligonlarıyla
              eşleştirildi. Ham kaynak geometrileri arşivde korunur.
            </p>
            <a
              href="https://acikyesil.bursa.bel.tr/license"
              target="_blank"
              rel="noreferrer"
            >
              Bursa Açık Veri Lisansı ↗
            </a>
          </section>
        </div>
      )}
    </div>
  );
}
