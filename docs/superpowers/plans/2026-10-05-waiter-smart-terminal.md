# Garson Servis & Akıllı Müşteri Öneri Terminali (Waiter POS AI) Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mevcut müşteri kiosk ekranını (`/`), dükkana giren müşterileri geniş açılı kamera ile otomatik algılayan, geçmiş tercihler, hava durumu ve günün saatine göre durumsal AI önerileri ve garson hitap repliği sunan, masadaki müşterilerin sipariş ve çıkış döngüsünü yöneten modern bir Garson Servis Terminali'ne dönüştürmek.

**Architecture:** Geniş açılı mekan kamerasının (`recognition_service.py`) algıladığı yüzler SQLite `customer_presence` tablosunda oturum açar (`waiting_order`). `recommendation_service.py` içindeki hibrit zeka motoru (0ms matematiksel skorlama + yerel NLP şablonu + opsiyonel Gemini token desteği) nokta atışı 3-4 öneri ve konuşma metni üretir. `templates/index.html`, `static/waiter.css` ve `static/waiter.js` üzerinden çalışan iki bölmeli Garson Terminali anlık bildirim, hızlı sipariş ve çıkış yönetimini sağlar.

**Tech Stack:** Python 3.10, Flask, SQLite3, InsightFace Buffalo_L / UniFace, Vanilla JS (ES6+), HTML5/CSS3 (Glassmorphism Dark Theme).

## Global Constraints
- Python komutları daima `.\venv\Scripts\python.exe` ile çalıştırılacaktır.
- Arka planda sunucu açık bırakılmayacaktır; testler bittiğinde süreçler kapatılacaktır.
- Hibrit öneri motoru internet veya harici API olmadan (%100 yerel ve çevrimdışı) hatasız çalışacaktır.
- Mevcut `/admin` yönetim paneli ve `/api/products` gibi mevcut yapılar bozulmadan korunacaktır.

---

### Task 1: Veritabanı & Mekan Varlık Şeması (`database.py`)

**Files:**
- Modify: `database.py`
- Test: `tests/test_presence_db.py`

**Interfaces:**
- Consumes: `get_db_connection()`
- Produces: `customer_presence` tablosu, `system_settings` tablosu, `add_or_update_presence(user_name, user_type, face_image)`, `get_active_presences()`, `set_presence_status(presence_id, status, order_summary)`, `get_setting(key)`, `set_setting(key, value)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_presence_db.py`:
```python
import unittest
import sqlite3
import os
from database import (
    init_db,
    add_or_update_presence,
    get_active_presences,
    set_presence_status,
    get_setting,
    set_setting,
    get_db_connection
)

class TestPresenceDB(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_presence_lifecycle(self):
        # 1. Yeni müşteri girişi
        pid = add_or_update_presence("Eren", "customer", "/static/profiles/eren.jpg")
        self.assertIsNotNone(pid)

        # 2. Aktif müşterileri listele
        presences = get_active_presences()
        waiting = [p for p in presences if p["status"] == "waiting_order" and p["user_name"] == "Eren"]
        self.assertEqual(len(waiting), 1)

        # 3. Sipariş alındı durumuna geçir
        set_presence_status(pid, "ordered", order_summary="Filtre Kahve, Kruvasan")
        presences_after = get_active_presences()
        ordered = [p for p in presences_after if p["status"] == "ordered" and p["user_name"] == "Eren"]
        self.assertEqual(len(ordered), 1)

        # 4. Çıkış yap
        set_presence_status(pid, "exited")
        presences_final = get_active_presences()
        remaining = [p for p in presences_final if p["id"] == pid]
        self.assertEqual(len(remaining), 0)

    def test_system_settings(self):
        set_setting("gemini_api_key", "test_key_12345")
        val = get_setting("gemini_api_key")
        self.assertEqual(val, "test_key_12345")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\python.exe tests/test_presence_db.py`
Expected: FAIL with `ImportError: cannot import name 'add_or_update_presence'`

- [ ] **Step 3: Implement presence schema and functions in `database.py`**

