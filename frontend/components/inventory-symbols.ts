const symbols: Record<string, [string, string]> = {
  households: ["🏠", "Hane"],
  detached: ["🏠", "Müstakil ev"],
  residential: ["🏢", "Konut binası"],
  mixed: ["🏬", "Karma kullanım binası"],
  buildings: ["🏢", "Bina"],
  companies: ["🏢", "Ofis"],
  businesses: ["🏪", "İşletme"],
  cycleways: ["🚲", "Bisiklet yolu"],
  services: ["📍", "Hizmet noktası"],
  fire: ["🚒", "İtfaiye"],
  hospital: ["🏥", "Hastane"],
  family_health: ["🩺", "Aile sağlığı merkezi"],
  pharmacy: ["💊", "Eczane"],
  bus: ["🚌", "Otobüs durağı"],
  rail: ["🚆", "Raylı sistem"],
  metro: ["🚇", "Metro istasyonu"],
  taxi: ["🚕", "Taksi durağı"],
  parking: ["🅿️", "Otopark"],
  school: ["🏫", "Okul"],
  university: ["🎓", "Üniversite"],
  park: ["🌳", "Park"],
  sports: ["⚽", "Spor tesisi"],
  culture: ["🎭", "Kültür merkezi"],
  library: ["📚", "Kütüphane"],
  social_facility: ["🤝", "Sosyal tesis"],
  assembly: ["🚩", "Toplanma alanı"],
  polyclinic: ["🩺", "Poliklinik"],
  adult_education: ["🎓", "Halk eğitim merkezi"],
  emergency_aid: ["🚑", "Acil müdahale noktası"],
  local_office: ["🏛️", "Muhtarlık"],
  waste_collection: ["🗑️", "Atık toplama noktası"],
  recycling: ["♻️", "Geri dönüşüm noktası"],
  air_monitor: ["🌫️", "Hava kalitesi ölçüm noktası"],
  municipal: ["🏛️", "Belediye hizmet noktası"],
};

export function inventorySymbol(kind: string, category?: string) {
  return symbols[category ?? kind] ?? symbols[kind] ?? symbols.services;
}

export function inventoryIconId(kind: string, category?: string) {
  const key = category ?? kind;
  return `inventory-${Object.hasOwn(symbols, key) ? key : "services"}`;
}

export function markerImage(id: string) {
  const key = id.slice("inventory-".length);
  const group = /^group-(.+)-(\d+)$/.exec(key);
  const count = group?.[2] ?? "";
  const symbol = symbols[group?.[1] ?? key];
  if (!symbol) return;
  const canvas = document.createElement("canvas");
  const width = count ? Math.max(53, 33 + count.length * 8) : 30;
  canvas.width = width * 2;
  canvas.height = 60;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.scale(2, 2);
  context.beginPath();
  context.roundRect(1, 1, width - 2, 28, 8);
  context.fillStyle = count ? "#eaf2f7" : "#fff";
  context.fill();
  context.strokeStyle = "#527f9d";
  context.stroke();
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font =
    '17px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif';
  context.fillText(symbol[0], count ? 15 : width / 2, 15);
  if (count) {
    context.font = "600 12px system-ui, sans-serif";
    context.fillStyle = "#123b60";
    context.fillText(count, (width + 23) / 2, 15);
  }
  return context.getImageData(0, 0, canvas.width, canvas.height);
}
