/**
 * UniFace Admin Dashboard Pro Logic
 * Comprehensive Real-time Analytics & CRM Manager
 */

class Dashboard {
    constructor() {
        this.currentPage = 'home';
        this.allCustomersData = [];
        this.adminProductsData = [];
        this.activeProductCategory = 'all';
        this.recognitionInterval = null;
        this.isRecognitionActive = true;
        this.init();
    }

    init() {
        this.setupNavigation();
        this.loadUserProfile();
        this.loadStats();
        this.loadRecentEntries();
        this.restoreSavedCamera();
        this.fetchRecognitionStatus();
        this.startLiveRecognitionPolling();

        const hash = window.location.hash.replace('#', '');
        if (hash && ['home', 'camera', 'customers', 'products', 'logs', 'settings'].includes(hash)) {
            this.switchPage(hash, false);
        }

        window.addEventListener('hashchange', () => {
            const h = window.location.hash.replace('#', '');
            if (h && ['home', 'camera', 'customers', 'products', 'logs', 'settings'].includes(h) && h !== this.currentPage) {
                this.switchPage(h, false);
            }
        });

        // Guard against late browser/password-manager autofill into search input
        setTimeout(() => {
            const searchInput = document.getElementById('customerSearchInput');
            if (searchInput && document.activeElement !== searchInput && searchInput.value) {
                searchInput.value = '';
                const clearBtn = document.getElementById('btnClearCustomerSearch');
                if (clearBtn) clearBtn.style.display = 'none';
                if (this.currentPage === 'customers') {
                    this.filterCustomers();
                }
            }
        }, 350);
    }

