/**
 * Settings Page Functionality
 */

class SettingsPage {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
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
