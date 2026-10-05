# Tasarım Dokümanı: Garson Servis & Akıllı Müşteri Öneri Terminali (Waiter POS AI)

**Tarih:** 2026-10-05  
**Durum:** Onaylandı / Tasarım Aşamasında  
**Hedef Kitle:** Garsonlar, Kasa Görevlileri ve Kafe İşletmecisi  

---

## 1. Yönetici Özeti & Amaç Değişimi

Sistem daha önce müşterinin kendi kendine kullandığı bir Kiosk ekranı (`/`) olarak çalışıyordu. Yeni konseptle birlikte sistemin ana kullanıcısı doğrudan **Garson** olmaktadır:

1. **Müşteri Girişi & Varlık Tespiti:** Müşteri dükkana girdiğinde geniş açılı genel mekan kamerası yüzü algılar ve Garson Terminali'nde anında yeni müşteri kartı açar.
2. **Durumsal Akıllı Öneri Algoritması:** Sistem müşterinin geçmiş sipariş alışkanlıklarını, anlık hava durumunu, günün saatini/öğün dilimini ve kafedeki popülerlik trendlerini birleştirerek nokta atışı 3-4 ürün önerir.
3. **Garson Konuşma Asistanı (Waiter Pitch):** Garson masaya gitmeden önce ekranda müşteriye söyleyebileceği hazır, kişiselleştirilmiş bir hitap cümlesi görür.
4. **Varlık Döngüsü & Çıkış Takibi:** Müşteri siparişi verildiğinde "Masada Olanlar" listesine geçer; kapıdan ayrıldığında veya garson masayı kapattığında oturum tamamlanır ve çıkış logu işlenir.

---

## 2. Mimari ve Varlık Döngüsü (Presence Lifecycle)

### 2.1 Müşteri Durum Makinesi (State Machine)

```
[Kamera Yüzü / Müşteriyi Algılar]
                 ↓
      ┌───────────────────────────┐
      │   DURUM: 'waiting_order'  │  ← Yeni Giriş (Sipariş Bekliyor)
      │  (Yeşil nabız, sesli uyarı)│
      └─────────────┬─────────────┘
                    │ Garson siparişi girer veya "Sipariş Alındı" der
                    ↓
      ┌───────────────────────────┐
      │     DURUM: 'ordered'      │  ← Masada / Servis Edildi (Pasif)
      │   (Sayaç devam eder)      │
      └─────────────┬─────────────┘
                    │ Müşteri kapıdan ayrılır veya Garson "Masayı Kapat" der
                    ↓
      ┌───────────────────────────┐
      │      DURUM: 'exited'      │  ← Çıkış Yapıldı / Arşivlendi
      │ (entry_logs güncellenir)  │
      └───────────────────────────┘
```

### 2.2 Veritabanı Şeması (`database.db`)

#### Tablo: `customer_presence` (Aktif Mekan Oturumları)
```sql
CREATE TABLE IF NOT EXISTS customer_presence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL, -- 'customer' | 'guest'
    face_image TEXT,         -- Anlık kırpılan yüz veya profil görseli yolu
    status TEXT NOT NULL DEFAULT 'waiting_order', -- 'waiting_order', 'ordered', 'exited'
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_summary TEXT,     -- Alınan sipariş ürünleri özeti
    notes TEXT              -- Garsonun müşteri için düştüğü anlık not
);
```

#### Tablo: `system_settings` (Ayarlar ve İsteğe Bağlı Token)
```sql
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT
);
-- Örn: 'gemini_api_key', 'ai_speech_enabled'
```

---

## 3. Hibrit Akıllı Öneri Algoritması (Contextual AI Engine)

Sistem öneri üretirken iki seviyeli **Hibrit Zeka Modeli** kullanır:

### Seviye 1: Ultra Hızlı Matematiksel Skorlama Motoru (0ms, %100 Yerel ve Çevrimdışı)

Her menü ürünü ($P_i$) için durumsal uygunluk skoru hesaplanır:

$$\text{Skor}(P_i) = S_{\text{geçmiş}} + S_{\text{hava}} + S_{\text{saat}} + S_{\text{trend}}$$

1. **Geçmiş Sipariş & Afinite ($S_{\text{geçmiş}}$ - Max 60 puan):**
   - Müşteri bu ürünü daha önce $N$ kez aldıysa: $N \times 25$ puan.
   - Son 3 siparişinden biriyse (Recency): $+15$ puan.
   - Müşterinin en çok sipariş verdiği kategorideki diğer ürünlere: $+10$ puan.
2. **Hava Durumu Uyumu ($S_{\text{hava}}$ - Max 30 puan):**
   - Sıcaklık $\ge 22^\circ\text{C}$ (Sıcak/Güneşli): Soğuk İçecek, Buzlu Latte, Frappe, Limonata $+30$ puan.
   - Sıcaklık $\le 17^\circ\text{C}$ veya Yağmurlu: Sıcak Filtre Kahve, Cappuccino, Sıcak Çikolata, Sıcak Kruvasan $+30$ puan.
3. **Günün Saati & Öğün Uyumu ($S_{\text{saat}}$ - Max 25 puan):**
   - `07:00 - 11:30`: Kruvasan, Poğaça, Sandviç, Filtre Kahve, Portakal Suyu $+25$ puan.
   - `11:30 - 15:00`: Sandviçler, Soğuk/Sıcak Kahveler $+20$ puan.
   - `15:00 - 19:00`: San Sebastian, Cheesecake, Brownie, Latte, Çay $+25$ puan.
   - `19:00 - 24:00`: Kafeinsiz içecekler, tatlılar $+20$ puan.
