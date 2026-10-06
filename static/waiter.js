/**
 * UniFace Waiter Service Terminal (Waiter POS AI) Logic
 * Real-time presence polling, contextual recommendations, waiter speech assistant, and table management.
 */

class WaiterTerminal {
    constructor() {
        this.selectedPresenceId = null;
        this.selectedCustomer = null;
        this.activeFilterTab = 'all';
        this.presences = { waiting: [], ordered: [] };
        this.knownPresenceIds = new Set();
        this.pendingExitedPresenceIds = new Set();
        this.allProducts = [];
        this.catalogCategory = 'all';
        this.catalogSearchQuery = '';
        this.currentRecommendations = [];
        this.currentOrderItems = [];
        this.soundEnabled = true;
        this.pollInterval = null;
        this.weatherInterval = null;

        this.init();
    }

    init() {
        this.fetchWeather();
        this.fetchPresences();
        this.fetchProducts();
        
        // Polling every 2.5 seconds
        this.pollInterval = setInterval(() => this.fetchPresences(), 2500);
        // Weather refresh every 2 minutes
        this.weatherInterval = setInterval(() => this.fetchWeather(), 120000);
    }

    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        const icon = document.getElementById('soundIcon');
        const label = document.getElementById('soundLabel');
        if (this.soundEnabled) {
            if (icon) icon.textContent = 'volume_up';
            if (label) label.textContent = 'Ses Açık';
            this.playChimeSound();
        } else {
            if (icon) icon.textContent = 'volume_off';
            if (label) label.textContent = 'Sessiz';
        }
    }

    playChimeSound() {
        if (!this.soundEnabled) return;
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.15); // A5
            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        } catch (e) {
            // Audio context policy fallback
        }
    }

    setFilterTab(tab) {
        this.activeFilterTab = tab;
        document.querySelectorAll('.tab-btn').forEach(btn => {
            if (btn.dataset.tab === tab) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        this.renderPresenceList();
    }

    fetchWeather() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    this.requestWeatherApi(lat, lon);
                },
                (err) => {
                    this.requestWeatherApi();
                },
                { timeout: 6000, maximumAge: 600000 }
            );
        } else {
            this.requestWeatherApi();
        }
    }

    async requestWeatherApi(lat = null, lon = null) {
        try {
            let url = '/api/weather';
            if (lat !== null && lon !== null) {
                url += `?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
            }
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                const temp = Math.round(data.main?.temp || 22);
                const desc = data.weather?.[0]?.description || 'Açık';
                const city = data.name || 'İstanbul';
                const source = data.source || '';
                const el = document.getElementById('weatherText');
                const widget = document.getElementById('topbarWeather');
                if (el) el.textContent = `${city} ${temp}°C • ${desc}`;
                if (widget && source) widget.title = `Hava Durumu Kaynağı: ${source} (Canlı Konum)`;
            }
        } catch (e) {}
    }

    async fetchPresences() {
        try {
            const res = await fetch('/api/waiter/presence');
            if (!res.ok) return;

            const data = await res.json();
            const rawWaiting = data.waiting || [];
            const rawOrdered = data.ordered || [];
            const waiting = rawWaiting.filter(p => !this.pendingExitedPresenceIds.has(p.id));
            const ordered = rawOrdered.filter(p => !this.pendingExitedPresenceIds.has(p.id));
            this.presences = { waiting, ordered };

            // Check for newly entered customers in waiting_order to trigger audio chime
            let hasNewArrival = false;
            for (const p of waiting) {
                if (!this.knownPresenceIds.has(p.id)) {
                    hasNewArrival = true;
                    this.knownPresenceIds.add(p.id);
                }
            }
            for (const p of ordered) {
                this.knownPresenceIds.add(p.id);
            }

            if (hasNewArrival && this.knownPresenceIds.size > waiting.length) {
                this.playChimeSound();
            }

            // Update Header and Tab Counters
            const waitingEl = document.getElementById('waitingCount');
            const seatedEl = document.getElementById('seatedCount');
            if (waitingEl) waitingEl.textContent = waiting.length;
            if (seatedEl) seatedEl.textContent = ordered.length;

            const tabAll = document.getElementById('tabCountAll');
            const tabWait = document.getElementById('tabCountWaiting');
            const tabOrd = document.getElementById('tabCountOrdered');
            if (tabAll) tabAll.textContent = waiting.length + ordered.length;
            if (tabWait) tabWait.textContent = waiting.length;
            if (tabOrd) tabOrd.textContent = ordered.length;

            this.renderPresenceList();

            // Refresh selected customer state if still present
            if (this.selectedPresenceId) {
                const all = [...waiting, ...ordered];
                const updated = all.find(p => p.id === this.selectedPresenceId);
                if (updated) {
                    this.selectedCustomer = updated;
                    this.updateCustomerHeaderUI(updated);
                }
            }
        } catch (err) {
            console.error('Presence fetch error:', err);
        }
    }

    formatAvatar(img, userName) {
        if (!img) {
            return `/api/profile_image/${encodeURIComponent(userName)}`;
        }
        if (img.startsWith('data:image') || img.startsWith('http://') || img.startsWith('https://') || img.startsWith('/api/') || img.startsWith('/static/')) {
            return img;
        }
        if (img.length > 50) {
            return 'data:image/jpeg;base64,' + img;
        }
        return `/api/profile_image/${encodeURIComponent(userName)}`;
    }

    renderPresenceList() {
        const container = document.getElementById('presenceList');
        if (!container) return;

        let list = [];
        if (this.activeFilterTab === 'all') {
            list = [...this.presences.waiting, ...this.presences.ordered];
        } else if (this.activeFilterTab === 'waiting') {
            list = this.presences.waiting;
        } else if (this.activeFilterTab === 'ordered') {
            list = this.presences.ordered;
        }

        if (list.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 48px 12px;">
                    <span class="material-symbols-outlined" style="font-size: 40px; opacity: 0.4;">hourglass_empty</span>
                    <p style="margin-top: 10px; font-size: 13px;">Şu an bu kategoride müşteri bulunmuyor.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = list.map(p => {
            const isWaiting = p.status === 'waiting_order';
            const isSelected = p.id === this.selectedPresenceId;
            const pulseClass = isWaiting ? 'waiting-pulse' : '';
            const selectedClass = isSelected ? 'selected' : '';
            const statusText = isWaiting ? 'Sipariş Bekliyor' : 'Masada / Sipariş Alındı';
            const statusDotClass = isWaiting ? 'waiting' : 'ordered';
            const badgeTypeClass = p.user_type === 'customer' ? 'customer' : 'guest';
            const typeLabel = p.user_type === 'customer' ? 'Kayıtlı' : 'Misafir';
            const elapsedText = p.elapsed_minutes === 0 ? 'Yeni girdi' : `${p.elapsed_minutes} dk`;
            const avatar = this.formatAvatar(p.face_image, p.user_name);

            return `
                <div class="presence-card ${pulseClass} ${selectedClass}" onclick="waiterTerminal.selectCustomer(${p.id})">
                    <div class="presence-avatar-wrap">
                        <img src="${avatar}" alt="${this.escapeHtml(p.user_name)}" class="presence-avatar" onerror="this.onerror=null; this.src='/static/images/default_user.svg';" />
                        <span class="presence-status-dot ${statusDotClass}"></span>
                    </div>
                    <div class="presence-meta">
                        <div class="presence-name-row">
                            <span class="presence-name" title="${this.escapeHtml(p.user_name)}">${this.escapeHtml(p.user_name)}</span>
                            <span class="presence-time-tag">${elapsedText}</span>
                        </div>
                        <div class="presence-sub-row">
                            <span class="user-badge ${badgeTypeClass}">${typeLabel}</span>
                            <span class="presence-status-badge ${statusDotClass}">${statusText}</span>
                        </div>
                        ${p.order_summary ? `<div class="presence-order-preview" title="${this.escapeHtml(p.order_summary)}">🍽️ ${this.escapeHtml(p.order_summary)}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    async selectCustomer(presenceId) {
        this.selectedPresenceId = presenceId;
        const all = [...this.presences.waiting, ...this.presences.ordered];
        const customer = all.find(p => p.id === presenceId);
        if (!customer) return;

        this.selectedCustomer = customer;
        this.currentOrderItems = [];
        this.renderOrderTray();
        this.renderPresenceList();

        // Switch view to customer detail
        const emptyView = document.getElementById('emptySelectionView');
        const detailView = document.getElementById('customerViewContainer');
        if (emptyView) emptyView.style.display = 'none';
        if (detailView) detailView.style.display = 'flex';

        this.updateCustomerHeaderUI(customer);
        await Promise.all([
            this.fetchRecommendations(customer.user_name),
            this.fetchProducts(customer.user_name)
        ]);
    }

    updateCustomerHeaderUI(customer) {
        const avatar = document.getElementById('detailAvatar');
        const name = document.getElementById('detailName');
        const typeBadge = document.getElementById('detailTypeBadge');
        const statusBadge = document.getElementById('detailStatusBadge');
        const elapsedText = document.getElementById('detailElapsedText');
        const visits = document.getElementById('detailVisitsCount');
        const spent = document.getElementById('detailTotalSpent');
        const notes = document.getElementById('customerNotesInput');

        if (avatar) avatar.src = this.formatAvatar(customer.face_image, customer.user_name);
        if (name) name.textContent = customer.user_name;
        if (typeBadge) {
            typeBadge.textContent = customer.user_type === 'customer' ? 'Kayıtlı Müşteri' : 'Misafir';
            typeBadge.className = `user-badge ${customer.user_type === 'customer' ? 'customer' : 'guest'}`;
        }
        if (statusBadge) {
            const isWait = customer.status === 'waiting_order';
            statusBadge.textContent = isWait ? '🟢 Sipariş Bekliyor' : '🟡 Masada / Servis Edildi';
            statusBadge.className = `presence-status-badge ${isWait ? 'waiting' : 'ordered'}`;
        }
        if (elapsedText) {
            elapsedText.textContent = customer.elapsed_minutes === 0 ? 'Yeni girdi' : `${customer.elapsed_minutes} dk önce girdi`;
        }
        if (visits) visits.textContent = (customer.order_count || 1);
        if (spent) spent.textContent = `${(customer.total_spent || 0).toFixed(2)} ₺`;
        if (notes && !notes.matches(':focus')) {
            notes.value = customer.notes || '';
        }

        // Dynamic Personalized Recommendations Header
        const recsTitle = document.getElementById('recsSectionTitle');
        const recsSub = document.getElementById('recsSectionSubtitle');
        const recsPill = document.getElementById('recsUserPill');

        if (recsTitle) {
            if (customer.user_type === 'customer') {
                recsTitle.textContent = `${customer.user_name} İçin Akıllı Öneriler`;
            } else {
                recsTitle.textContent = `${customer.user_name} İçin Durumsal Öneriler`;
            }
        }
        if (recsSub) {
            if (customer.user_type === 'customer') {
                recsSub.textContent = `${customer.user_name} adlı müşterinin sipariş geçmişi ve anlık duruma göre seçildi`;
            } else {
                recsSub.textContent = `Günün popüler seçimleri, hava durumu ve saat dilimine göre seçildi`;
            }
        }
        if (recsPill) {
            recsPill.style.display = 'inline-block';
            recsPill.textContent = customer.user_type === 'customer' ? 'Kişisel Profil' : 'Misafir Profili';
        }
    }

    async fetchRecommendations(customerName) {
        const pitchText = document.getElementById('waiterPitchText');
        const recsGrid = document.getElementById('recsGrid');
        const pitchContextTag = document.getElementById('pitchContextTag');

        if (pitchText) pitchText.innerHTML = '<span style="opacity:0.6;">AI önerileri ve hitap repliği hesaplanıyor...</span>';
        if (recsGrid) recsGrid.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:10px 0;">Öneriler yükleniyor...</div>';

        try {
            const res = await fetch(`/api/waiter/recommendations/${encodeURIComponent(customerName)}`);
            if (!res.ok) throw new Error('API Hatası');

            const data = await res.json();
            this.currentRecommendations = data.recommendations || [];
            const pitch = data.waiter_pitch || 'Hoş geldiniz! Menümüzden dilediğiniz lezzeti hazırlayabiliriz.';
            const ctx = data.context || {};

            if (pitchText) pitchText.textContent = `"${pitch}"`;
            if (pitchContextTag) {
                const t = Math.round(ctx.temp || 24);
                pitchContextTag.textContent = `🌤️ ${t}°C • ${ctx.weather || 'Açık'}`;
            }

            this.renderRecommendations();
        } catch (err) {
            this.currentRecommendations = [];
            if (pitchText) pitchText.textContent = `"Hoş geldiniz! Bugün size ne ikram edelim?"`;
            if (recsGrid) recsGrid.innerHTML = '<p style="color:var(--danger); font-size:13px;">Öneriler alınırken bağlantı hatası oluştu.</p>';
        }
    }

    renderRecommendations() {
        const recsGrid = document.getElementById('recsGrid');
        if (!recsGrid) return;

        const recs = this.currentRecommendations || [];
        if (recs.length === 0) {
            recsGrid.innerHTML = '<p class="text-muted" style="padding:10px 0; font-size:13px;">Öneri bulunamadı.</p>';
            return;
        }

        const inTrayMap = new Map();
        for (const item of this.currentOrderItems) {
            inTrayMap.set(item.product_id, item.quantity);
        }

        recsGrid.innerHTML = recs.map(r => {
            const price = (typeof r.price === 'number') ? r.price.toFixed(2) : parseFloat(r.price || 0).toFixed(2);
            const img = r.image_url || '/static/images/espresso.jpg';
            const safeName = this.escapeHtml(r.product_name);
            const reason = r.reason_badge || '✨ Şefin Tavsiyesi';
            const inTrayQty = inTrayMap.get(r.id) || 0;
            const inTrayClass = inTrayQty > 0 ? 'in-tray' : '';
            const inTrayBadge = inTrayQty > 0 
                ? `<span class="in-tray-count-badge" style="position:static; margin-left:auto;"><span class="material-symbols-outlined" style="font-size:12px;">shopping_basket</span> ${inTrayQty}x</span>` 
                : '';

            return `
                <div class="rec-card ${inTrayClass}">
                    <div class="rec-top">
                        <img src="${img}" alt="${safeName}" class="rec-thumb" onerror="this.onerror=null; this.src='/static/images/espresso.jpg';" />
                        <div class="rec-info">
                            <div class="rec-name" title="${safeName}">${safeName}</div>
                            <div style="display:flex; align-items:center; gap:6px;">
                                <div class="rec-badge">${reason}</div>
                                ${inTrayBadge}
                            </div>
                            <div class="rec-price">${price} ₺</div>
                        </div>
                    </div>
                    <button class="btn-add-rec" type="button" onclick="waiterTerminal.addToOrder(${r.id}, '${safeName.replace(/'/g, "\\'")}', ${r.price})">
                        <span class="material-symbols-outlined" style="font-size: 16px;">add_circle</span>
                        <span>Siparişe Ekle</span>
                    </button>
                </div>
            `;
        }).join('');
    }

    async fetchProducts(customerName = null) {
        try {
            let url = '/api/products';
            if (customerName) {
                url += `?customer_name=${encodeURIComponent(customerName)}`;
            }
            const res = await fetch(url);
            if (!res.ok) return;

            const data = await res.json();
            this.allProducts = data.products || [];
            this.renderCatalogCategoryTabs();
            this.renderCatalogGrid();
        } catch (err) {
            console.error('Fetch products error:', err);
        }
    }

    renderCatalogCategoryTabs() {
        const bar = document.getElementById('catalogCategoryBar');
        if (!bar) return;

        const cats = ['all'];
        const seen = new Set();
        for (const p of this.allProducts) {
            const c = (p.category || 'Genel').trim();
            if (c && !seen.has(c)) {
                seen.add(c);
                cats.push(c);
            }
        }

        bar.innerHTML = cats.map(cat => {
            const isActive = (this.catalogCategory === cat);
            const label = (cat === 'all') ? 'Tümü' : this.escapeHtml(cat);
            return `
                <button 
                    type="button" 
                    class="catalog-cat-pill ${isActive ? 'active' : ''}" 
                    onclick="waiterTerminal.setCatalogCategory('${cat.replace(/'/g, "\\'")}')"
                >
                    ${label}
                </button>
            `;
        }).join('');
    }

    setCatalogCategory(cat) {
        this.catalogCategory = cat;
        this.renderCatalogCategoryTabs();
        this.renderCatalogGrid();
    }

    handleCatalogSearch(value) {
        this.catalogSearchQuery = (value || '').trim().toLowerCase();
        const clearBtn = document.getElementById('catalogClearBtn');
        if (clearBtn) {
            clearBtn.style.display = this.catalogSearchQuery ? 'flex' : 'none';
        }
        this.renderCatalogGrid();
    }

    clearCatalogSearch() {
        const input = document.getElementById('catalogSearchInput');
        if (input) input.value = '';
        this.catalogSearchQuery = '';
        const clearBtn = document.getElementById('catalogClearBtn');
        if (clearBtn) clearBtn.style.display = 'none';
        this.renderCatalogGrid();
    }

    renderCatalogGrid() {
        const grid = document.getElementById('catalogProductsGrid');
        const countPill = document.getElementById('catalogCountPill');
        if (!grid) return;

        let filtered = this.allProducts || [];

        if (this.catalogCategory !== 'all') {
            filtered = filtered.filter(p => (p.category || 'Genel').trim().toLowerCase() === this.catalogCategory.toLowerCase());
        }

        if (this.catalogSearchQuery) {
            const q = this.catalogSearchQuery;
            filtered = filtered.filter(p => {
                const name = (p.product_name || p.name || '').toLowerCase();
                const cat = (p.category || '').toLowerCase();
                const desc = (p.description || '').toLowerCase();
                return name.includes(q) || cat.includes(q) || desc.includes(q);
            });
        }

        if (countPill) {
            if (this.catalogSearchQuery || this.catalogCategory !== 'all') {
                countPill.textContent = `${filtered.length} / ${this.allProducts.length} ürün`;
            } else {
                countPill.textContent = `${filtered.length} ürün`;
            }
        }

        if (filtered.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 36px 12px;">
                    <span class="material-symbols-outlined" style="font-size: 32px; opacity: 0.4;">search_off</span>
                    <p style="margin-top: 8px; font-size: 13px;">Aramanıza veya seçilen kategoriye uygun ürün bulunamadı.</p>
                </div>
            `;
            return;
        }

        // Map of product_id -> quantity in current order tray
        const inTrayMap = new Map();
        for (const item of this.currentOrderItems) {
            inTrayMap.set(item.product_id, item.quantity);
        }

        grid.innerHTML = filtered.map(p => {
            const id = p.id;
            const name = p.product_name || p.name;
            const safeName = this.escapeHtml(name);
            const price = (typeof p.price === 'number') ? p.price.toFixed(2) : parseFloat(p.price || 0).toFixed(2);
            const cat = this.escapeHtml(p.category || 'Genel');
            const img = p.image_url || '/static/images/espresso.jpg';
            const inTrayQty = inTrayMap.get(id) || 0;
            const inTrayClass = inTrayQty > 0 ? 'in-tray' : '';
            const badgeHtml = inTrayQty > 0 
                ? `<span class="in-tray-count-badge"><span class="material-symbols-outlined" style="font-size:12px;">shopping_basket</span> ${inTrayQty}x</span>` 
                : (p.is_favorite ? `<span class="in-tray-count-badge" style="background:#f59e0b;">⭐ Favori</span>` : '');

            return `
                <div class="catalog-card ${inTrayClass}" onclick="waiterTerminal.addToOrder(${id}, '${safeName.replace(/'/g, "\\'")}', ${p.price})">
                    ${badgeHtml}
                    <div class="catalog-card-top">
                        <img src="${img}" alt="${safeName}" class="catalog-card-thumb" onerror="this.onerror=null; this.src='/static/images/espresso.jpg';" />
                        <div class="catalog-card-info">
                            <div class="catalog-card-name" title="${safeName}">${safeName}</div>
                            <div class="catalog-card-cat">${cat}</div>
                        </div>
                    </div>
                    <div class="catalog-card-bottom">
                        <span class="catalog-card-price">${price} ₺</span>
                        <button 
                            class="btn-catalog-add" 
                            type="button" 
                            title="Siparişe Ekle" 
                            onclick="event.stopPropagation(); waiterTerminal.addToOrder(${id}, '${safeName.replace(/'/g, "\\'")}', ${p.price})"
                        >
                            <span class="material-symbols-outlined" style="font-size: 14px;">add</span>
                            <span>Ekle</span>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    speakPitch() {
        const textEl = document.getElementById('waiterPitchText');
        if (!textEl) return;
        const text = textEl.textContent.replace(/^"|"$/g, '').trim();
        if (!text || text.includes('hesaplanıyor') || text.includes('yükleniyor')) return;

        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'tr-TR';
            utterance.rate = 0.95;
            window.speechSynthesis.speak(utterance);
        } else {
            this.showToast('Tarayıcınız sesli okumayı desteklemiyor.', 'warning');
        }
    }

    addToOrder(productId, productName, price) {
        const existing = this.currentOrderItems.find(i => i.product_id === productId);
        if (existing) {
            existing.quantity += 1;
        } else {
            this.currentOrderItems.push({
                product_id: productId,
                product_name: productName,
                price: parseFloat(price) || 0,
                quantity: 1
            });
        }
        this.renderOrderTray();
        this.renderRecommendations();
        this.renderCatalogGrid();
    }

    changeItemQuantity(productId, delta) {
        const item = this.currentOrderItems.find(i => i.product_id === productId);
        if (!item) return;

        item.quantity += delta;
        if (item.quantity <= 0) {
            this.currentOrderItems = this.currentOrderItems.filter(i => i.product_id !== productId);
        }
        this.renderOrderTray();
        this.renderRecommendations();
        this.renderCatalogGrid();
    }

    renderOrderTray() {
        const list = document.getElementById('trayItemsList');
        const totalText = document.getElementById('trayTotalText');
        if (!list || !totalText) return;

        if (this.currentOrderItems.length === 0) {
            list.innerHTML = '<p style="color: var(--text-muted); font-size: 12px; text-align: center; margin: 10px 0;">Henüz ürün eklenmedi. Menüden veya akıllı önerilerden tıklayarak ekleyin.</p>';
            totalText.textContent = '0.00 ₺';
            return;
        }

        let total = 0;
        list.innerHTML = this.currentOrderItems.map(item => {
            const itemTotal = item.quantity * item.price;
            total += itemTotal;
            return `
                <div class="tray-item-row">
                    <div>
                        <strong>${this.escapeHtml(item.product_name)}</strong>
                        <span style="color:var(--text-secondary); font-size:11px; margin-left:6px;">(${item.price.toFixed(2)} ₺)</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <button class="tray-qty-btn" type="button" onclick="waiterTerminal.changeItemQuantity(${item.product_id}, -1)">-</button>
                        <span style="font-weight:700; min-width:18px; text-align:center;">${item.quantity}</span>
                        <button class="tray-qty-btn" type="button" onclick="waiterTerminal.changeItemQuantity(${item.product_id}, 1)">+</button>
                        <span style="font-weight:700; color:var(--success); min-width:60px; text-align:right;">${itemTotal.toFixed(2)} ₺</span>
                    </div>
                </div>
            `;
        }).join('');

        totalText.textContent = `${total.toFixed(2)} ₺`;
    }

    async submitOrder() {
        if (!this.selectedCustomer) {
            this.showToast('Lütfen önce bir müşteri seçin.', 'warning');
            return;
        }
        if (this.currentOrderItems.length === 0) {
            this.showToast('Lütfen en az bir ürün ekleyin.', 'warning');
            return;
        }

        const btn = document.getElementById('btnConfirmOrder');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="material-symbols-outlined" style="animation: spin 1s linear infinite;">sync</span> Kaydediliyor...';
        }

        try {
            const res = await fetch('/api/waiter/create_order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    presence_id: this.selectedPresenceId,
                    user_name: this.selectedCustomer.user_name,
                    items: this.currentOrderItems
                })
            });

            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast('Sipariş kaydedildi ve masaya işlendi.', 'success');
                this.currentOrderItems = [];
                this.renderOrderTray();
                this.renderRecommendations();
                this.renderCatalogGrid();
                await this.fetchPresences();
            } else {
                this.showToast('Hata: ' + (data.error || 'Sipariş oluşturulamadı.'), 'danger');
            }
        } catch (err) {
            this.showToast('Bağlantı hatası: ' + err, 'danger');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span> <span>Siparişi Onayla & Masaya İşle</span>';
            }
        }
    }

    checkoutCustomer() {
        if (!this.selectedCustomer) return;

        const presenceId = this.selectedPresenceId;
        const customerToExit = { ...this.selectedCustomer };
        const prevStatus = customerToExit.status || 'ordered';

        // 1. Mark as pending exited to prevent polling race conditions
        this.pendingExitedPresenceIds.add(presenceId);

        // 2. Optimistic UI update: Remove immediately from active lists
        this.presences.waiting = this.presences.waiting.filter(p => p.id !== presenceId);
        this.presences.ordered = this.presences.ordered.filter(p => p.id !== presenceId);

        // 3. Clear active selection and reset detail panel
        this.selectedPresenceId = null;
        this.selectedCustomer = null;
        this.currentOrderItems = [];

        const emptyView = document.getElementById('emptySelectionView');
        const detailView = document.getElementById('customerViewContainer');
        if (emptyView) emptyView.style.display = 'flex';
        if (detailView) detailView.style.display = 'none';

        // 4. Update counters and re-render list instantly
        const waitingEl = document.getElementById('waitingCount');
        const seatedEl = document.getElementById('seatedCount');
        if (waitingEl) waitingEl.textContent = this.presences.waiting.length;
        if (seatedEl) seatedEl.textContent = this.presences.ordered.length;

        const tabAll = document.getElementById('tabCountAll');
        const tabWait = document.getElementById('tabCountWaiting');
        const tabOrd = document.getElementById('tabCountOrdered');
        if (tabAll) tabAll.textContent = this.presences.waiting.length + this.presences.ordered.length;
        if (tabWait) tabWait.textContent = this.presences.waiting.length;
        if (tabOrd) tabOrd.textContent = this.presences.ordered.length;

        this.renderPresenceList();

        // 5. Send exit request to backend in background
        fetch('/api/waiter/set_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                presence_id: presenceId,
                status: 'exited'
            })
        }).then(async (res) => {
            const data = await res.json();
            if (!res.ok || !data.success) {
                this.showToast('Çıkış işlemi sunucuya iletilemedi: ' + (data.error || 'Hata'), 'danger');
            }
        }).catch((err) => {
            this.showToast('Bağlantı hatası: ' + err, 'danger');
        });

        // 6. Show Undo Toast in the bottom-right corner
        this.showUndoToast({
            id: presenceId,
            name: customerToExit.user_name,
            prevStatus,
            customerObj: customerToExit
        });
    }

    async undoCheckout(presenceId, prevStatus, customerObj) {
        // 1. Remove from pending set
        this.pendingExitedPresenceIds.delete(presenceId);

        // 2. Put customer back into presences list optimistically
        const targetList = (prevStatus === 'waiting_order') ? this.presences.waiting : this.presences.ordered;
        if (!targetList.some(p => p.id === presenceId)) {
            targetList.unshift(customerObj);
        }

        // 3. Update counters
        const waitingEl = document.getElementById('waitingCount');
        const seatedEl = document.getElementById('seatedCount');
        if (waitingEl) waitingEl.textContent = this.presences.waiting.length;
        if (seatedEl) seatedEl.textContent = this.presences.ordered.length;

        const tabAll = document.getElementById('tabCountAll');
        const tabWait = document.getElementById('tabCountWaiting');
        const tabOrd = document.getElementById('tabCountOrdered');
        if (tabAll) tabAll.textContent = this.presences.waiting.length + this.presences.ordered.length;
        if (tabWait) tabWait.textContent = this.presences.waiting.length;
        if (tabOrd) tabOrd.textContent = this.presences.ordered.length;

        // 4. Reselect the customer (restores selection, updates panel, re-renders list)
        await this.selectCustomer(presenceId);

        // 5. Restore status in backend
        try {
            const res = await fetch('/api/waiter/set_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    presence_id: presenceId,
                    status: prevStatus
                })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast(`Masa geri alındı: ${customerObj.user_name}`, 'success', 3000);
            } else {
                this.showToast('Geri alma başarısız oldu: ' + (data.error || 'Hata'), 'danger');
            }
        } catch (err) {
            this.showToast('Geri alma bağlantı hatası: ' + err, 'danger');
        }
    }

    showUndoToast({ id, name, prevStatus, customerObj }) {
        const container = document.getElementById('waiterToastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = 'waiter-toast';
        toast.innerHTML = `
            <div class="toast-content">
                <span class="material-symbols-outlined toast-icon warning">logout</span>
                <div class="toast-text">
                    <strong>${this.escapeHtml(name)}</strong> masadan ayrıldı.
                </div>
            </div>
            <div class="toast-actions">
                <button class="btn-toast-undo" type="button">
                    <span class="material-symbols-outlined">undo</span>
                    <span>Geri Al</span>
                </button>
                <button class="btn-toast-close" type="button" title="Kapat">
                    <span class="material-symbols-outlined" style="font-size:18px;">close</span>
                </button>
            </div>
            <div class="toast-progress" style="animation-duration: 6500ms;"></div>
        `;

        let timer = setTimeout(() => {
            toast.remove();
            this.pendingExitedPresenceIds.delete(id);
        }, 6500);

        const undoBtn = toast.querySelector('.btn-toast-undo');
        const closeBtn = toast.querySelector('.btn-toast-close');

        if (undoBtn) {
            undoBtn.addEventListener('click', () => {
                clearTimeout(timer);
                toast.remove();
                this.undoCheckout(id, prevStatus, customerObj);
            });
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                clearTimeout(timer);
                toast.remove();
                this.pendingExitedPresenceIds.delete(id);
            });
        }

        container.appendChild(toast);
    }

    showToast(message, type = 'info', duration = 3500) {
        const container = document.getElementById('waiterToastContainer');
        if (!container) return;

        const iconMap = {
            info: 'info',
            success: 'check_circle',
            warning: 'warning',
            danger: 'error'
        };
        const iconName = iconMap[type] || 'info';

        const toast = document.createElement('div');
        toast.className = 'waiter-toast';
        toast.innerHTML = `
            <div class="toast-content">
                <span class="material-symbols-outlined toast-icon ${type}">${iconName}</span>
                <div class="toast-text">${this.escapeHtml(message)}</div>
            </div>
            <div class="toast-actions">
                <button class="btn-toast-close" type="button" title="Kapat">
                    <span class="material-symbols-outlined" style="font-size:18px;">close</span>
                </button>
            </div>
            <div class="toast-progress" style="animation-duration: ${duration}ms; background: ${type === 'danger' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#10b981'};"></div>
        `;

        let timer = setTimeout(() => {
            toast.remove();
        }, duration);

        const closeBtn = toast.querySelector('.btn-toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                clearTimeout(timer);
                toast.remove();
            });
        }

        container.appendChild(toast);
    }

    async saveCurrentNote() {
        if (!this.selectedPresenceId) return;
        const input = document.getElementById('customerNotesInput');
        const notes = input ? input.value.trim() : '';

        try {
            const res = await fetch('/api/waiter/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    presence_id: this.selectedPresenceId,
                    notes: notes
                })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                this.showToast('Müşteri notu kaydedildi.', 'success');
            } else {
                this.showToast('Not kaydedilemedi: ' + (data.error || 'Hata'), 'danger');
            }
        } catch (e) {
            this.showToast('Hata: ' + e, 'danger');
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global Terminal Instance
let waiterTerminal;
document.addEventListener('DOMContentLoaded', () => {
    waiterTerminal = new WaiterTerminal();
    window.waiterTerminal = waiterTerminal;
});