In `database.py`, add table creation in `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS customer_presence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    user_type TEXT NOT NULL DEFAULT 'customer',
    face_image TEXT,
    status TEXT NOT NULL DEFAULT 'waiting_order',
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_summary TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS system_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT
);
```

Add functions:
```python
def add_or_update_presence(user_name, user_type='customer', face_image=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if already active in venue (waiting_order or ordered)
    cursor.execute("""
        SELECT id, status FROM customer_presence 
        WHERE user_name = ? AND status IN ('waiting_order', 'ordered')
        ORDER BY id DESC LIMIT 1
    """, (user_name,))
    row = cursor.fetchone()
    
    if row:
        pid = row["id"]
        # Update last seen timestamp and face image if provided
        if face_image:
            cursor.execute("""
                UPDATE customer_presence 
                SET last_seen_time = CURRENT_TIMESTAMP, face_image = ?
                WHERE id = ?
            """, (face_image, pid))
        else:
            cursor.execute("""
                UPDATE customer_presence 
                SET last_seen_time = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (pid,))
        conn.commit()
        conn.close()
        return pid
    else:
        cursor.execute("""
            INSERT INTO customer_presence (user_name, user_type, face_image, status, entry_time, last_seen_time)
            VALUES (?, ?, ?, 'waiting_order', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (user_name, user_type, face_image))
        pid = cursor.lastrowid
        conn.commit()
        conn.close()
        return pid

def get_active_presences():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, user_type, face_image, status, entry_time, last_seen_time, order_summary, notes
        FROM customer_presence
        WHERE status IN ('waiting_order', 'ordered')
        ORDER BY 
            CASE status WHEN 'waiting_order' THEN 1 ELSE 2 END,
            entry_time DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def set_presence_status(presence_id, status, order_summary=None, notes=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?", "last_seen_time = CURRENT_TIMESTAMP"]
    params = [status]
    if order_summary is not None:
        updates.append("order_summary = ?")
        params.append(order_summary)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    params.append(presence_id)
    
    cursor.execute(f"UPDATE customer_presence SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["setting_value"] if row else default

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_settings (setting_key, setting_value) 
        VALUES (?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
    """, (key, value))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\python.exe tests/test_presence_db.py`
Expected: Ran 2 tests in ...s, OK

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_presence_db.py
git commit -m "feat(db): add customer presence and system settings tables and helpers"
```

---

### Task 2: Durumsal Akıllı Öneri Algoritması & Garson Konuşma Asistanı (`recommendation_service.py`)

**Files:**
- Modify: `recommendation_service.py`
- Test: `tests/test_contextual_recommendations.py`

**Interfaces:**
- Consumes: `get_db_connection()`, `get_setting("gemini_api_key")`
- Produces: `get_contextual_recommendations(user_name, weather_data=None, current_hour=None)` -> `{"recommendations": [...], "waiter_pitch": "...", "context": {...}}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_contextual_recommendations.py`:
```python
import unittest
from recommendation_service import recommendation_service

