/**
 * Settings Page Functionality
 */

class SettingsPage {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCameras();
        this.openTabFromUrl();
    }

    openTabFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const tab = params.get('tab');
        if (tab) {
            dashboardBase.switchTab(tab);
        }
    }

    setupEventListeners() {
        const changePasswordBtn = document.getElementById('changePasswordBtn');
        if (changePasswordBtn) {
            changePasswordBtn.addEventListener('click', () => this.showChangePasswordModal());
        }

        const logoutAllBtn = document.getElementById('logoutAllBtn');
        if (logoutAllBtn) {
            logoutAllBtn.addEventListener('click', () => this.logoutAll());
        }

        const addCameraForm = document.getElementById('addCameraForm');
        if (addCameraForm) {
            addCameraForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.addCamera();
            });
        }
    }

    async loadCameras() {
        const cameraList = document.getElementById('cameraList');
        if (!cameraList) return;
        try {
            const response = await fetch('/api/camera_settings');
            if (!response.ok) throw new Error('Kameralar yüklenemedi');
            const data = await response.json();
            if (data.cameras.length === 0) {
                cameraList.innerHTML = '<p class="empty">Henüz kamera eklenmemiş.</p>';
                return;
            }
            let html = '<table><thead><tr><th>Ad</th><th>Değer</th><th>Durum</th><th>İşlemler</th></tr></thead><tbody>';
            data.cameras.forEach(cam => {
                const statusClass = cam.is_active ? 'active-cam' : '';
                const statusText = cam.is_active ? '✅ Aktif' : '⏸️ Pasif';
                html += `<tr class="${statusClass}">
                    <td>${dashboardBase.escapeHtml(cam.cam_name)}</td>
                    <td>${dashboardBase.escapeHtml(cam.cam_value)}</td>
                    <td>${statusText}</td>
                    <td>
                        ${!cam.is_active ? `<button class="btn btn-primary btn-sm" onclick="settingsPage.activateCamera(${cam.id})">Aktif Et</button>` : ''}
                        ${!cam.is_active ? `<button class="btn btn-secondary btn-sm" onclick="settingsPage.deleteCamera(${cam.id})">Sil</button>` : ''}
                    </td>
                </tr>`;
            });
            html += '</tbody></table>';
            cameraList.innerHTML = html;
        } catch (error) {
            cameraList.innerHTML = '<p class="empty">Kameralar yüklenirken hata oluştu.</p>';
        }
    }

    async addCamera() {
        const camName = document.getElementById('camName').value.trim();
        const camValue = document.getElementById('camValue').value.trim();
        if (!camName || !camValue) {
            dashboardBase.showAlert('Kamera adı ve değeri gereklidir', 'error');
            return;
        }
        try {
            const response = await fetch('/api/camera_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cam_name: camName, cam_value: camValue })
            });
            const data = await response.json();
            if (response.ok) {
                dashboardBase.showAlert(data.message, 'success');
                document.getElementById('camName').value = '';
                document.getElementById('camValue').value = '';
                this.loadCameras();
            } else {
                dashboardBase.showAlert(data.error || 'Hata oluştu', 'error');
            }
        } catch (error) {
            dashboardBase.showAlert('Kamera eklenirken hata oluştu', 'error');
        }
    }

    async activateCamera(camId) {
        try {
            const response = await fetch(`/api/camera_settings/${camId}/activate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (response.ok) {
                dashboardBase.showAlert(data.message, 'success');
                this.loadCameras();
            } else {
                dashboardBase.showAlert(data.error || 'Hata oluştu', 'error');
            }
        } catch (error) {
            dashboardBase.showAlert('Kamera aktif edilirken hata oluştu', 'error');
        }
    }

    async deleteCamera(camId) {
        if (!confirm('Bu kamerayı silmek istediğinize emin misiniz?')) return;
        try {
            const response = await fetch(`/api/camera_settings/${camId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (response.ok) {
                dashboardBase.showAlert(data.message, 'success');
                this.loadCameras();
            } else {
                dashboardBase.showAlert(data.error || 'Hata oluştu', 'error');
            }
        } catch (error) {
            dashboardBase.showAlert('Kamera silinirken hata oluştu', 'error');
        }
    }

    showChangePasswordModal() {
        dashboardBase.showAlert('Şifre değiştirme özelliği henüz geliştirilmiş değil', 'info');
        // TODO: Implement change password modal
    }

    async logoutAll() {
        if (confirm('Tüm oturumlardan çıkmak istediğinize emin misiniz?')) {
            try {
                const response = await fetch('/api/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    dashboardBase.showAlert('Tüm oturumlardan çıkılıyor...', 'success');
                    setTimeout(() => {
                        window.location.href = '/admin';
                    }, 1500);
                }
            } catch (error) {
                console.error('Error logging out:', error);
                dashboardBase.showAlert('Hata oluştu', 'error');
            }
        }
    }
}

// Initialize when DOM is ready
let settingsPage;
document.addEventListener('DOMContentLoaded', () => {
    settingsPage = new SettingsPage();
});