4. **Kafe Popülerliği & Demografi ($S_{\text{trend}}$ - Max 15 puan):**
   - Kafede en çok satan ürünler $+10$ puan.
   - Yeni misafirler için yaş/cinsiyet trendleri devreye girer.

En yüksek puanlı **ilk 3-4 ürün** "Akıllı Öneriler" olarak seçilir.

### Seviye 2: Garson Konuşma Asistanı (Waiter Pitch Generator)

1. **Yerel NLP Şablon Motoru (Varsayılan):**
   - Saat, hava durumu ve seçilen 1 numaralı öneriye göre akıcı Türkçe hitap üretir.
   - *Örnek (Kayıtlı):* *"Ahmet Bey hoş geldiniz! Bugün hava oldukça sıcak, favoriniz olan Buzlu Karamel Latte hazırlayalım mı, yanında yeni fırından çıkan Kruvasan ile?"*
   - *Örnek (Misafir):* *"Hoş geldiniz! Şu an ikindi saatindeyiz; şefimizin yeni çıkardığı San Sebastian Cheesecake ve Sıcak Latte ikilisini denemek ister misiniz?"*
2. **İsteğe Bağlı Gemini LLM Katmanı (Token girildiyse):**
   - Dükkan sahibi ayarlar tablosuna `gemini_api_key` girmişse, arka planda kısa bir prompt ile esprili, samimi ve doğal alternatif replikler üretilir. Hata veya internet kesintisinde anında Seviye 1 yerel şablonuna düşülür (graceful fallback).

---

## 4. Kullanıcı Arayüzü & Garson Deneyimi (UI/UX)

`/` rotası (Müşteri Kiosk yerine) tam ekran, modern ve karanlık temalı **Garson Servis Terminali**'ne dönüşür:

### 4.1 Ekran Düzeni
1. **Üst Çubuk (Topbar):**
   - Kafe Başlığı & Logo
   - Canlı Saat & Tarih
   - Canlı Hava Durumu Kartı (Örn: *☀️ 26°C Güneşli - İstanbul*)
   - Sayaç Rozetleri: `🟢 2 Sipariş Bekleyen | 🟡 5 Masada`
   - Sesli Bildirim Anahtarı (Yeni girişlerde 'Ding' sesi)
   - Yönetici Paneli Bağlantısı (`/admin`)
2. **Sol Panel (Dükkandaki Canlı Müşteriler - %35 Genişlik):**
   - İki ana sekme veya alt alta liste:
     - **🟢 Sipariş Bekleyenler:** Yeni giren müşteriler yeşil çerçeve ve nabız efektiyle listelenir.
     - **🟡 Masada Olanlar:** Siparişi alınmış oturan müşteriler.
   - Kart Bileşeni: Canlı yüz fotoğrafı, isim, içeride kaldığı süre, durum rozeti.
3. **Sağ Panel (Müşteri Zekası & Hızlı Sipariş - %65 Genişlik):**
   - Seçilen müşterinin detayları: Profil resmi, isim, toplam ziyaret, toplam harcama, notlar.
   - **AI Konuşma Asistanı Balonu:** Garsonun masada söyleyeceği hazır replik.
   - **Önerilen Ürünler Izgarası (3-4 Kart):** Ürün resmi, isim, fiyat, önerilme nedeni rozeti ve `+ Ekle` butonu.
   - **Tüm Menü Sekmesi:** İstenirse diğer menü ürünlerinden de seçim yapma olanağı.
   - **Aksiyon Barı:**
     - `[ Siparişi Onayla & Masaya İşle ]` (Müşteriyi 'Masada Olanlar'a aktarır)
     - `[ Masadan Ayrıldı / Çıkış ]` (Müşteriyi mekandan düşürür)

---

## 5. API Uç Noktaları (RESTful API)

| Metot | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/api/waiter/presence` | Dükkanda bulunan aktif müşterileri (`waiting_order`, `ordered`) gruplayarak döndürür. |
| `POST` | `/api/waiter/set_status` | Müşterinin durumunu değiştirir (`waiting_order` -> `ordered` veya `exited`). |
| `GET` | `/api/waiter/recommendations/<user_name>` | Seçilen müşteri için Seviye 1 ve Seviye 2 önerileri ile konuşma repliğini döndürür. |
| `POST` | `/api/waiter/create_order` | Seçilen müşteri için hızlı sipariş oluşturur ve müşteriyi `ordered` durumuna geçirir. |
| `POST` | `/api/waiter/notes` | Garsonun müşteri için düştüğü notu kaydeder. |
| `POST` | `/api/settings/gemini_token` | Admin panelinden opsiyonel Gemini API anahtarını kaydeder. |

---

## 6. Güvenilirlik & Hata Yönetimi

1. **Kamera Takibi Güvenliği:** Kamera geniş açıda bir kişiyi 2-3 saniye kaçırsa bile mekan oturumu hemen silinmez (`last_seen_time` toleransı 5 dakikadır). Garson istediği zaman tek tıkla masayı kapatabilir.
2. **Çevrimdışı Çalışma Garantisi:** Gemini API anahtarı olsun veya olmasın, internet olmasa bile yerel öneri algoritması ve yerel şablonlar milisaniye seviyesinde çalışır.
3. **Müşteri Ayrışımı:** Kayıtlı müşteriler yeşil ve isimli rozetle, yeni tanınmayan müşteriler `Misafir #X` geçici kimliğiyle kusursuz şekilde yönetilir.
