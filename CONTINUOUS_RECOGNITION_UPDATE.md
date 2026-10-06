# Sürekli Yüz Tanıma Sistemi Güncellemesi

## Yapılan Değişiklikler

### 1. Backend (app.py)

#### Yeni Fonksiyonlar
- **`get_next_guest_id()`** - Veritabanında kayıtlı Guest'leri kontrol eder ve sonraki Guest ID'yi döner
- **`save_guest_from_frame(face_encoding, guest_name)`** - Bilinmeyen yüzü Guest olarak kaydeder, veritabanına ekler ve klasör oluşturur

#### Güncellenmiş Fonksiyonlar
- **`read_camera_loop()`** 
  - Real-time yüz tanıma işlemi eklendi
  - Performans için her 3. frame'de tanıma yapılıyor
  - Tanınan yüzlere bounding box ve isim çiziliyor
  - Tanınmayan yüzler otomatik "Guest_X" olarak kaydediliyor

#### Yeni API Endpoints
1. **`POST /api/toggle_recognition`** (Admin)
   - Yüz tanıma işlemini açıp kapatır
   - Request: `{ "enabled": true/false }`

2. **`GET /api/current_recognized_person`**
   - Şu anki tanınan kişinin bilgisini döner
   - Response: Kişi bilgileri (ad, fotoğraf, son giriş tarihi, harcama)

3. **`POST /api/rename_guest/<old_name>/<new_name>`** (Admin)
   - Guest isimlerini gerçek isimle değiştirir
   - Guest klasörü ve veritabanı kaydı güncellenir

#### Video Feed Değişiklikleri
- **`GET /video_feed`** - Artık bounding box ve isim ile processed frame'leri gösterir
- **`GET /video_feed_raw`** - Ham frame'leri gösterir (eski /video_feed davranışı)

---

### 2. Frontend (main.js)

#### Yeni Fonksiyonlar
- **`startContinuousRecognition()`**
  - Backend'de tanımayı açar
  - Her 500ms'de `/api/current_recognized_person` polling yaparak UI günceller

- **`clearRecognizedUser()`**
  - Tanınan kişi bilgisini temizler
  - UI'yi "No entrance" durumuna döndürür

- **`stopContinuousRecognition()`**
  - Polling'i durdurur
  - Backend'de tanımayı kapatır

#### Güncellenmiş Fonksiyonlar
- **`DOMContentLoaded`** - Sayfa yüklendiğinde `startContinuousRecognition()` çağrılıyor
- **`stopRecognition()`** - Frontend ve backend tanımayı durdurur

---

### 3. Frontend (customers.js)

#### Güncellenmiş Fonksiyonlar
- **`displayCustomers()`**
  - Guest isimleri için "Adı Değiştir" butonu eklendi
  - Sadece "Guest_" ile başlayan isimlere bu butonu gösterir

#### Yeni Fonksiyonlar
- **`renameGuest(oldName)`**
  - Admin tarafından Guest isimlerini değiştirmek için kullanılır
  - Prompt ile yeni isim alır
  - `/api/rename_guest/<old>/<new>` API'sini çağırır

---

## Sistem Çalışış Akışı

### 1. Sistem Başlangıcı
```
1. Flask uygulaması başlar
2. Veritabanı initialize edilir
3. Modeller eğitilir (train_model)
4. Known faces yüklenir (load_known_faces)
5. Kamera başlatılır
6. read_camera_loop thread'i başlatılır
```

### 2. Anasayfaya Giriş (index.html)
```
1. Sayfa yüklenir
2. startContinuousRecognition() çağrılır
3. Backend: RECOGNITION_ENABLED = True yapılır
4. Frontend: 500ms'de bir polling başlar
```

