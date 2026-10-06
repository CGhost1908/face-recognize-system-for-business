from datetime import datetime
from database import get_db_connection


class RecommendationService:
    """
    Personalized Customer-Centric Recommendation Engine & Order Management.
    Features:
    - User Order Frequency & Recency Weighting
    - Category Affinity Modeling
    - Dynamic Favorite & Recommendation Badges
    - Flexible Order Placement (IDs, Product Names, or String Lists)
    - Automatic Total Spent Tracking
    """

    def get_products_for_user(self, user_name=None):
        """
        Returns all active products sorted so recommended items appear at the top.
        - For recognized returning customers: Products they frequently order appear first with 'Favoriniz' badge.
        - For new users / guests: Cafe-wide top sellers appear first.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all menu products
        cursor.execute("SELECT id, product_name, category, price, description, image_url FROM products")
        products = [dict(row) for row in cursor.fetchall()]

        if not products:
            conn.close()
            return []

        user_item_counts = {}
        user_category_counts = {}
        recent_item_ids = set()
        cafe_item_counts = {}

        # 1. Fetch overall cafe product sales popularity
        cursor.execute("""
            SELECT product_id, SUM(quantity) as total_qty
            FROM order_items
            GROUP BY product_id
        """)
        for row in cursor.fetchall():
            cafe_item_counts[row["product_id"]] = row["total_qty"]

        # 2. Fetch specific user order history if user_name is provided
        if user_name:
            # Query itemized order history
            cursor.execute("""
                SELECT oi.product_id, p.category, SUM(oi.quantity) as user_qty
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                WHERE o.user_name = ? OR o.name = ?
                GROUP BY oi.product_id, p.category
            """, (user_name, user_name))
            for row in cursor.fetchall():
                pid = row["product_id"]
                cat = row["category"]
                qty = row["user_qty"]
                user_item_counts[pid] = qty
                user_category_counts[cat] = user_category_counts.get(cat, 0) + qty

            # Query last 3 orders for recency boost
            cursor.execute("""
                SELECT oi.product_id
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                WHERE o.user_name = ? OR o.name = ?
                ORDER BY o.id DESC
                LIMIT 10
            """, (user_name, user_name))
            for row in cursor.fetchall():
                recent_item_ids.add(row["product_id"])

        conn.close()

        # 3. Calculate recommendation score and metadata for each product
        has_user_history = len(user_item_counts) > 0

        for p in products:
            pid = p["id"]
            cat = p["category"]
            user_qty = user_item_counts.get(pid, 0)
            cat_qty = user_category_counts.get(cat, 0)
            cafe_qty = cafe_item_counts.get(pid, 0)
            is_recent = pid in recent_item_ids

            if has_user_history:
                # High weight for directly ordered items, bonus for recency and favorite category
                score = (user_qty * 30) + (15 if is_recent else 0) + (cat_qty * 4) + (cafe_qty * 0.5)
                
                if user_qty >= 2:
                    p["badge"] = f"★ Favoriniz ({user_qty} kez)"
                    p["is_favorite"] = True
                    p["is_recommended"] = True
                elif user_qty == 1:
                    p["badge"] = "Daha Önce Sipariş Verildi"
                    p["is_favorite"] = False
                    p["is_recommended"] = True
                elif cat_qty > 0:
                    p["badge"] = f"Sevdiğiniz Kategori ({cat})"
                    p["is_favorite"] = False
                    p["is_recommended"] = True
                elif cafe_qty > 0:
                    p["badge"] = "Popüler Ürün"
                    p["is_favorite"] = False
                    p["is_recommended"] = False
                else:
                    p["badge"] = ""
                    p["is_favorite"] = False
                    p["is_recommended"] = False
            else:
                # Cafe-wide popularity for new guests
                score = cafe_qty * 5
                p["is_favorite"] = False
                p["is_recommended"] = cafe_qty > 0
                p["badge"] = "En Çok Satan" if cafe_qty > 0 else ""

            p["score"] = round(score, 1)
            p["user_order_count"] = user_qty
            # Legacy name alias support
            p["name"] = p["product_name"]

        # Sort products descending by score, then by product_name
        products.sort(key=lambda x: (x["score"], -x["id"]), reverse=True)
        return products

    def get_contextual_recommendations(self, user_name=None, weather_data=None, current_hour=None):
        """
        Calculates situational AI recommendations (top 3-4 products) and generates
        a personalized waiter speech card (waiter_pitch).
        Hybrid model:
        1. Fast mathematical scoring: user history + weather match + time-of-day match + cafe trends
        2. Natural Turkish waiter pitch generator (local NLP template + optional Gemini API hook)
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all menu products
        cursor.execute("SELECT id, product_name, category, price, description, image_url FROM products")
        products = [dict(row) for row in cursor.fetchall()]

        if not products:
            conn.close()
            return {"recommendations": [], "waiter_pitch": "Menüde henüz ürün bulunmuyor.", "context": {}}

        user_item_counts = {}
        user_category_counts = {}
        recent_item_ids = set()
        cafe_item_counts = {}

        # 1. Cafe sales popularity
        cursor.execute("""
            SELECT product_id, SUM(quantity) as total_qty
            FROM order_items
            GROUP BY product_id
        """)
        for row in cursor.fetchall():
            cafe_item_counts[row["product_id"]] = row["total_qty"]

        # 2. Specific user order history
        if user_name:
            cursor.execute("""
                SELECT oi.product_id, p.category, SUM(oi.quantity) as user_qty
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                WHERE o.user_name = ? OR o.name = ?
                GROUP BY oi.product_id, p.category
            """, (user_name, user_name))
            for row in cursor.fetchall():
                pid = row["product_id"]
                cat = row["category"]
                qty = row["user_qty"]
                user_item_counts[pid] = qty
                user_category_counts[cat] = user_category_counts.get(cat, 0) + qty

            cursor.execute("""
                SELECT oi.product_id
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                WHERE o.user_name = ? OR o.name = ?
                ORDER BY o.id DESC
                LIMIT 5
            """, (user_name, user_name))
            for row in cursor.fetchall():
                recent_item_ids.add(row["product_id"])

            # Query customer preferences table
            cursor.execute("SELECT food, preference FROM customer_preferences WHERE user_name = ?", (user_name,))
            user_preferences = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # Parse context parameters
        if current_hour is None:
            current_hour = datetime.now().hour

        if not weather_data or not isinstance(weather_data, dict):
            weather_data = {"temp": 22.0, "description": "Açık"}
        temp = float(weather_data.get("temp", 22.0))
        weather_desc = str(weather_data.get("description", "Açık"))

        has_user_history = len(user_item_counts) > 0
        display_name = user_name if user_name and not user_name.lower().startswith("guest") else "Müşteri"

        # Calculate scores
        for p in products:
            pid = p["id"]
            name = p["product_name"] or ""
            name_lower = name.lower()
            cat = p["category"] or ""
            cat_lower = cat.lower()

            user_qty = user_item_counts.get(pid, 0)
            cat_qty = user_category_counts.get(cat, 0)
            cafe_qty = cafe_item_counts.get(pid, 0)
            is_recent = pid in recent_item_ids

            score = 0.0
            reason_badge = ""

            # Check explicit customer preferences first
            if user_preferences:
                for pref in user_preferences:
                    food_term = (pref.get("food") or "").strip().lower()
                    pref_term = (pref.get("preference") or "").strip()
                    if food_term and (food_term in name_lower or food_term in cat_lower):
                        score += 50
                        reason_badge = f"🎯 Özel Tercih: {pref_term}" if pref_term else "🎯 Tercih Edilen"
                        break

            # A. User History Score (Highest Priority for Personalized AI)
            if has_user_history:
                if user_qty >= 2:
                    score += (user_qty * 40) + 30
                    if not reason_badge:
                        reason_badge = f"⭐ {display_name} Tercihi ({user_qty}x)"
                elif user_qty == 1:
                    score += 35
                    if not reason_badge:
                        reason_badge = f"Önceki Sipariş ({user_qty}x)"
                if is_recent:
                    score += 20
                if cat_qty > 0:
                    score += min(cat_qty * 5, 20)

            # B. Weather Context Score (Max ~35)
            is_cold_drink = any(k in name_lower or k in cat_lower for k in ["soğuk", "soguk", "cold", "buz", "portakal", "limonata", "frappe"])
            is_hot_drink = any(k in name_lower or k in cat_lower for k in ["sıcak", "sicak", "espresso", "americano", "latte", "cappuccino", "filtre", "türk", "turk", "çay", "cay"])
            is_bakery = any(k in name_lower or k in cat_lower for k in ["kruvasan", "sandviç", "sandvic", "cheesecake", "tatlı", "tatli", "pasta", "kurabiye"])

            if temp >= 22.0:
                if is_cold_drink:
                    score += 35
                    if not reason_badge:
                        reason_badge = f"❄️ Sıcak Hava Önerisi ({temp:.0f}°C)"
            elif temp <= 17.0:
                if is_hot_drink or is_bakery:
                    score += 35
                    if not reason_badge:
                        reason_badge = f"☕ Soğuk Hava Önerisi ({temp:.0f}°C)"

            # C. Meal / Time of Day Score (Max ~30)
            if 6 <= current_hour < 11.5:
                # Sabah Kahvaltısı
                if any(k in name_lower for k in ["kruvasan", "sandviç", "sandvic", "filtre", "portakal"]):
                    score += 30
                    if not reason_badge:
                        reason_badge = "🥐 Sabah Kahvaltısı"
            elif 11.5 <= current_hour < 15:
                # Öğle Molası
                if is_bakery or is_cold_drink:
                    score += 25
                    if not reason_badge:
                        reason_badge = "🥪 Öğle Molası"
            elif 15 <= current_hour < 19:
                # İkindi Çayı & Tatlısı
                if any(k in name_lower or k in cat_lower for k in ["cheesecake", "tatlı", "tatli", "kruvasan", "latte", "cappuccino", "çay", "cay"]):
                    score += 30
                    if not reason_badge:
                        reason_badge = "🍰 İkindi Tatlısı"
            else:
                # Akşam
                if is_bakery or is_hot_drink:
                    score += 20
                    if not reason_badge:
                        reason_badge = "🌙 Akşam Keyfi"

            # D. Overall Popularity
            score += cafe_qty * 1.5
            if not reason_badge:
                reason_badge = "🔥 Popüler Tercih" if cafe_qty > 0 else "✨ Şefin Tavsiyesi"

            p["score"] = round(score, 1)
            p["reason_badge"] = reason_badge
            p["user_order_count"] = user_qty

        # Sort descending by contextual score
        products.sort(key=lambda x: (x["score"], -x["id"]), reverse=True)
        top_recommendations = products[:4]

        # Generate Waiter Speech Card
        waiter_pitch = self._generate_waiter_pitch(user_name, top_recommendations, temp, current_hour, weather_desc)

        return {
            "success": True,
            "user_name": user_name,
            "recommendations": top_recommendations,
            "waiter_pitch": waiter_pitch,
            "context": {
                "temp": temp,
                "weather": weather_desc,
                "hour": current_hour
            }
        }

    def _generate_waiter_pitch(self, user_name, top_recommendations, temp, current_hour, weather_desc="Açık"):
        if not top_recommendations:
            return "Hoş geldiniz! Menümüzden dilediğiniz lezzeti hazırlayabiliriz."

        top1 = top_recommendations[0]["product_name"]
        top2 = top_recommendations[1]["product_name"] if len(top_recommendations) > 1 else ""

        # Check if Gemini token is configured in system settings
        try:
            from database import get_setting
            gemini_token = get_setting("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
            if gemini_token:
                import requests
                prompt = (
                    f"Bir kafede garson için müşteriye söylenecek tek cümlelik, samimi, güler yüzlü ve profesyonel bir karşılama/öneri repliği yaz.\n"
                    f"Müşteri: {user_name or 'Misafir'}\n"
                    f"Hava Durumu: {temp:.0f}°C, {weather_desc}\n"
                    f"Günün Saati: Saat {current_hour:.0f}\n"
                    f"Öne Çıkan Menü Ürünleri: {top1}, {top2}\n"
                    f"Sadece söylenecek tek cümleyi tırnaksız olarak dön, başka açıklama yazma."
                )
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_token}"
                g_res = requests.post(
                    gemini_url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=3.0
                )
                if g_res.status_code == 200:
                    cand = g_res.json().get("candidates", [])
                    if cand and "content" in cand[0] and "parts" in cand[0]["content"]:
                        gemini_pitch = cand[0]["content"]["parts"][0].get("text", "").strip()
                        if gemini_pitch:
                            return gemini_pitch
        except Exception as ge:
            print(f"[WARN] Gemini waiter pitch generation fallback to template: {ge}")

        # Time phrase
        if 6 <= current_hour < 11.5:
            time_phrase = "sabah kahvaltısı için"
        elif 11.5 <= current_hour < 15:
            time_phrase = "öğle saatlerinde"
        elif 15 <= current_hour < 19:
            time_phrase = "ikindi keyfi için"
        else:
            time_phrase = "akşam saatlerinde"

        # Temp phrase
        if temp >= 24.0:
            temp_phrase = f"hava {temp:.0f}°C ve oldukça sıcak"
        elif temp <= 16.0:
            temp_phrase = f"hava {temp:.0f}°C ve serin"
        else:
            temp_phrase = f"hava {temp:.0f}°C"

        is_registered = user_name and not user_name.lower().startswith("guest") and not user_name.lower().startswith("misafir")

        if is_registered:
            has_fav = top_recommendations[0].get("user_order_count", 0) >= 2
            if has_fav:
                if top2:
                    return f"{user_name} hoş geldiniz! Bugün {temp_phrase}; favoriniz olan {top1} hazırlayalım mı? Yanında taze {top2} çok yakışır."
                return f"{user_name} hoş geldiniz! Bugün {temp_phrase}; her zamanki gibi {top1} hazırlamamızı ister misiniz?"
            else:
                if top2:
                    return f"{user_name} hoş geldiniz! Bugün {time_phrase} şefimizin önerisi {top1}; yanında {top2} denemek ister misiniz?"
                return f"{user_name} hoş geldiniz! Bugün {time_phrase} özel önerimiz {top1}, ikram edelim mi?"
        else:
            if top2:
                return f"Hoş geldiniz! Bugün {temp_phrase}; {time_phrase} en çok tercih edilen lezzetimiz {top1} ve yanında {top2} ikram edelim mi?"
            return f"Hoş geldiniz! Bugün {temp_phrase}; şefimizin özel önerisi {top1} denemek ister misiniz?"

    def place_order(self, user_name, order_items):
        """
        Place an order for a customer/guest.
        Flexible item formats supported:
        - List of dicts: [{'product_id': 1, 'quantity': 2}] or [{'product_name': 'Latte', 'quantity': 1}]
        - List of strings: ['Espresso', 'Espresso', 'Kruvasan']
        """
        if not user_name:
            return {"success": False, "error": "Kullanıcı adı gereklidir."}
        if not order_items:
            return {"success": False, "error": "Sipariş listesi boş olamaz."}

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Build catalog lookup maps: id -> product, name_lower -> product
            cursor.execute("SELECT id, product_name, price, category FROM products")
            all_prods = [dict(row) for row in cursor.fetchall()]
            prod_by_id = {p["id"]: p for p in all_prods}
            prod_by_name = {p["product_name"].strip().lower(): p for p in all_prods}

            items_to_insert = []
            total_amount = 0.0

            # Normalize order_items input
            normalized_items = []
            if isinstance(order_items, list):
                for item in order_items:
                    if isinstance(item, str):
                        # E.g. "Espresso"
                        normalized_items.append({"name": item.strip(), "quantity": 1})
                    elif isinstance(item, dict):
                        pid = item.get("product_id") or item.get("id")
                        pname = item.get("product_name") or item.get("name") or item.get("food")
                        qty = int(item.get("quantity") or item.get("qty") or 1)
                        normalized_items.append({"product_id": pid, "name": pname, "quantity": max(1, qty)})
            elif isinstance(order_items, dict):
                # Single item dict
                normalized_items.append(order_items)

            # Consolidate duplicate items in the same order
            consolidated = {}
            for item in normalized_items:
                pid = item.get("product_id")
                pname = item.get("name")
                qty = item.get("quantity", 1)

                matched_prod = None
                if pid and int(pid) in prod_by_id:
                    matched_prod = prod_by_id[int(pid)]
                elif pname and pname.strip().lower() in prod_by_name:
                    matched_prod = prod_by_name[pname.strip().lower()]

                if matched_prod:
                    mp_id = matched_prod["id"]
                    if mp_id in consolidated:
                        consolidated[mp_id]["quantity"] += qty
                    else:
                        consolidated[mp_id] = {
                            "product": matched_prod,
                            "quantity": qty
                        }

            if not consolidated:
                conn.close()
                return {"success": False, "error": "Geçerli bir menü ürünü seçilmedi."}

            for item_data in consolidated.values():
                prod = item_data["product"]
                qty = item_data["quantity"]
                pid = prod["id"]
                p_name = prod["product_name"]
                price = float(prod["price"])
                subtotal = price * qty
                total_amount += subtotal
                items_to_insert.append((pid, p_name, qty, price))

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            foods_summary = ", ".join([f"{qty}x {p_name}" for _, p_name, qty, _ in items_to_insert])

            # 1. Create order record
            cursor.execute(
                "INSERT INTO orders (user_name, name, total_amount, foods, order_date) VALUES (?, ?, ?, ?, ?)",
                (user_name, user_name, total_amount, foods_summary, now_str)
            )
            order_id = cursor.lastrowid

            # 2. Create itemized order records
            for pid, p_name, qty, price in items_to_insert:
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                    (order_id, pid, p_name, qty, price)
                )

            # 3. Update total_spent and last_login_date for user
            cursor.execute(
                "UPDATE users SET total_spent = total_spent + ?, last_login_date = ? WHERE name = ?",
                (total_amount, now_str, user_name)
            )

            conn.commit()
            conn.close()

            try:
                print(f"[ORDER] Successfully placed Order #{order_id} for {user_name}: {foods_summary} ({total_amount:.2f} TL)")
            except Exception:
                print(f"[ORDER] Successfully placed Order #{order_id} for {user_name}: Total {total_amount:.2f} TL")

            return {
                "success": True,
                "order_id": order_id,
                "user_name": user_name,
                "total_amount": total_amount,
                "foods": foods_summary,
                "items": [{"product_id": pid, "product_name": p_name, "quantity": qty, "price": price} for pid, p_name, qty, price in items_to_insert],
                "order_date": now_str,
                "message": f"Siparişiniz başarıyla alındı! Toplam: {total_amount:.2f} TL"
            }
        except Exception as e:
            conn.close()
            try:
                print(f"[ERROR] Failed to place order: {e}")
            except Exception:
                pass
            return {"success": False, "error": str(e)}


recommendation_service = RecommendationService()


