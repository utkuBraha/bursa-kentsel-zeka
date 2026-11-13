# Veri kaynakları ve veri sözleşmesi
Araştırma tarihi: 2026-11-12. Ayrıntılı URL/koşul tablosu: SMART-CITY-RESEARCH.md.

| Kimlik | Kaynak | Format | Tür | Kullanım / durum |
|---|---|---|---|---|
| bursa-district-2025 | https://bapi.bursa.bel.tr/apigateway/bbbAcikVeri_Cbs/ilce_nufus_2025 | JSON/GeoJSON | REAL | resmî ilçe kaynağı; indirme ve şema doğrulama |
| bursa-neighborhood | https://bapi.bursa.bel.tr/apigateway/bbbAcikVeri_Cbs/Mahalle | JSON/GeoJSON | REAL | mahalle kaynağı; büyük dosya, sunucu tarafında işlenecek |
| osm | https://www.openstreetmap.org/ | XML/PBF/GeoJSON dönüşümü | REAL | Faz 3 bina, POI, yol aday kaynağı; ODbL atfı |
| tuik | https://veriportali.tuik.gov.tr/ | henüz doğrulanmadı | REAL | yalnızca toplulaştırılmış istatistik; içe aktarım yok |
| demo-seed-v1 | `backend/app/demo_seed.py` | JSON/DB | SYNTHETIC | 10.000 hane, 3.000 bina, 1.500 işletme, 500 şirket ve 360 demo hizmet noktası |
| access-model-v1 | uygulama analizi | JSON/DB | ESTIMATED | açıklanabilir skor; henüz uygulanmadı |

## Soy ağacı ve lisans
Her kayıtta source_id, data_type (REAL/SYNTHETIC/ESTIMATED), source_record_id, method, created_at, updated_at bulunacak. DataSource ayrıca URL, lisans URL'si, erişim tarihi, doğrulama durumu, veri dönemi ve SHA-256 tutar. Ham veri değiştirilmeyecek; işlenmiş türevler ayrı saklanacak. Veri dönüşümü resmî kaynağa dayanmayı kaldırmaz, yöntemi ayrıca kaydedilir.
Bursa verilerinde kaynak ve https://acikyesil.bursa.bel.tr/license atfı gösterilir. Resmî logo/marka kullanım hakkı varsayılmaz. Muhtar gibi kişi bilgileri bu projeye alınmaz.

## Alım kapısı
HTTP başarı → boyut limiti → JSON şeması → CRS 4326 / koordinat sırası → polygon geçerliliği → ilçe ve mahalle ilişki kontrolü → kopya anahtar kontrolü → işlem içinde yükleme. Geometri onarımı sessiz yapılmaz. Yeterli veri yoksa boş durum; yaklaşık sınır çizilmez. Kaynak hizmet kapsamı eksikse 'hizmet yok' sonucu çıkarılmaz.

## Sentetik üretim tasarımı
Seed ve üretici sürümü saklanır. Doğrulanmış mahalle içinde, mümkünse gerçek bina footprint'lerinde ağırlıklı örnekleme yapılır. Sentetik bina üretilirse açıkça SYNTHETIC etiketlenir. Hane nüfusu yaş grubu toplamına eşit, bina/mahalle ilişkisi tutarlı olmalıdır. Kaynak konut yoğunluğu bilinmiyorsa dağılımın varsayım olduğu belirtilir. Gerçek kişi, telefon, TC, e-posta veya özel adres üretilmez.

## İndirilen dosyaların ilk kalite kontrolü
`backend/.venv/bin/python scripts/inspect_sources.py` ile rapor yeniden üretilir: `data/processed/source-quality.json`. 17 ilçe (EPSG:4326), 1.074 mahalle (EPSG:2320), bunlardan 70'i Nilüfer. Shapely geçerlilik kontrolünde geçersiz geometri yok. Bu, güncellik veya resmî topolojik kapsama garantisi değildir. Faz 2'de EPSG:2320 → 4326 dönüşümü, Nilüfer containment/tolerans, komşuluk ve görsel hizalama kontrolü yapılacak. Her iki dosyanın SHA-256 değeri rapordadır. Faz 1 DB'ye yalnız ilçe kimlik/ad kataloğu alınır.


### Sentetik envanter

