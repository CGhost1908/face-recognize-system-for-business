/**
 * Dashboard Frontend
 * Handles dashboard UI and interactions
 */

class Dashboard {
    constructor() {
        this.currentPage = 'home';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadUserProfile();
        this.loadDashboardData();
    }

    setupEventListeners() {
        // Navigation items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.switchPage(page);
            });
        });

        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                const nav = document.querySelector('.sidebar-nav');
                nav.classList.toggle('active');
            });
        }

        // User menu
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
        document.getElementById('logoutLink').addEventListener('click', (e) => {
            e.preventDefault();
            this.logout();
        });

        // Camera controls
        const changeCameraBtn = document.getElementById('changeCameraBtn');
        if (changeCameraBtn) {
            changeCameraBtn.addEventListener('click', () => this.changeCamera());
        }

        // Add customer button
        const addCustomerBtn = document.getElementById('addCustomerBtn');
        if (addCustomerBtn) {
            addCustomerBtn.addEventListener('click', () => this.showAddCustomerModal());
        }
    }

    switchPage(page) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        // Remove active from all nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        // Show selected page
        const pageElement = document.getElementById(`${page}-page`);
        if (pageElement) {
            pageElement.classList.add('active');
        }

        // Mark nav item as active
        const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (navItem) {
            navItem.classList.add('active');
        }

        // Update page title
        const titles = {
            home: 'Ana Sayfa',
            customers: 'Müşteri Yönetimi',
            camera: 'Kamera Kontrolü',
            reports: 'Raporlar',
            settings: 'Ayarlar'
        };
        document.getElementById('pageTitle').textContent = titles[page] || 'Dashboard';

        this.currentPage = page;

        // Load page-specific data
        if (page === 'customers') {
            this.loadCustomers();
        }
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
                document.getElementById('settingsUsername').value = data.username;
                document.getElementById('settingsEmail').value = data.email;
            } else if (response.status === 401) {
                window.location.href = '/admin?session_expired=true';
            }
        } catch (error) {
            console.error('Error loading profile:', error);
        }
    }

    async loadDashboardData() {
        try {
            // Load recent customers
            const response = await fetch('/api/get_last_customers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ count: 5 })
            });

            if (response.ok) {
                const data = await response.json();
                this.displayRecentCustomers(data.customers);
                
                // Update stats
                document.getElementById('totalCustomers').textContent = data.customers.length;
                
                // Calculate total spent
                const totalSpent = data.customers.reduce((sum, c) => sum + (c.total_spent || 0), 0);
                document.getElementById('totalRevenue').textContent = `$${totalSpent.toFixed(2)}`;
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
        }
    }

    displayRecentCustomers(customers) {
        const tbody = document.getElementById('recentCustomersTable');
        
        if (customers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="empty">Müşteri yok</td></tr>';
            return;
        }

        tbody.innerHTML = customers.map(customer => `
            <tr>
                <td>${this.escapeHtml(customer.name)}</td>
                <td>${customer.last_login_date || 'Hiç'}</td>
                <td>$${(customer.total_spent || 0).toFixed(2)}</td>
            </tr>
        `).join('');
    }

    async loadCustomers() {
        try {
            const response = await fetch('/api/get_last_customers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ count: 100 })
            });

            if (response.ok) {
                const data = await response.json();
                this.displayCustomers(data.customers);
            }
        } catch (error) {
            console.error('Error loading customers:', error);
            this.showAlert('Müşteri yükleme hatası', 'error');
        }
    }

    displayCustomers(customers) {
        const container = document.getElementById('customersContainer');
        
        if (customers.length === 0) {
            container.innerHTML = '<p class="empty">Müşteri bulunamadı</p>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>İsim</th>
                        <th>Son Giriş</th>
                        <th>Toplam Harcama</th>
                        <th>İşlemler</th>
                    </tr>
                </thead>
                <tbody>
                    ${customers.map(customer => `
                        <tr>
                            <td>${this.escapeHtml(customer.name)}</td>
                            <td>${customer.last_login_date || 'Hiç'}</td>
                            <td>$${(customer.total_spent || 0).toFixed(2)}</td>
                            <td>
                                <button class="btn btn-secondary" onclick="dashboard.viewCustomer('${customer.id}')">Görüntüle</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    async changeCamera() {
        const cameraIndex = document.getElementById('cameraIndex').value;

        try {
            const response = await fetch('/api/cam_changed', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ cam_number: parseInt(cameraIndex) })
            });

            if (response.ok) {
                const data = await response.json();
                this.showAlert(data.message, 'success');
            } else {
                this.showAlert('Kamera değiştirilirken hata oluştu', 'error');
            }
        } catch (error) {
            console.error('Error changing camera:', error);
            this.showAlert('Hata: Kamera değiştirilemiyor', 'error');
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

    showAddCustomerModal() {
        this.showAlert('Bu özellik henüz geliştirilmiş değil', 'info');
    }

    viewCustomer(customerId) {
        this.showAlert(`Müşteri ${customerId} görüntüleniyor...`, 'info');
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

// Initialize dashboard when DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new Dashboard();
});
