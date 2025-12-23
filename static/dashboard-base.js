/**
 * Dashboard Base Functionality
 * Shared across all dashboard pages
 */

class DashboardBase {
    constructor() {
        this.setupEventListeners();
        this.loadUserProfile();
    }

    setupEventListeners() {
        // User menu dropdown
        const userMenuBtn = document.getElementById('userMenuBtn');
        const userDropdown = document.getElementById('userDropdown');
        
        if (userMenuBtn) {
            userMenuBtn.addEventListener('click', () => {
                userDropdown.classList.toggle('active');
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.user-menu')) {
                userDropdown?.classList.remove('active');
            }
        });

        // Logout
        const logoutLink = document.getElementById('logoutLink');
        if (logoutLink) {
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.logout();
            });
        }

        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                const nav = document.querySelector('.sidebar-nav');
                nav.classList.toggle('active');
            });
        }

        // Tab buttons in settings
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.switchTab(button.dataset.tab);
            });
        });
    }

    async loadUserProfile() {
        try {
            const response = await fetch('/api/user/profile', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                document.getElementById('username').textContent = data.username;
                
                // Update settings fields if they exist
                if (document.getElementById('settingsUsername')) {
                    document.getElementById('settingsUsername').value = data.username;
                }
                if (document.getElementById('settingsEmail')) {
                    document.getElementById('settingsEmail').value = data.email;
                }
                if (document.getElementById('createdAt')) {
                    document.getElementById('createdAt').value = data.created_at;
                }
                if (document.getElementById('lastLogin')) {
                    document.getElementById('lastLogin').value = data.last_login || 'Hiç';
                }
            } else if (response.status === 401) {
                window.location.href = '/admin?session_expired=true';
            }
        } catch (error) {
            console.error('Error loading profile:', error);
        }
    }

    async logout() {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                this.showAlert('Çıkış yapılıyor...', 'success');
                setTimeout(() => {
                    window.location.href = '/admin';
                }, 1500);
            }
        } catch (error) {
            console.error('Error logging out:', error);
            window.location.href = '/admin';
        }
    }

    switchTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });

        // Remove active from all tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });

        // Show selected tab
        const tabElement = document.getElementById(`${tabName}-tab`);
        if (tabElement) {
            tabElement.classList.add('active');
        }

        // Mark button as active
        const button = document.querySelector(`[data-tab="${tabName}"]`);
        if (button) {
            button.classList.add('active');
        }
    }

    showAlert(message, type = 'info') {
        let alertElement;

        if (type === 'error') {
            alertElement = document.getElementById('errorAlert');
        } else if (type === 'success') {
            alertElement = document.getElementById('successAlert');
        } else {
            alertElement = document.getElementById('infoAlert');
        }

        alertElement.textContent = message;
        alertElement.classList.add('show');

        // Auto-hide after 4 seconds
        setTimeout(() => {
            alertElement.classList.remove('show');
        }, 4000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize dashboard base when DOM is ready
let dashboardBase;
document.addEventListener('DOMContentLoaded', () => {
    dashboardBase = new DashboardBase();
});


//CAM SELECT
function camChanged(value){
    if(value == "6"){
        value = prompt("Lütfen kamera IP adresini girin:", "http://");
        if(!value){
            document.getElementById('cam0').click();
            return;
        }
        localStorage.setItem('cam_number', value);
        fetch('/api/cam_changed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ cam_number: value })
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
        })
        .catch(error => {
            console.error('Hata:', error);
        });
    }else{
        localStorage.setItem('cam_number', value);
        fetch('/api/cam_changed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ cam_number: value })
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
        })
        .catch(error => {
            console.error('Hata:', error);
        });
    }
}

document.addEventListener("DOMContentLoaded", (event) => { 
    document.getElementById(`cam${localStorage.getItem('cam_number') || 0}`).click();
});