Üretici, ilçe ve mahalle kesişimi içinde binalar üretir ve haneleri bu binalara bağlar. Bursa genelinde 153.829 hane ve 539.268 kişi bulunur. Beş ilçedeki sekiz referans mahalle daha yoğun ve donatılı örneklenir. Sentetik hizmetlerin kaynak anahtarı `demo-seed-v1` olarak saklanır. Bursa Uludağ Üniversitesi Görükle yerleşkesi ayrı kaynak kaydıyla haritada gösterilir. [Yerleşke kaynağı](https://uludag.edu.tr/gorukle-yerleskesi-85514)

Kent haritası puanı, yedi hizmet grubunda bulunan sentetik tesis türlerinin ilgili gruptaki türlere oranını eşit ağırlıkla ortalar. İlçe puanı mahallelerin sentetik nüfusuyla ağırlıklandırılır.

### Araç rotası

Hane detayında, kullanıcı tek bir rota istediğinde sentetik hane ve seçili pilot hizmet koordinatları FOSSGIS OSRM araç servisine gönderilir. Servis [OpenStreetMap yol ağını](https://www.openstreetmap.org/copyright) kullanır. İlçe dış hattı rotayı kırpmaz. Yerleşimler en yakın araç yolu noktasına bağlı varsayılır. Gösterilen süre standart araç tahminidir. Canlı trafik ve ekip çıkış süresi dahil değildir. Toplu kapsama analizinde yerel OSRM ve sürümlenmiş bir yol ağı özeti gerekir. [FOSSGIS servis koşulları](https://routing.openstreetmap.de/about.html).

## Bursa geneli genişleme

- **Resmî referans.** [2025 ilçe nüfusu ve sınırları](https://acikyesil.bursa.bel.tr/dataset/ilce-bazli-nufus-verisi), [mahalle sınırları](https://acikyesil.bursa.bel.tr/dataset/mahalle-sinirlari) ve [TÜİK ADNKS 2025](https://veriportali.tuik.gov.tr/Bulten/Index?p=53899). İlçe kartındaki kişi/km², resmî nüfusun EPSG:32635 ile hesaplanan poligon alanına bölünmesiyle elde edilir.
- **Mahalle eşleşmesi.** Belediye mahalle dosyasındaki Keles ve Harmancık etiketleri karşı ilçenin poligonuyla sırasıyla yaklaşık %98,5 ve %98,9 örtüşür. Ters eşleşme doğrulanınca mahallelerin ilçe bağlantısı düzeltilir. İlçe poligonları, nüfus kimlikleri ve ham dosyalar korunur.
- **Sentetik örnekleme.** Yeni ilçelerde hane sayısı 2025 ilçe nüfusuna göre Nilüfer’in 23.000 hanelik örneğine oranlanır. Nilüfer dışındaki ilçelerde nüfus oranı 1,55 katsayısıyla ölçeklenir ve ilçe başına 600–30.000 hane üretilir. Daha küçük ilçelerde müstakil yapı, büyük ilçelerde konut ve karma yapı oranı artar. Ofis ve işletmeler karma yapılarda kümelenir. İlçe başına en az iki sentetik itfaiye, dört okul ve sekiz otobüs durağı üretilir. Bu ölçek ilçeler arasında farklı örnekleme oranlarına yol açar. Mahallelerin ağırlığı OSM yerleşim noktalarının türüne ve sayısına göre belirlenir. Yerleşim noktası bulunmayan mahalleler düşük ağırlık alır. Haneler yerleşim çevresinde kümelenir.
- **Yol ağı ve yerleşim noktaları.** [Geofabrik OSM Türkiye kesiti](https://download.geofabrik.de/europe/turkey.html), 12 Kasım 2026. Bursa ve çevresi için 28.0,39.53,30.05,40.66 kesiti. Yerleşim dosyası 1.858 place düğümünün koordinat ve türlerini içerir. © OpenStreetMap katkıda bulunanlar, [ODbL](https://www.openstreetmap.org/copyright). Araç süreleri OSRM sürüş profiliyle tahmin edilir. Canlı trafik ve müdahale hazırlık süresi kapsama dahil değildir.

Mahalle karşılaştırmasındaki demo kişi/km², sentetik hane nüfusunun mahalle analiz alanına bölünmesiyle hesaplanır. Hane rota menüsü komşu ilçelerde kuş uçuşu 8 km içindeki hizmetlerden ilçe ve kategori başına en yakın noktayı sunar.
