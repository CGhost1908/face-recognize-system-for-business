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
        this.currentOrderItems = [];
        this.soundEnabled = true;
        this.pollInterval = null;
        this.weatherInterval = null;

        this.init();
    }

    init() {
        this.fetchWeather();
        this.fetchPresences();
        
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
            const waiting = data.waiting || [];
            const ordered = data.ordered || [];
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
            const avatar = p.face_image || '/static/images/default_user.png';

            return `
                <div class="presence-card ${pulseClass} ${selectedClass}" onclick="waiterTerminal.selectCustomer(${p.id})">
                    <div class="presence-avatar-wrap">
                        <img src="${avatar}" alt="${this.escapeHtml(p.user_name)}" class="presence-avatar" onerror="this.onerror=null; this.src='/static/images/default_user.png';" />
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
        await this.fetchRecommendations(customer.user_name);
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

        if (avatar) avatar.src = customer.face_image || '/static/images/default_user.png';
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
    }

    async fetchRecommendations(customerName) {
        const pitchText = document.getElementById('waiterPitchText');
        const recsGrid = document.getElementById('recsGrid');
        const pitchContextTag = document.getElementById('pitchContextTag');

        if (pitchText) pitchText.innerHTML = '<span style="opacity:0.6;">AI önerileri ve hitap repliği hesaplanıyor...</span>';
        if (recsGrid) recsGrid.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">Öneriler yükleniyor...</div>';

        try {
            const res = await fetch(`/api/waiter/recommendations/${encodeURIComponent(customerName)}`);
            if (!res.ok) throw new Error('API Hatası');

            const data = await res.json();
            const recs = data.recommendations || [];
            const pitch = data.waiter_pitch || 'Hoş geldiniz! Menümüzden dilediğiniz lezzeti hazırlayabiliriz.';
            const ctx = data.context || {};

            if (pitchText) pitchText.textContent = `"${pitch}"`;
            if (pitchContextTag) {
                const t = Math.round(ctx.temp || 24);
                pitchContextTag.textContent = `🌤️ ${t}°C • ${ctx.weather || 'Açık'}`;
            }

            if (recsGrid) {
                if (recs.length === 0) {
                    recsGrid.innerHTML = '<p class="text-muted">Öneri bulunamadı.</p>';
                    return;
                }

                recsGrid.innerHTML = recs.map(r => {
                    const price = (typeof r.price === 'number') ? r.price.toFixed(2) : parseFloat(r.price || 0).toFixed(2);
                    const img = r.image_url || '/static/images/espresso.jpg';
                    const safeName = this.escapeHtml(r.product_name);
                    const reason = r.reason_badge || '✨ Şefin Tavsiyesi';

                    return `
                        <div class="rec-card">
                            <div class="rec-top">
                                <img src="${img}" alt="${safeName}" class="rec-thumb" onerror="this.onerror=null; this.src='/static/images/espresso.jpg';" />
                                <div class="rec-info">
                                    <div class="rec-name" title="${safeName}">${safeName}</div>
                                    <div class="rec-badge">${reason}</div>
                                    <div class="rec-price">${price} ₺</div>
                                </div>
                            </div>
                            <button class="btn-add-rec" onclick="waiterTerminal.addToOrder(${r.id}, '${safeName.replace(/'/g, "\\'")}', ${r.price})">
                                <span class="material-symbols-outlined" style="font-size: 16px;">add_circle</span>
                                <span>Siparişe Ekle</span>
                            </button>
                        </div>
                    `;
                }).join('');
            }
        } catch (err) {
            if (pitchText) pitchText.textContent = `"Hoş geldiniz! Bugün size ne ikram edelim?"`;
            if (recsGrid) recsGrid.innerHTML = '<p style="color:var(--danger); font-size:13px;">Öneriler alınırken bağlantı hatası oluştu.</p>';
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
    }

    changeItemQuantity(productId, delta) {
        const item = this.currentOrderItems.find(i => i.product_id === productId);
        if (!item) return;

        item.quantity += delta;
        if (item.quantity <= 0) {
            this.currentOrderItems = this.currentOrderItems.filter(i => i.product_id !== productId);
        }
        this.renderOrderTray();
    }

    renderOrderTray() {
        const list = document.getElementById('trayItemsList');
        const totalText = document.getElementById('trayTotalText');
        if (!list || !totalText) return;

        if (this.currentOrderItems.length === 0) {
            list.innerHTML = '<p style="color: var(--text-muted); font-size: 12px; text-align: center; margin: 10px 0;">Henüz ürün eklenmedi. Yukarıdaki akıllı önerilerden tıklayarak ekleyin.</p>';
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
                        <button class="tray-qty-btn" onclick="waiterTerminal.changeItemQuantity(${item.product_id}, -1)">-</button>
                        <span style="font-weight:700; min-width:18px; text-align:center;">${item.quantity}</span>
                        <button class="tray-qty-btn" onclick="waiterTerminal.changeItemQuantity(${item.product_id}, 1)">+</button>
                        <span style="font-weight:700; color:var(--success); min-width:60px; text-align:right;">${itemTotal.toFixed(2)} ₺</span>
                    </div>
                </div>
            `;
        }).join('');

        totalText.textContent = `${total.toFixed(2)} ₺`;
    }

    async submitOrder() {
        if (!this.selectedCustomer) {
            alert('Lütfen önce bir müşteri seçin.');
            return;
        }
        if (this.currentOrderItems.length === 0) {
            alert('Lütfen en az bir ürün seçin.');
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
                alert(`Sipariş başarıyla alındı! Masa durumu 'Masada / Sipariş Alındı' olarak güncellendi.`);
                this.currentOrderItems = [];
                this.renderOrderTray();
                await this.fetchPresences();
            } else {
                alert('Hata: ' + (data.error || 'Sipariş oluşturulamadı.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span> <span>Siparişi Onayla & Masaya İşle</span>';
            }
        }
    }

    async checkoutCustomer() {
        if (!this.selectedCustomer) return;
        const name = this.selectedCustomer.user_name;

        if (!confirm(`'${name}' isimli müşterinin masadan ayrıldığını onaylıyor musunuz? (Oturum kapatılacaktır)`)) {
            return;
        }

        try {
            const res = await fetch('/api/waiter/set_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    presence_id: this.selectedPresenceId,
                    status: 'exited'
                })
            });

            const data = await res.json();
            if (res.ok && data.success) {
                this.selectedPresenceId = null;
                this.selectedCustomer = null;
                this.currentOrderItems = [];

                const emptyView = document.getElementById('emptySelectionView');
                const detailView = document.getElementById('customerViewContainer');
                if (emptyView) emptyView.style.display = 'flex';
                if (detailView) detailView.style.display = 'none';

                await this.fetchPresences();
            } else {
                alert('Hata: ' + (data.error || 'Çıkış işlemi yapılamadı.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        }
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
                alert('Müşteri notu kaydedildi.');
            } else {
                alert('Not kaydedilemedi: ' + (data.error || 'Hata'));
            }
        } catch (e) {
            alert('Hata: ' + e);
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
