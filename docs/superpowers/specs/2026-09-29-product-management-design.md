# Ürün Yönetimi (Ekleme, Silme, Listeleme ve Görsel Yönetimi) Tasarım Dokümanı

**Tarih:** 2026-09-29  
**Durum:** Onaylandı  
**Kapsam:** Admin paneli ürün yönetim sayfası (`#products-page`), backend RESTful API'leri (`POST /api/products`, `DELETE /api/products/<id>`), dosya yükleme mekanizması ve müşteri kiosk ekranı senkronizasyonu.

---

## 1. Amaç & Kapsam
İşletme yöneticisinin admin paneli üzerinden:
1. Kafede satılan ürünleri görüntüleyebilmesi,
2. Modal arayüzü ile yeni ürün (isim, kategori, fiyat, açıklama, görsel) ekleyebilmesi,
3. Mevcut ürünleri onay alarak sistemden ve veritabanından silebilmesi,
4. Eklenen/silinen ürünlerin hem veritabanına (`products` tablosu) hem de müşteri kiosk ekranına (`/index`) anlık olarak yansıması.

---

## 2. Mimari ve Bileşenler

### 2.1 Backend & Veritabanı (`app.py`, `database.py`)
* **Veritabanı Tablosu (`products`):**
  - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `product_name`: TEXT NOT NULL UNIQUE
  - `category`: TEXT NOT NULL
  - `price`: REAL NOT NULL
  - `description`: TEXT DEFAULT ''
  - `image_url`: TEXT DEFAULT ''

* **API Endpoint'leri:**
  1. `GET /api/products` (veya `GET /api/get_products`):
     - Tüm aktif ürünleri JSON listesi olarak döner.
  2. `POST /api/products`:
     - Yeni ürün oluşturur.
     - `multipart/form-data` ve `application/json` formatlarını kabul eder.
     - Dosya yüklenmişse `static/images/products/` klasörüne benzersiz dosya adıyla kaydeder.
     - Doğrulama: `product_name` dolu ve benzersiz olmalı, `price` pozitif sayı olmalı, `category` seçili olmalı.
     - Dönüş: `{"success": true, "message": "Ürün başarıyla eklendi.", "product": {...}}`
  3. `DELETE /api/products/<int:product_id>`:
     - Ürünü veritabanından siler.
     - Eğer ürün `order_items` geçmişinde varsa, geçmiş siparişlerin bütünlüğünü bozmamak için ilişkili referansları güvenli yönetir.
     - Dönüş: `{"success": true, "message": "Ürün başarıyla silindi."}`

### 2.2 Frontend Arayüzü (`templates/dashboard.html`, `static/dashboard.js`, `static/dashboard.css`)
* **Ürünler Sayfası (`#products-page`):**
  - Üst başlık satırında:
    - Sayfa Başlığı ve ikon: `restaurant_menu Kafe Menü & Ürün Yönetimi`
    - Sağ tarafta yeşil renkli **"+ Yeni Ürün Ekle"** butonu (`#btnOpenAddProductModal`).
  - Kategori Filtreleme Sekmeleri:
    - `Tümü`, `Kahve`, `Soğuk İçecek`, `Tatlı & Fırın`, `Yiyecek`.
  - Ürün Kartları Izgarası (`#adminProductsGrid`):
    - Kart yapısı:
      - 56x56 px yuvarlatılmış ürün görseli.
      - Ürün adı ve açıklama.
      - Kategori rozeti (`.badge-category`).
      - Fiyat göstergesi (`65.00 ₺`).
      - Kırmızı aksiyon butonu: `Sil` butonu (çöp kutusu ikonu ve onay diyaloğu).

* **Yeni Ürün Ekleme Modalı (`#addProductModal`):**
  - Koyu tema uyumlu cam/neon modal kutusu.
  - Alanlar:
    - `Ürün Adı` (`#newProdName`)
    - `Kategori` (`#newProdCategory` - Seçim ve Özel Kategori)
    - `Fiyat (₺)` (`#newProdPrice`)
    - `Açıklama` (`#newProdDesc`)
    - `Görsel Yükle / URL` (`#newProdImageFile` ve `#newProdImageUrl`)
  - Butonlar: `İptal` ve `Ürünü Kaydet`.

---

## 3. Güvenlik & Doğrulama
- Yüklenen dosyaların uzantı kontrolü (`.jpg`, `.jpeg`, `.png`, `.webp`).
- Güvenli dosya adı (`secure_filename`).
- Sayısal fiyat doğrulaması (`float(price) > 0`).
- SQL Enjeksiyonuna karşı parametrik SQLite sorguları (`?`).

---

## 4. Test & Doğrulama Planı
1. SQLite veritabanı sorguları (`SELECT`, `INSERT`, `DELETE`) birim testi.
2. Endpoint API testleri (`POST /api/products`, `DELETE /api/products/<id>`).
3. Admin arayüzü JavaScript syntax kontrolü (`node --check static/dashboard.js`).
4. Kiosk ekranı (`/index`) ile uyumluluk doğrulaması.