class TestContextualRecommendations(unittest.TestCase):
    def test_hot_weather_recommendations(self):
        # 30 derece sıcak hava ve ikindi saatinde (16:00)
        res = recommendation_service.get_contextual_recommendations(
            user_name="Eren",
            weather_data={"temp": 30.0, "description": "Güneşli"},
            current_hour=16
        )
        self.assertIn("recommendations", res)
        self.assertIn("waiter_pitch", res)
        self.assertGreaterEqual(len(res["recommendations"]), 1)
        # Önerilen ilk ürünlerden biri soğuk kategori veya tatlı olmalı
        recs = res["recommendations"]
        badges = [r.get("reason_badge", "") for r in recs]
        self.assertTrue(any("Sıcak Hava" in b or "İkindi" in b or "Favori" in b for b in badges))

    def test_cold_morning_recommendations(self):
        # 10 derece soğuk hava ve sabah saatinde (09:00)
        res = recommendation_service.get_contextual_recommendations(
            user_name="Misafir #1",
            weather_data={"temp": 10.0, "description": "Soğuk ve Yağmurlu"},
            current_hour=9
        )
        self.assertIn("recommendations", res)
        self.assertIn("waiter_pitch", res)
        recs = res["recommendations"]
        badges = [r.get("reason_badge", "") for r in recs]
        self.assertTrue(any("Sabah" in b or "Soğuk Hava" in b or "Popüler" in b for b in badges))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\python.exe tests/test_contextual_recommendations.py`
Expected: FAIL with `AttributeError: 'RecommendationService' object has no attribute 'get_contextual_recommendations'`

- [ ] **Step 3: Implement contextual algorithm and speech generator in `recommendation_service.py`**

In `recommendation_service.py`, add `get_contextual_recommendations(self, user_name=None, weather_data=None, current_hour=None)`:
- Retrieve menu products from `products`.
- Parse `weather_data` (default temperature: 22.0 if not provided).
- Determine current hour (default: `datetime.now().hour` if not provided).
- Calculate:
  - User history score (frequency, recency, category affinity).
  - Weather score: If `temp >= 22`: Soğuk İçecek, Buzlu Kahve, Limonata get +30. If `temp <= 17`: Sıcak Kahve, Sıcak Çikolata, Kruvasan get +30.
  - Meal/Hour score: `7 <= hour < 11.5`: Kahvaltı/Kruvasan/Sandviç +25. `11.5 <= hour < 15`: Sandviç +20. `15 <= hour < 19`: Tatlı/Espresso/Çay +25.
  - Overall popularity score.
- Attach `reason_badge` to each product (e.g., `"⭐ Favoriniz (3 kez)"`, `"❄️ Sıcak Hava Önerisi (30°C)"`, `"🥐 Sabah Kahvaltısı"`, `"🍰 İkindi Tatlısı"`).
- Select top 3-4 products.
- Generate `waiter_pitch`:
  - Check if `gemini_api_key` exists in `system_settings`. If so, optionally attempt quick generation with 1.5s timeout.
  - Fallback to natural Turkish NLP template:
    - If user has favorite: *"{name} hoş geldiniz! Bugün hava {temp_desc}; favoriniz olan {top_prod} hazırlayalım mı, yanında taze {second_prod} ile?"*
    - If guest / new: *"Hoş geldiniz! Şu an {time_desc} saatindeyiz; şefimizin önerisi {top_prod} ve yanında {second_prod} denemek ister misiniz?"*

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\python.exe tests/test_contextual_recommendations.py`
Expected: Ran 2 tests in ...s, OK

- [ ] **Step 5: Commit**

```bash
git add recommendation_service.py tests/test_contextual_recommendations.py
git commit -m "feat(ai): implement contextual recommendation scoring and waiter pitch generator"
```

---

### Task 3: Backend Garson REST API'leri & Kamera Varlık Entegrasyonu (`app.py`)

**Files:**
- Modify: `app.py`, `recognition_service.py`
- Test: `tests/test_waiter_api.py`

**Interfaces:**
- Consumes: `database.py` (presence functions), `recommendation_service.py`
- Produces:
  - `GET /api/waiter/presence`
  - `POST /api/waiter/set_status`
  - `GET /api/waiter/recommendations/<user_name>`
  - `POST /api/waiter/create_order`
  - `POST /api/waiter/notes`
  - `POST /api/settings/gemini_token`

- [ ] **Step 1: Write the failing test**

Create `tests/test_waiter_api.py`:
```python
import unittest
import json
from app import app
from database import add_or_update_presence, get_active_presences, set_presence_status

class TestWaiterAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_waiter_presence_and_status(self):
        # 1. Simüle varlık oluştur
        pid = add_or_update_presence("Eren", "customer")
        
        # 2. GET /api/waiter/presence
        res = self.client.get('/api/waiter/presence')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("waiting", data)
        self.assertIn("ordered", data)

        # 3. POST /api/waiter/set_status (ordered yap)
        res_status = self.client.post('/api/waiter/set_status', json={
            "presence_id": pid,
            "status": "ordered",
            "order_summary": "Espresso"
        })
        self.assertEqual(res_status.status_code, 200)
        self.assertTrue(res_status.get_json().get("success"))

        # 4. GET /api/waiter/recommendations/Eren
        res_rec = self.client.get('/api/waiter/recommendations/Eren')
        self.assertEqual(res_rec.status_code, 200)
        rec_data = res_rec.get_json()
        self.assertIn("recommendations", rec_data)
        self.assertIn("waiter_pitch", rec_data)

        # 5. Temizle (exited yap)
        self.client.post('/api/waiter/set_status', json={
            "presence_id": pid,
            "status": "exited"
        })

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\python.exe tests/test_waiter_api.py`
Expected: FAIL with 404 Not Found on `/api/waiter/presence`

