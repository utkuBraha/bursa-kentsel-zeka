# Bursa Kentsel Zekâ

Bursa’nın 17 ilçesi için geliştirilmiş bağımsız bir kentsel karar destek prototipi. Harita, sentetik envanter ve yol ağı üzerinden hizmete erişimi incelemeyi ve yeni bir hizmet noktasının etkisini karşılaştırmayı sağlar.

- **Kent haritası** ilçelerin sentetik hizmet gelişmişliği puanlarını gösterir. İlçe seçince aynı görünüm mahalle düzeyine iner. Puan, yedi hizmet grubundaki tesis türü çeşitliliğine dayanır. İlçe puanı mahallelerin sentetik nüfusuyla ağırlıklandırılır. Gösterge yalnızca demo envanterini temsil eder.
- **Harita katmanları** konut, ofis ve hizmet kayıtlarını açar. Her sekmede **Tümünü seç** ile kullanılabilir katmanları birlikte açabilirsiniz.
- **Mahalle analizi ve hizmet erişimi** nüfus, envanter ve kapsama sonuçlarını gösterir. Kapsama kuş uçuşu halkalarıyla veya araç ağı üzerinden incelenebilir.
- **Yatırım senaryoları** aday bir hizmet noktasının kapsanan hane ve nüfusa etkisini karşılaştırır ve yatırım bölgeleri önerir.

## İş akışı

```mermaid
flowchart TD
    A["Resmî ilçe ve mahalle sınırları"] --> B["Nilüfer pilotu"]
    B --> C["Sentetik konut, hane ve hizmet envanteri"]
    C --> D["Harita katmanları ve mahalle göstergeleri"]
    D --> E["OSRM ile araç ağı kapsama analizi"]
    E --> F["Mevcut durum ve aday yatırım karşılaştırması"]
    F --> G["Bursa genelinde 17 ilçe ve 1.074 mahalle"]
```

1. Resmî sınırlar ve ilçe nüfusları içe alındı. Nilüfer, ilk veri ve uygulama doğrulaması için pilot ilçe olarak seçildi.
2. Mahalle sınırları içinde sentetik konut, hane, ofis ve hizmet kayıtları üretildi. Bina ve hane ilişkileri ile nüfus toplamları doğrulandı.
3. Envanter harita katmanlarına aktarıldı. Mahalle göstergeleri nüfusu, hizmet dağılımını ve sentetik hizmet çeşitliliğini karşılaştırmaya açtı.
4. Kuş uçuşu kapsama halkaları ve OSRM araç ağı hesabı eklendi. Yatırım senaryoları, aday bir hizmet noktasının kapsanan hane ve nüfusa etkisini ölçtü.
5. Nilüfer’de doğrulanan iş akışı Bursa’nın 17 ilçesine ve 1.074 mahalle analiz alanına genişletildi.

## Fork sonrası kurulum

Git ve Docker Compose gerekir. GitHub’da repoyu fork edin ve aşağıdaki ilk komutta `FORK_URL` yerine kendi fork’unuzun HTTPS klon adresini yazın.

```sh
git clone FORK_URL bursa-kentsel-zeka
cd bursa-kentsel-zeka
cp .env.example .env
docker compose up --build -d --wait
```

İlk açılışta sınırlar ve sentetik envanter hazırlanır. Bu işlem birkaç dakika sürebilir. [Uygulamayı aç](http://127.0.0.1:3016/) · [Yerel API belgeleri](http://127.0.0.1:8000/docs)

## Yol ağı ve yatırım senaryoları

Yerel OSRM kurulumu için `osmium` gerekir. [Geofabrik Türkiye verisini](https://download.geofabrik.de/europe/turkey.html) proje köküne `turkey-latest.osm.pbf` adıyla kaydedin ve komutları sırasıyla çalıştırın.

```sh
mkdir -p data/routing/city
osmium extract -s smart -b 28.0,39.53,30.05,40.66 turkey-latest.osm.pbf -o data/routing/city/bursa.osm.pbf
bash scripts/prepare-routing.sh
docker compose -f docker-compose.yml -f compose.routing.yml up --build -d --wait
```

Sürüş tahminleri mevcut araç ağına dayanır. Sentetik haneler en yakın araç yolu noktasına bağlı kabul edilir. Canlı trafik ve ekip çıkış süresi hesaba katılmaz.

## Veri kaynakları

İlçe nüfusu ve sınırları Bursa Açık Yeşil’e dayanır. Haneler ve hizmet envanterinin büyük bölümü sentetiktir. Yerleşim noktaları ve yol ağı OpenStreetMap verilerine dayanır. [Veri kaynakları ve lisanslar](DATA-SOURCES.md)
