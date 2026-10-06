# Ürün Yönetimi (Ekleme, Silme ve Görsel Yönetimi) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin paneline yeni ürün ekleme (modal ile resim/URL, ad, kategori, fiyat, açıklama) ve ürün silme işlevlerini ekleyerek veritabanı ve müşteri kiosk ekranı ile tam senkronizasyon sağlamak.

**Architecture:** Flask REST API (`POST /api/products`, `DELETE /api/products/<id>`) + SQLite veritabanı parametrik sorguları + HTML5 Modal form arayüzü + Asenkron fetch/FormData istemci iletişimi.

**Tech Stack:** Python 3, Flask, SQLite3, Vanilla JavaScript (ES6), CSS3 Modern Glassmorphic Dark UI.

## Global Constraints
- Parametrik SQLite sorguları ile SQL injection koruması.
- `secure_filename` ile güvenli dosya adı ve uzantı doğrulaması (`.jpg`, `.jpeg`, `.png`, `.webp`).
- Yüklenen dosyaların `static/images/products/` dizininde saklanması.
- Geriye dönük uyumluluk: `/index` kiosk ekranının ve `recommendation_service.py` servisinin kesintisiz çalışması.

---

### Task 1: Backend Veritabanı ve RESTful API Endpoint'leri

**Files:**
- Modify: `app.py`
- Create: `test_product_api.py`

- [ ] **Step 1: Test dosyasını hazırla (test_product_api.py)**
Yazılacak test: `POST /api/products` ile ürün ekleme ve `DELETE /api/products/<id>` ile silme.

- [ ] **Step 2: Testi çalıştırıp başarısız olduğunu doğrula**
Run: `python test_product_api.py`
Expected: FAIL (404/405 endpoint yok)

- [ ] **Step 3: app.py içine POST ve DELETE endpoint'lerini ekle**
`POST /api/products`: FormData ve JSON desteği, dosya yükleme (`static/images/products/`), veritabanına kayıt.
`DELETE /api/products/<int:product_id>`: Veritabanından güvenli silme.

- [ ] **Step 4: Testi yeniden çalıştır ve geçtiğini doğrula**
Run: `python test_product_api.py`
Expected: PASS (200 OK, ürün eklendi ve silindi)

- [ ] **Step 5: Geçici test dosyasını temizle ve kontrol et**

---

### Task 2: Frontend HTML ve CSS Arayüzü (Modal & Kart Tasarımı)

**Files:**
- Modify: `templates/dashboard.html`
- Modify: `static/dashboard.css`

- [ ] **Step 1: templates/dashboard.html üzerinde '#products-page' başlığına "+ Yeni Ürün Ekle" butonu ekle**
- [ ] **Step 2: templates/dashboard.html dosyasının altına '#addProductModal' modal yapısını ekle**
İçerik: Ürün adı, Kategori seçimi (Kahve, Soğuk İçecek, Tatlı & Fırın, Yiyecek veya Yeni Kategori), Fiyat (₺), Açıklama, Görsel Dosyası veya Görsel URL'si, İptal ve Kaydet butonları.
- [ ] **Step 3: static/dashboard.css içine modal, ürün kartı aksiyonları ve kategori rozetleri stillerini ekle**

---

### Task 3: Frontend JavaScript Mantığı (Ekleme, Silme ve Dinamik Yenileme)

**Files:**
- Modify: `static/dashboard.js`

- [ ] **Step 1: loadAdminProducts() metodunu güncelle**
Her ürün kartına kategori rozeti, açıklama ve sağ altta kırmızı "Sil" butonu (`onclick="dashboard.deleteProduct(${p.id}, '${escapedName}')"`) ekle.
- [ ] **Step 2: openAddProductModal() ve closeAddProductModal() metodlarını ekle**
- [ ] **Step 3: submitAddProduct() metodunu ekle**
Form verilerini `FormData` ile toplayıp `POST /api/products` endpoint'ine gönder, başarılı olunca modalı kapatıp ürün listesini yenile.
- [ ] **Step 4: deleteProduct(productId, productName) metodunu ekle**
Onay sorusu sor (`confirm`), onaylanırsa `DELETE /api/products/${productId}` çağrısı yap ve listeyi anında yenile.
- [ ] **Step 5: JavaScript syntax kontrolü yap**
Run: `node --check static/dashboard.js`
Expected: 0 hata

---

### Task 4: Uçtan Uca Doğrulama ve Müşteri Kiosk Uyumluluğu

- [ ] **Step 1: app.py başlatma ve API doğrulama**
Run: `python -m py_compile app.py`
- [ ] **Step 2: Test ürünü ekleyip /index Kiosk ve /admin panellerinde kontrol etme**