- [ ] **Step 3: Implement Waiter endpoints in `app.py` & trigger in `recognition_service.py`**

In `app.py`, implement:
- `GET /api/waiter/presence`: calls `get_active_presences()`, partitions into `waiting` (`status == 'waiting_order'`) and `ordered` (`status == 'ordered'`), calculating minutes elapsed since `entry_time`.
- `POST /api/waiter/set_status`: receives `presence_id`, `status` (`waiting_order`, `ordered`, `exited`), optional `order_summary`, and calls `set_presence_status()`.
- `GET /api/waiter/recommendations/<user_name>`: fetches live weather from `get_weather()` helper, calls `recommendation_service.get_contextual_recommendations(user_name, weather)`.
- `POST /api/waiter/create_order`: receives `presence_id`, `user_name`, `items` (`[{"product_id": 1, "product_name": "Espresso", "price": 45, "quantity": 1}]`), inserts into `orders` & `order_items`, updates user `total_spent`, and updates presence status to `ordered` with order summary.
- `POST /api/waiter/notes`: receives `presence_id`, `notes`, updates note on presence.
- `POST /api/settings/gemini_token`: saves token to `set_setting("gemini_api_key", token)`.

In `recognition_service.py`:
- In the frame processing loop where an identity is confirmed (either returning registered customer or assigned guest), call `add_or_update_presence(user_name, user_type, profile_image)` with a throttled check (e.g. once every 5 seconds per user) so recognized people automatically populate the Waiter terminal!

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\python.exe tests/test_waiter_api.py`
Expected: Ran 1 test in ...s, OK

- [ ] **Step 5: Commit**

```bash
git add app.py recognition_service.py tests/test_waiter_api.py
git commit -m "feat(api): add waiter presence, recommendation and order endpoints with camera integration"
```

---

### Task 4: Garson Terminali Arayüzü & Tasarımı (`templates/index.html` & `static/waiter.css`)

**Files:**
- Modify: `templates/index.html`
- Create: `static/waiter.css`

**Interfaces:**
- Consumes: `/api/waiter/presence`, `/api/waiter/recommendations/<name>`, `/api/weather`, `/api/products`
- Produces: Modern 2-column layout (Left: Active presence stream with waiting & seated tabs; Right: Customer intelligence header, AI Waiter Pitch bubble, Contextual recommendation grid with +Add button, quick order cart, and status change buttons).

- [ ] **Step 1: Create `static/waiter.css` with responsive dark glassmorphic styling**

Include:
- Layout: Topbar (`.waiter-topbar`), Main Container (`.waiter-container`), Left Panel (`.presence-sidebar`, 360px-420px), Right Panel (`.customer-detail-panel`, flex: 1).
- Badges: `.badge-waiting` (glowing green pulse animation `@keyframes pulse-ring`), `.badge-seated` (subtle amber), `.badge-time` (elapsed time chip).
- Customer presence card (`.presence-card`): hover effects, active border, thumbnail `.presence-avatar`, title and meta.
- AI Pitch Card (`.ai-pitch-card`): gradient border, glowing robot/chat icon, prominent italic quote styling.
- Recommendation Cards (`.rec-product-card`): image thumbnail, reason tag (`.rec-reason-badge`), price, quick add button.
- Cart & Action footer (`.waiter-action-footer`): "Siparişi Onayla & Masaya İşle" (`.btn-confirm-order`), "Masadan Ayrıldı / Çıkış" (`.btn-checkout`).

- [ ] **Step 2: Update `templates/index.html`**

Replace old customer self-service kiosk markup with the new Waiter POS Terminal structure:
- Modern header with Kafe logo, live clock, weather widget, counter badges (`#waitingCount`, `#seatedCount`), sound toggle button, and Admin Panel link.
- Two-column view:
  - Left: Search filter, tabs ("Tümü", "Bekleyenler", "Masadakiler"), `#presenceList` container.
  - Right: Empty state placeholder when no customer is selected (`"Masadaki veya yeni giriş yapan bir müşteriyi seçin"`), and `#customerDetailView` containing:
    - Customer profile header (Photo, Name, Visits count, Total Spent, Notes input).
    - `#waiterPitchBox` (AI speech bubble).
    - `#contextualRecsGrid` (3-4 smart recommendation cards).
    - `#orderItemsList` and quick total.
    - Action buttons: "Siparişi Onayla & Masaya Aktar" (`#btnCompleteOrder`) and "Masadan Ayrıldı" (`#btnExitCustomer`).