    setupNavigation() {
        // Tab Navigation Links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.dataset.page;
                this.switchPage(page);
            });
        });

        // Logout Button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }

        // Camera Controls
        const btnChangeCam = document.getElementById('btnChangeCam');
        if (btnChangeCam) {
            btnChangeCam.addEventListener('click', () => this.changeCamera());
        }

        // CRM Search Input
        const searchInput = document.getElementById('customerSearchInput');
        if (searchInput) {
            if (document.activeElement !== searchInput) {
                searchInput.value = '';
            }
            searchInput.addEventListener('input', () => {
                const clearBtn = document.getElementById('btnClearCustomerSearch');
                if (clearBtn) clearBtn.style.display = searchInput.value ? 'inline-flex' : 'none';
                this.filterCustomers();
            });
        }

        // CRM Tab Filters
        document.querySelectorAll('.btn-tab').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.btn-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.filterCustomers();
            });
        });
    }

    switchPage(page, updateHash = true) {
        document.querySelectorAll('.page-section').forEach(sec => sec.classList.remove('active'));
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));

        const targetSec = document.getElementById(`${page}-page`);
        const targetLink = document.querySelector(`.nav-link[data-page="${page}"]`);

        if (targetSec) targetSec.classList.add('active');
        if (targetLink) targetLink.classList.add('active');

        // Dynamically update Topbar Title & Subtitle
        const pageMeta = {
            home: { title: 'Genel Bakış', subtitle: 'Müşteri akışı ve canlı satış takibi' },
            camera: { title: 'Canlı Kamera', subtitle: 'Kamera akışı, tam ekran ve kaynak ayarları' },
            customers: { title: 'Müşteriler (CRM)', subtitle: 'Kayıtlı müşteriler ve misafir yönetimi' },
            products: { title: 'Ürün & Menü', subtitle: 'Kafe menüsü ve fiyat listesi' },
            logs: { title: 'Giriş & Sipariş Logları', subtitle: 'Geçmiş tanıma ve hareket kayıtları' },
            settings: { title: 'Sistem Ayarları', subtitle: 'Yönetici hesabı ve sistem yapılandırması' }
        };

        const currentMeta = pageMeta[page] || pageMeta.home;
        const pageTitleElem = document.getElementById('pageTitle');
        const pageSubtitleElem = document.getElementById('pageSubtitle');
        if (pageTitleElem) pageTitleElem.textContent = currentMeta.title;
        if (pageSubtitleElem) pageSubtitleElem.textContent = currentMeta.subtitle;

        this.currentPage = page;
        if (updateHash) {
            window.location.hash = page;
        }

        // Load page-specific data
        if (page === 'home') {
            this.loadStats();
            this.loadRecentEntries();
        } else if (page === 'camera') {
            this.loadCameraPresets();
            this.initWebRTCStream();
        } else if (page === 'customers') {
            const searchInput = document.getElementById('customerSearchInput');
            if (searchInput && document.activeElement !== searchInput) {
                searchInput.value = '';
                const clearBtn = document.getElementById('btnClearCustomerSearch');
                if (clearBtn) clearBtn.style.display = 'none';
            }
            this.loadAllCustomers();
        } else if (page === 'products') {
            this.loadAdminProducts();
        } else if (page === 'logs') {
            this.loadFullLogs();
        } else if (page === 'settings') {
            this.loadTokenSettings();
        }
    }

    restoreSavedCamera() {
        const savedCam = localStorage.getItem('selectedCameraSource');
        if (savedCam) {
            const input = document.getElementById('camIndexInput');
            if (input) input.value = savedCam;
        }
    }

    async setCameraSource(source, saveToStorage = true) {
        try {
            const res = await fetch('/api/cam_changed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_source: source })
            });

            if (res.ok) {
                const data = await res.json();
                const activeSrc = data.camera_source || source;
                if (saveToStorage) {
                    localStorage.setItem('selectedCameraSource', activeSrc);
                }
                const input = document.getElementById('camIndexInput');
                if (input) input.value = activeSrc;
                this.loadCameraPresets();
            }
        } catch (err) {
            console.error('Error setting camera source:', err);
        }
    }

    async changeCamera() {
        const camSource = document.getElementById('camIndexInput')?.value || '0';
        await this.setCameraSource(camSource, true);
        alert(`Kamera kaynağı '${camSource}' olarak kaydedildi ve aktif edildi.`);
    }

    async loadCameraPresets() {
        let activeSource = localStorage.getItem('selectedCameraSource');
        let dbPresets = [];

        try {
            const res = await fetch('/api/camera_settings');
            if (res.ok) {
                const data = await res.json();
                dbPresets = data.cameras || [];
                if (!activeSource && data.current_camera_source) {
                    activeSource = data.current_camera_source;
                    localStorage.setItem('selectedCameraSource', activeSource);
                    const input = document.getElementById('camIndexInput');
                    if (input) input.value = activeSource;
                }
            }
        } catch (err) {}

        if (!activeSource) activeSource = '0';

        let localPresets = JSON.parse(localStorage.getItem('cameraPresets') || '[]');

        // Merge DB and LocalStorage presets
        const allPresetsMap = new Map();
        localPresets.forEach(p => allPresetsMap.set(String(p.cam_value), p));
        dbPresets.forEach(p => allPresetsMap.set(String(p.cam_value), { cam_name: p.cam_name, cam_value: p.cam_value, id: p.id }));

        // Ensure default presets (Webcam 0, Webcam 1) exist if empty
        if (allPresetsMap.size === 0) {
            allPresetsMap.set('0', { cam_name: 'Varsayılan Webcam (0)', cam_value: '0' });
            allPresetsMap.set('1', { cam_name: 'İkinci Kamera (1)', cam_value: '1' });
        }

        const presets = Array.from(allPresetsMap.values());
        localStorage.setItem('cameraPresets', JSON.stringify(presets));

        const container = document.getElementById('cameraPresetsList');
        if (!container) return;

        container.innerHTML = presets.map((p, idx) => {
            const isActive = String(p.cam_value) === String(activeSource);
            return `
                <div class="dash-card" style="margin-bottom:0; padding:14px; border:1px solid ${isActive ? 'var(--border-highlight)' : 'var(--border-color)'}; background:${isActive ? 'var(--bg-card-hover)' : 'var(--bg-surface)'};">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <h4 style="font-size:14px; font-weight:600;">${this.escapeHtml(p.cam_name)}</h4>
                        ${isActive ? '<span class="pulse-badge green">AKTİF</span>' : ''}
                    </div>
                    <p style="font-size:11px; color:var(--text-secondary); word-break:break-all; margin-bottom:12px;">
                        Kaynağı: <code>${this.escapeHtml(String(p.cam_value))}</code>
                    </p>
                    <div style="display:flex; gap:6px;">
                        <button class="btn ${isActive ? 'btn-secondary' : 'btn-primary'}" onclick="dashboard.activatePreset('${this.escapeHtml(String(p.cam_value))}', '${p.id || ''}')" ${isActive ? 'disabled' : ''}>
                            ${isActive ? 'Aktif' : 'Aktif Et'}
                        </button>
                        <button class="btn btn-danger" onclick="dashboard.deletePreset('${p.id || ''}', ${idx})" title="Preset Sil">
                            <span class="material-symbols-outlined" style="font-size:16px;">delete</span>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async addCameraPreset() {
        const name = document.getElementById('presetNameInput')?.value.trim();
        const value = document.getElementById('presetSourceInput')?.value.trim();

        if (!name || !value) {
            alert('Lütfen hem kamera adını hem kaynağını girin.');
            return;
        }

        // Save to DB
        try {
            await fetch('/api/camera_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cam_name: name, cam_value: value })
            });
        } catch (err) {}

        // Save to LocalStorage
        let localPresets = JSON.parse(localStorage.getItem('cameraPresets') || '[]');
        localPresets.push({ cam_name: name, cam_value: value });
        localStorage.setItem('cameraPresets', JSON.stringify(localPresets));

        document.getElementById('presetNameInput').value = '';
        document.getElementById('presetSourceInput').value = '';

        alert(`'${name}' preseti kaydedildi!`);
        this.loadCameraPresets();
    }

    async activatePreset(source, presetId = '') {
        if (presetId) {
            try {
                const res = await fetch(`/api/camera_settings/${presetId}/activate`, { method: 'POST' });
                if (res.ok) {
                    localStorage.setItem('selectedCameraSource', source);
                    const input = document.getElementById('camIndexInput');
                    if (input) input.value = source;
                    this.loadCameraPresets();
                    alert(`Kamera kaynağı '${source}' olarak aktif edildi.`);
                    return;
                }
            } catch (err) {}
        }
        await this.setCameraSource(source, true);
        alert(`Kamera kaynağı '${source}' olarak aktif edildi.`);
    }

    async deletePreset(presetId, index) {
        if (!confirm('Bu kamera presetini silmek istediğinize emin misiniz?')) return;

        if (presetId) {
            try {
                await fetch(`/api/camera_settings/${presetId}`, { method: 'DELETE' });
            } catch (err) {}
        }

        let localPresets = JSON.parse(localStorage.getItem('cameraPresets') || '[]');
        localPresets.splice(index, 1);
        localStorage.setItem('cameraPresets', JSON.stringify(localPresets));

        this.loadCameraPresets();
    }


    async loadUserProfile() {
        try {
            const res = await fetch('/api/user/profile');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('username').textContent = data.username || 'Admin';
                if (document.getElementById('settingsUsername')) document.getElementById('settingsUsername').value = data.username || '';
                if (document.getElementById('settingsEmail')) document.getElementById('settingsEmail').value = data.email || '';
            }
        } catch (err) {
            console.error('Profile load error:', err);
        }
    }

    async loadStats() {
        try {
            const res = await fetch('/api/stats');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('statCustomerCount').textContent = data.customer_count || 0;
                document.getElementById('statGuestCount').textContent = data.guest_count || 0;
                document.getElementById('statOrderCount').textContent = data.order_count || 0;
                document.getElementById('statTotalRevenue').textContent = `${(data.total_revenue || 0).toFixed(2)} ₺`;
            }
        } catch (err) {
            console.error('Stats load error:', err);
        }
    }

    async loadRecentEntries() {
        try {
            const res = await fetch('/api/entry_logs');
            if (res.ok) {
                const logs = await res.json();
                const tbody = document.getElementById('recentEntriesTable');
                if (!tbody) return;

                if (!logs || logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Giriş kaydı bulunamadı.</td></tr>';
                    return;
                }

                tbody.innerHTML = logs.slice(0, 6).map(log => `
                    <tr>
                        <td><strong>${this.escapeHtml(log.user_name)}</strong></td>
                        <td><span class="badge-user ${log.user_type === 'customer' ? 'customer' : 'guest'}">${log.user_type === 'customer' ? 'Müşteri' : 'Misafir'}</span></td>
                        <td>${log.entry_time}</td>
                        <td>%${Math.round((log.confidence || 0.95) * 100)}</td>
                    </tr>
                `).join('');
            }
        } catch (err) {
            console.error('Recent entries load error:', err);
        }
    }

    startLiveRecognitionPolling() {
        if (this.recognitionInterval) clearInterval(this.recognitionInterval);
        
        this.recognitionInterval = setInterval(async () => {
            if (this.currentPage !== 'home') return;

            if (!this.isRecognitionActive) {
                const nameElem = document.getElementById('dashRecName');
                const typeElem = document.getElementById('dashRecType');
                if (nameElem && nameElem.textContent !== 'Kamera Kapalı') {
                    nameElem.textContent = 'Kamera Kapalı';
                    if (typeElem) typeElem.textContent = 'Akış Durduruldu';
                }
                return;
            }

            try {
                const res = await fetch('/api/current_recognized_person');
                if (res.ok) {
                    const data = await res.json();
                    const nameElem = document.getElementById('dashRecName');
                    const typeElem = document.getElementById('dashRecType');
                    const imgElem = document.getElementById('dashRecImage');
                    const timeElem = document.getElementById('dashRecTime');

                    if (data.recognized) {
                        nameElem.textContent = data.name;
                        typeElem.textContent = data.user_type === 'customer' ? 'Kayıtlı Müşteri' : 'Misafir';
                        imgElem.src = "data:image/jpeg;base64," + data.image;
                        timeElem.textContent = new Date().toLocaleTimeString();
                    } else {
                        nameElem.textContent = 'Bekleniyor...';
                        typeElem.textContent = 'Kamera Açık';
                        imgElem.src = "https://cdn.pixabay.com/photo/2023/02/18/11/00/icon-7797704_640.png";
                        timeElem.textContent = '--:--:--';
                    }
                }
            } catch (err) {
                console.error('Live polling error:', err);
            }
        }, 800);
    }

    async fetchRecognitionStatus() {
        try {
            const res = await fetch('/api/recognition_status');
            if (res.ok) {
                const data = await res.json();
                this.isRecognitionActive = !!data.is_active;
                if (data.camera_source !== undefined) {
                    const input = document.getElementById('camIndexInput');
                    if (input && !input.value) input.value = data.camera_source;
                    if (!localStorage.getItem('selectedCameraSource')) {
                        localStorage.setItem('selectedCameraSource', data.camera_source);
                    }
                }
                this.updateRecognitionUI();
            }
        } catch (err) {
            console.error('Recognition status fetch error:', err);
        }
    }

    async toggleRecognition() {
        try {
            const nextState = !this.isRecognitionActive;
            const currentCam = document.getElementById('camIndexInput')?.value?.trim() || localStorage.getItem('selectedCameraSource') || null;
            const res = await fetch('/api/toggle_recognition', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    enabled: nextState,
                    camera_source: currentCam
                })
            });

            if (res.ok) {
                const data = await res.json();
                this.isRecognitionActive = !!data.is_active;
                if (data.camera_source !== undefined) {
                    const input = document.getElementById('camIndexInput');
                    if (input) input.value = data.camera_source;
                    localStorage.setItem('selectedCameraSource', data.camera_source);
                }
                this.updateRecognitionUI();
                this.initWebRTCStream();

                if (!this.isRecognitionActive) {
                    const nameElem = document.getElementById('dashRecName');
                    const typeElem = document.getElementById('dashRecType');
                    if (nameElem) nameElem.textContent = 'Kamera Kapalı';
                    if (typeElem) typeElem.textContent = 'Akış Durduruldu';
                }
            }
        } catch (err) {
            console.error('Toggle recognition error:', err);
        }
    }

    updateRecognitionUI() {
        const isActive = this.isRecognitionActive;

        // 1. Sidebar status
        const sidebarDot = document.getElementById('sidebarAiDot');
        const sidebarText = document.getElementById('sidebarAiText');

        if (sidebarDot) {
            sidebarDot.className = isActive ? 'status-dot green' : 'status-dot red';
        }
        if (sidebarText) {
            sidebarText.textContent = isActive ? 'Sistem: Aktif' : 'Sistem: Durduruldu';
        }

        // 2. Topbar master toggle button
        const topbarBtn = document.getElementById('btnTopbarToggleRec');
        const topbarDot = document.getElementById('topbarRecDot');
        const topbarIcon = document.getElementById('topbarRecIcon');
        const topbarText = document.getElementById('topbarRecText');

        if (topbarBtn) {
            topbarBtn.className = isActive ? 'btn-topbar-rec active' : 'btn-topbar-rec inactive';
            topbarBtn.setAttribute('title', isActive ? 'Kamerayı ve Tanımayı Durdur' : 'Kamerayı ve Tanımayı Başlat');
        }
        if (topbarDot) {
            topbarDot.className = isActive ? 'rec-pulse-dot active' : 'rec-pulse-dot inactive';
        }
        if (topbarIcon) {
            topbarIcon.textContent = isActive ? 'videocam' : 'videocam_off';
        }
        if (topbarText) {
            topbarText.textContent = isActive ? 'Kamera Aktif' : 'Kamera Kapalı';
        }

        // 3. Camera page status badge
        const camBadge = document.getElementById('camRecStatusBadge');
        if (camBadge) {
            camBadge.className = isActive ? 'badge-status-pill active' : 'badge-status-pill inactive';
            camBadge.textContent = isActive ? 'Açık' : 'Kapalı';
        }
    }

    async loadAllCustomers() {
        try {
            const res = await fetch('/api/get_last_customers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ count: 200 })
            });

            if (res.ok) {
                const data = await res.json();
                this.allCustomersData = data.customers || [];
                this.filterCustomers();
            }
        } catch (err) {
            console.error('Customers load error:', err);
        }
    }

    clearCustomerSearch() {
        const searchInput = document.getElementById('customerSearchInput');
        if (searchInput) {
            searchInput.value = '';
            const clearBtn = document.getElementById('btnClearCustomerSearch');
            if (clearBtn) clearBtn.style.display = 'none';
            this.filterCustomers();
        }
    }

    filterCustomers() {
        const query = (document.getElementById('customerSearchInput')?.value || '').toLowerCase().trim();
        const activeTab = document.querySelector('.btn-tab.active')?.dataset.filter || 'all';

        let filtered = this.allCustomersData.filter(c => {
            const matchesQuery = c.name.toLowerCase().includes(query);
            const matchesTab = (activeTab === 'all') || 
                               (activeTab === 'customer' && c.user_type !== 'guest' && !c.name.startsWith('Guest_')) ||
                               (activeTab === 'guest' && (c.user_type === 'guest' || c.name.startsWith('Guest_')));
            return matchesQuery && matchesTab;
        });

        const tbody = document.getElementById('customersTableBody');
        if (!tbody) return;

        // Reset master checkbox
        const selectAll = document.getElementById('selectAllCustomers');
        if (selectAll) selectAll.checked = false;

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Kullanıcı bulunamadı.</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(c => {
            const escapedName = this.escapeHtml(c.name).replace(/'/g, "\\'");
            const safeTarget = c.id ? c.id : escapedName;
            return `
            <tr>
                <td style="text-align:center;">
                    <input type="checkbox" class="customer-checkbox custom-checkbox" value="${c.id || c.name}" />
                </td>
                <td>
                    <img src="${c.image ? 'data:image/jpeg;base64,' + c.image : 'https://cdn.pixabay.com/photo/2023/02/18/11/00/icon-7797704_640.png'}" 
                         style="width:36px; height:36px; border-radius:50%; object-fit:cover;" />
                </td>
                <td><strong>${this.escapeHtml(c.name)}</strong></td>
                <td><span class="badge-user ${c.name.startsWith('Guest_') ? 'guest' : 'customer'}">${c.name.startsWith('Guest_') ? 'Misafir' : 'Müşteri'}</span></td>
                <td>${c.last_login_date || 'Hiç'}</td>
                <td>${(c.total_spent || 0).toFixed(2)} ₺</td>
                <td>
                    <div style="display:flex; gap:6px; align-items:center;">
                        ${c.name.startsWith('Guest_') ? 
                            `<button class="btn btn-primary" onclick="dashboard.openRenameModal('${escapedName}')">İsme Dönüştür</button>` : 
                            `<span class="badge-registered"><span class="material-symbols-outlined" style="font-size:14px; vertical-align:middle;">verified</span> Kayıtlı</span>`
                        }
                        <button class="btn btn-danger" onclick="dashboard.deleteSingleCustomer('${safeTarget}')" title="Kullanıcıyı Sil">
                            <span class="material-symbols-outlined" style="font-size:16px;">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        }).join('');
    }

    toggleSelectAllCustomers(masterCb) {
        const checkboxes = document.querySelectorAll('.customer-checkbox');
        checkboxes.forEach(cb => cb.checked = masterCb.checked);
    }

    async deleteSingleCustomer(target) {
        if (!confirm(`Bu kullanıcıyı silmek istediğinize emin misiniz? (${target})`)) return;
        await this.executeDeleteUsers([target]);
    }

    async deleteSelectedCustomers() {
        const checkedBoxes = document.querySelectorAll('.customer-checkbox:checked');
        if (checkedBoxes.length === 0) {
            alert('Lütfen önce silmek istediğiniz kullanıcıları seçin.');
            return;
        }

        const targets = Array.from(checkedBoxes).map(cb => cb.value);
        if (!confirm(`Seçilen ${targets.length} kullanıcıyı silmek istediğinize emin misiniz?`)) return;

        await this.executeDeleteUsers(targets);
    }

    async executeDeleteUsers(targets) {
        try {
            const res = await fetch('/api/delete_users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets: targets })
            });

            if (res.ok) {
                const data = await res.json();
                alert(data.message || 'Seçilen kullanıcılar silindi.');
                this.loadAllCustomers();
                this.loadStats();
            } else {
                alert('Silme işleminde hata oluştu.');
            }
        } catch (err) {
            alert('Sunucu hatası: ' + err);
        }
    }


    openRenameModal(guestName) {
        document.getElementById('renameOldName').value = guestName;
        document.getElementById('renameNewName').value = '';
        document.getElementById('renameModal').style.display = 'flex';
    }

    closeRenameModal() {
        document.getElementById('renameModal').style.display = 'none';
    }

    async submitRenameGuest() {
        const oldName = document.getElementById('renameOldName').value;
        const newName = document.getElementById('renameNewName').value.trim();

        if (!newName) {
            alert('Lütfen geçerli bir isim girin.');
            return;
        }

        try {
            const res = await fetch(`/api/rename_guest/${encodeURIComponent(oldName)}/${encodeURIComponent(newName)}`, {
                method: 'POST'
            });

            if (res.ok) {
                alert(`${oldName} başarıyla ${newName} olarak dönüştürüldü!`);
                this.closeRenameModal();
                this.loadAllCustomers();
                this.loadStats();
            } else {
                alert('İsim değiştirilirken hata oluştu.');
            }
        } catch (err) {
            alert('Sunucu hatası: ' + err);
        }
    }

    async loadAdminProducts() {
        try {
            const res = await fetch('/api/get_products');
            if (res.ok) {
                const data = await res.json();
                this.adminProductsData = data.products || [];
                this.renderAdminProducts();
            }
        } catch (err) {
            console.error('Products load error:', err);
        }
    }

    renderAdminProducts() {
        const grid = document.getElementById('adminProductsGrid');
        if (!grid) return;

        let filtered = this.adminProductsData || [];
        if (this.activeProductCategory && this.activeProductCategory !== 'all') {
            filtered = filtered.filter(p => (p.category || '').toLowerCase() === this.activeProductCategory.toLowerCase());
        }

        if (filtered.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; color: var(--text-secondary);">
                    <span class="material-symbols-outlined" style="font-size: 42px; opacity: 0.6; display: block; margin-bottom: 8px;">inventory_2</span>
                    <p style="margin: 0; font-size: 14px;">Bu kategoride henüz ürün bulunmuyor.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = filtered.map(p => {
            const name = p.product_name || p.name || 'İsimsiz Ürün';
            const price = (typeof p.price === 'number') ? p.price.toFixed(2) : parseFloat(p.price || 0).toFixed(2);
            const category = p.category || 'Genel';
            const desc = p.description || '';
            const img = p.image_url || 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=200';
            const safeNameForJs = this.escapeHtml(name).replace(/'/g, "\\'");

            return `
                <div class="product-admin-card">
                    <div class="product-card-top">
                        <img src="${img}" alt="${this.escapeHtml(name)}" class="product-thumb" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=200';" />
                        <div class="product-info">
                            <h4 title="${this.escapeHtml(name)}">${this.escapeHtml(name)}</h4>
                            <span class="product-category-tag">${this.escapeHtml(category)}</span>
                            ${desc ? `<p class="product-desc" title="${this.escapeHtml(desc)}">${this.escapeHtml(desc)}</p>` : ''}
                        </div>
                    </div>
                    <div class="product-card-bottom">
                        <span class="product-price">${price} ₺</span>
                        <button class="btn-prod-delete" onclick="dashboard.deleteProduct(${p.id}, '${safeNameForJs}')" title="Ürünü Sil">
                            <span class="material-symbols-outlined" style="font-size: 15px;">delete</span>
                            <span>Sil</span>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    filterProducts(category) {
        this.activeProductCategory = category || 'all';
        document.querySelectorAll('#productCategoryTabs .btn-tab').forEach(b => {
            if (b.getAttribute('data-prod-filter') === this.activeProductCategory) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
        this.renderAdminProducts();
    }

    openAddProductModal() {
        const form = document.getElementById('addProductForm');
        if (form) form.reset();

        const catSelect = document.getElementById('newProdCategorySelect');
        if (catSelect) catSelect.value = 'Kahve';

        const customCat = document.getElementById('newProdCategoryCustom');
        if (customCat) {
            customCat.style.display = 'none';
            customCat.value = '';
        }

        const modal = document.getElementById('addProductModal');
        if (modal) modal.style.display = 'flex';

        setTimeout(() => {
            const nameInput = document.getElementById('newProdName');
            if (nameInput) nameInput.focus();
        }, 50);
    }

    closeAddProductModal() {
        const modal = document.getElementById('addProductModal');
        if (modal) modal.style.display = 'none';
    }

    onCategorySelectChange(selectElem) {
        const customInput = document.getElementById('newProdCategoryCustom');
        if (!customInput) return;
        if (selectElem.value === '__custom__') {
            customInput.style.display = 'block';
            customInput.required = true;
            customInput.focus();
        } else {
            customInput.style.display = 'none';
            customInput.required = false;
            customInput.value = '';
        }
    }

    async submitAddProduct() {
        const nameInput = document.getElementById('newProdName');
        const catSelect = document.getElementById('newProdCategorySelect');
        const customCat = document.getElementById('newProdCategoryCustom');
        const priceInput = document.getElementById('newProdPrice');
        const descInput = document.getElementById('newProdDesc');
        const fileInput = document.getElementById('newProdImageFile');
        const urlInput = document.getElementById('newProdImageUrl');
        const submitBtn = document.getElementById('btnSubmitAddProduct');

        const name = nameInput ? nameInput.value.trim() : '';
        let category = catSelect ? catSelect.value : 'Kahve';
        if (category === '__custom__') {
            category = customCat ? customCat.value.trim() : '';
        }
        const price = priceInput ? parseFloat(priceInput.value) : NaN;
        const description = descInput ? descInput.value.trim() : '';

        if (!name) {
            alert('Lütfen ürün adını girin.');
            if (nameInput) nameInput.focus();
            return;
        }

        if (!category) {
            alert('Lütfen ürün kategorisini belirtin.');
            if (customCat) customCat.focus();
            return;
        }

        if (isNaN(price) || price < 0) {
            alert('Lütfen geçerli bir fiyat girin.');
            if (priceInput) priceInput.focus();
            return;
        }

        const formData = new FormData();
        formData.append('product_name', name);
        formData.append('name', name);
        formData.append('category', category);
        formData.append('price', price);
        formData.append('description', description);

        if (fileInput && fileInput.files && fileInput.files[0]) {
            formData.append('image_file', fileInput.files[0]);
        }
        if (urlInput && urlInput.value.trim()) {
            formData.append('image_url', urlInput.value.trim());
        }

        try {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="material-symbols-outlined" style="animation: spin 1s linear infinite;">sync</span> Ekleniyor...';
            }

            const res = await fetch('/api/products', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (res.ok && (data.success || data.status === 'success')) {
                alert(`'${name}' başarıyla menüye eklendi!`);
                this.closeAddProductModal();
                await this.loadAdminProducts();
            } else {
                alert('Hata: ' + (data.error || data.message || 'Ürün eklenemedi.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<span class="material-symbols-outlined">check</span> Ürünü Kaydet';
            }
        }
    }

    async deleteProduct(productId, productName) {
        if (!confirm(`'${productName}' isimli ürünü menüden silmek istediğinize emin misiniz?`)) {
            return;
        }

        try {
            const res = await fetch(`/api/products/${productId}`, {
                method: 'DELETE'
            });

            const data = await res.json();
            if (res.ok && (data.success || data.status === 'success')) {
                await this.loadAdminProducts();
            } else {
                alert('Hata: ' + (data.error || data.message || 'Ürün silinemedi.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        }
    }

    async loadFullLogs() {
        try {
            const res = await fetch('/api/entry_logs');
            if (res.ok) {
                const logs = await res.json();
                const tbody = document.getElementById('fullLogsTableBody');
                if (!tbody) return;

                if (!logs || logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-muted">Kayıtlı log bulunamadı.</td></tr>';
                    return;
                }

                tbody.innerHTML = logs.map(l => `
                    <tr>
                        <td>#${l.id || 1}</td>
                        <td><strong>${this.escapeHtml(l.user_name)}</strong></td>
                        <td><span class="badge-user ${l.user_type === 'customer' ? 'customer' : 'guest'}">${l.user_type}</span></td>
                        <td>${l.entry_time}</td>
                        <td>%${Math.round((l.confidence || 0.95) * 100)} Algılama Doğruluğu</td>
                    </tr>
                `).join('');
            }
        } catch (err) {
            console.error('Logs load error:', err);
        }
    }

    async initWebRTCStream() {
        const video = document.getElementById('dashWebRTCFeed');
        const img = document.getElementById('dashCameraFeed');
        const badge = document.getElementById('streamTypeBadge');
        if (!video || !img) return;

        if (!this.isRecognitionActive) {
            this.stopWebRTCStream();
            video.style.display = 'none';
            img.style.display = 'block';
            if (badge) {
                badge.textContent = 'Kamera Kapalı';
                badge.style.color = '#ef4444';
                badge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
            }
            return;
        }

        try {
            this.stopWebRTCStream();

            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            this.peerConnection = pc;

            pc.addTransceiver('video', { direction: 'recvonly' });

            pc.ontrack = (event) => {
                video.srcObject = event.streams[0];
                video.style.display = 'block';
                img.style.display = 'none';
                if (badge) {
                    badge.textContent = 'Canlı Akış (WebRTC)';
                    badge.style.color = '#34d399';
                    badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                }
            };

            pc.oniceconnectionstatechange = () => {
                if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                    video.style.display = 'none';
                    img.style.display = 'block';
                    if (badge) {
                        badge.textContent = 'Canlı Akış';
                        badge.style.color = '#10b981';
                        badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                    }
                }
            };

            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            const whepHost = window.location.hostname || '127.0.0.1';
            const whepUrl = `http://${whepHost}:8889/live/whep`;

            const res = await fetch(whepUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: offer.sdp
            });

            if (res.ok) {
                const answerSdp = await res.text();
                await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
            } else {
                throw new Error('MediaMTX WHEP not responding');
            }
        } catch (err) {
            console.log('WebRTC fallback to MJPEG:', err);
            video.style.display = 'none';
            img.style.display = 'block';
            if (badge) {
                badge.textContent = 'MJPEG Standart Akış';
                badge.style.color = '#a3e635';
                badge.style.borderColor = 'rgba(163, 230, 53, 0.4)';
            }
        }
    }

    stopWebRTCStream() {
        if (this.peerConnection) {
            try {
                this.peerConnection.close();
            } catch (e) {}
            this.peerConnection = null;
        }
        const video = document.getElementById('dashWebRTCFeed');
        if (video) {
            video.srcObject = null;
        }
    }

    toggleFullscreenCamera() {
        const container = document.querySelector('.dash-video-wrapper') || document.getElementById('dashCameraFeed');
        if (!container) return;
        if (!document.fullscreenElement) {
            if (container.requestFullscreen) {
                container.requestFullscreen();
            } else if (container.webkitRequestFullscreen) {
                container.webkitRequestFullscreen();
            } else if (container.msRequestFullscreen) {
                container.msRequestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        }
    }


    async loadTokenSettings() {
        try {
            const res = await fetch('/api/settings/tokens');
            if (res.ok) {
                const data = await res.json();
                const accuInput = document.getElementById('accuweatherTokenInput');
                const geminiInput = document.getElementById('geminiTokenInput');

                if (accuInput && data.accuweather) {
                    if (data.accuweather.configured) {
                        accuInput.placeholder = `Mevcut Anahtar: ${data.accuweather.masked} (Değiştirmek için yeni yazın)`;
                    } else {
                        accuInput.placeholder = 'AccuWeather API Key girin...';
                    }
                }

                if (geminiInput && data.gemini) {
                    if (data.gemini.configured) {
                        geminiInput.placeholder = `Mevcut Anahtar: ${data.gemini.masked} (Değiştirmek için yeni yazın)`;
                    } else {
                        geminiInput.placeholder = 'Gemini API Key girin...';
                    }
                }
            }
        } catch (e) {
            console.error('Tokens load error:', e);
        }
    }

    async saveAccuweatherToken() {
        const input = document.getElementById('accuweatherTokenInput');
        const token = input ? input.value.trim() : '';
        if (!token) {
            alert('Lütfen geçerli bir AccuWeather API anahtarı girin.');
            return;
        }

        try {
            const res = await fetch('/api/settings/accuweather_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alert('AccuWeather API anahtarı başarıyla kaydedildi! Garson ekranı artık konumunuza göre bu anahtarı kullanacak.');
                if (input) input.value = '';
                this.loadTokenSettings();
            } else {
                alert('Hata: ' + (data.error || 'Kaydedilemedi.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        }
    }

    async saveGeminiToken() {
        const input = document.getElementById('geminiTokenInput');
        const token = input ? input.value.trim() : '';
        if (!token) {
            alert('Lütfen geçerli bir Gemini API anahtarı girin.');
            return;
        }

        try {
            const res = await fetch('/api/settings/gemini_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alert('Google Gemini API anahtarı başarıyla kaydedildi! AI Garson replikleri artık bu anahtarla çalışacak.');
                if (input) input.value = '';
                this.loadTokenSettings();
            } else {
                alert('Hata: ' + (data.error || 'Kaydedilemedi.'));
            }
        } catch (err) {
            alert('Bağlantı hatası: ' + err);
        }
    }


    async logout() {
        try {
            await fetch('/api/logout', { method: 'POST' });
        } catch (err) {}
        window.location.href = '/admin';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new Dashboard();
    window.dashboard = dashboard;
});