### 3. Yüz Tanıma Döngüsü (read_camera_loop)
```
Her frame:
  → latest_raw_frame güncellenir
  
Her 3. frame:
  → Yüz locations tespit edilir
  → Face encodings çıkartılır
  
Her yüz için:
  → Bilinen yüzlerle karşılaştırılır (tolerance=0.6)
  
  Eğer tanınırsa:
    → isim = tanınan kişi
    → Veritabanında son_giriş_tarihi güncellenir
  
  Eğer tanınmazsa:
    → guest_id = get_next_guest_id()
    → isim = f"Guest_{guest_id}"
    → save_guest_from_frame() çağrılıyor
    → known_faces reload edilir
  
  → Bounding box + isim processed_frame'e çizilir
  → last_recognized_name güncellenir
```

### 4. Frontend Polling Döngüsü (her 500ms)
```
1. /api/current_recognized_person çağrılır
2. Dönüş: Tanınan kişi bilgileri
3. updateRecognizedUser() çağrılıyor
   → Ad, fotoğraf, son giriş tarihi, harcama güncellenir
   → Order history, food preferences güncellenir
```

### 5. Guest Adı Değiştirme (Admin)
```
1. Customers sayfasında Guest'i seç
2. "Adı Değiştir" butonu → renameGuest()
3. Prompt'ta yeni isim gir
4. /api/rename_guest/<old>/<new> çağrılır
   → Veritabanında isim güncellenir
   → Klasör adı değiştirilir
   → known_faces reload edilir
5. Customers listesi yenilenir
```

---

## Tolerans Değerleri

- **Face Matching Tolerance**: 0.6
  - Değeri düşürürseniz: Daha katı karşılaştırma (false positive az)
  - Değeri yükseltirseniz: Daha esnek karşılaştırma (recognition daha iyi)

---

## Performance Optimizasyonları

1. **Her 3. frame'de tanıma**: read_camera_loop içinde `RECOGNITION_EVERY_N_FRAMES = 3`
2. **0.25 ölçek ile resize**: Face detection daha hızlı
3. **500ms polling**: Sunucuya fazla yük bindirmiyor
4. **Threading**: Kamera okuma ve tanıma ayrı thread'lerde

---

## Test Edilecek Senaryolar

✅ **Sistem Başlanğıcı**
- Kamera başlar
- Known faces yüklenir
- read_camera_loop çalışır

✅ **Anasayfada Yüz Tanıma**
- Index.html açılır
- Startcontinuous recognition başlar
- Bilinen kişi tanınırsa → Bilgileri gösterilir
- Bilinmeyen yüz → Guest_1, Guest_2, ... kaydedilir

✅ **Guest Adı Değiştirme**
- Admin → Customers
- Guest_1 → "Adı Değiştir"
- Yeni isim gir
- Veritabanı ve klasör güncellenir

✅ **Kamera Modunu Kapatma**
- "Show Cam" butonu → Polling durdurulur
- RECOGNITION_ENABLED = False yapılır

---

## Bilinen Sınırlamalar

1. **Tolerance Tuning**: Face matching tolerance'ı gerekirse ayarlayabilirsiniz (tolerance=0.6)
2. **Multiple Faces**: Aynı frame'de birden fazla yüz var ise, first match'i tanır
3. **Guest Kaydı**: Sadece 1 frame'den encoding yapıldığı için accuracy sınırlı olabilir
4. **Performance**: 3840x2160 gibi çok yüksek çözünürlüklerde performans düşebilir

---

## Debugging

### Log Çıktıları
- `[INFO]` - Normal bilgi mesajları
- `[WARNING]` - Uyarı mesajları (örn: kamera bağlantısı koptu)
- `[HATA]` - Hata mesajları

### Common Issues

1. **Guest kaydı başarısız**
   - Dosya izni kontrol edin (dataset/ klasörü yazılabilir mi?)
   - Diskli boş yer kontrol edin

2. **Tanıma %0 başarı**
   - Tolerance değerini artırın (0.6 → 0.7)
   - Daha iyi aydınlatma sağlayın
   - Face rotation'u minimize edin

3. **Polling hatası**
   - Browser console'da hata kontrolü
   - Backend logs'u kontrol edin

---

## Gelecek İyileştirmeler

- [ ] Guest kaydında 5 frame kullanarak averaging yapma
- [ ] Kişi çıkış detection'ı
- [ ] Real-time stats dashboard
- [ ] Export tanıma logs (CSV)