- [ ] **Step 3: Verify HTML and CSS files exist and link properly**

Run: `node --check static/waiter.js` (once created) and inspect template syntax.

- [ ] **Step 4: Commit**

```bash
git add templates/index.html static/waiter.css
git commit -m "feat(ui): convert index.html into waiter service terminal with waiter.css"
```

---

### Task 5: Garson Terminali İstemci Mantığı (`static/waiter.js`)

**Files:**
- Create: `static/waiter.js`

**Interfaces:**
- Consumes: All `/api/waiter/*` endpoints, HTML elements in `templates/index.html`.
- Produces: `class WaiterTerminal` with live polling (every 2.5s), audio chime on new `waiting_order`, dynamic card rendering, selection and fetching of contextual recommendations, cart management, and order placement.

- [ ] **Step 1: Implement `static/waiter.js`**

Implement complete `WaiterTerminal` class:
```javascript
class WaiterTerminal {
    constructor() {
        this.selectedPresenceId = null;
        this.selectedCustomerName = null;
        this.presences = { waiting: [], ordered: [] };
        this.currentOrderItems = [];
        this.soundEnabled = true;
        this.pollInterval = null;
        this.init();
    }
    // init, setupEventListeners, startPolling, fetchPresences, renderPresenceList
    // playChimeSound (Web Audio API synthetic chime or clean audio beep)
    // selectCustomer(presenceId, customerName)
    // fetchRecommendations(customerName)
    // renderRecommendations(data)
    // addItemToOrder(product)
    // removeItemFromOrder(index)
    // submitOrder() -> POST /api/waiter/create_order
    // markAsExited(presenceId) -> POST /api/waiter/set_status
    // saveCustomerNote(presenceId, notes)
}
```

- [ ] **Step 2: Validate JavaScript syntax**

Run: `node --check static/waiter.js`
Expected: Exited with code 0.

- [ ] **Step 3: Commit**

```bash
git add static/waiter.js
git commit -m "feat(client): implement waiter terminal interactive logic, polling, audio and ordering"
```

---

### Task 6: Uçtan Uca Doğrulama & Süreç Kontrolü

**Files:**
- Modify: `task.md`

- [ ] **Step 1: Run complete test suite**

Run:
```bash
.\venv\Scripts\python.exe tests/test_presence_db.py
.\venv\Scripts\python.exe tests/test_contextual_recommendations.py
.\venv\Scripts\python.exe tests/test_waiter_api.py
```
Expected: All tests PASS.

- [ ] **Step 2: Verify Python compilation of all modified files**

Run: `.\venv\Scripts\python.exe -m py_compile app.py database.py recommendation_service.py`
Expected: Exited with code 0.

- [ ] **Step 3: Verify all background processes are closed**

Run: `Get-Process -Name python, mediamtx -ErrorAction SilentlyContinue`
Ensure no unintended background servers remain active.

- [ ] **Step 4: Update `task.md` and commit**

```bash
git add task.md
git commit -m "docs: update task list with completed waiter smart terminal implementation"
```
