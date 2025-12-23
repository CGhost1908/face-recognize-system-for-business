
class CustomersPage {
    constructor() {
        this.customers = [];
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCustomers();
    }

    setupEventListeners() {
        const addCustomerBtn = document.getElementById('addCustomerBtn');
        if (addCustomerBtn) {
            addCustomerBtn.addEventListener('click', () => this.showAddCustomerModal());
        }

        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.filterCustomers(e.target.value));
        }

        const sortBy = document.getElementById('sortBy');
        if (sortBy) {
            sortBy.addEventListener('change', (e) => this.sortCustomers(e.target.value));
        }
    }

    async loadCustomers() {
        try {
            const response = await fetch('/api/get_users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ count: 100 })
            });

            if (response.ok) {
                const data = await response.json();
                this.customers = data.customers;
                this.displayCustomers(this.customers);
            }
        } catch (error) {
            console.error('Error loading customers:', error);
            dashboardBase.showAlert('Müşteri yükleme hatası', 'error');
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
                        <th style="text-align: end;">İşlemler</th>
                    </tr>
                </thead>
                <tbody>
                    ${customers.map(customer => `
                        <tr>
                            <td>${dashboardBase.escapeHtml(customer.name)}</td>
                            <td>${customer.last_login_date || 'Hiç'}</td>
                            <td>${(customer.total_spent || 0).toFixed(2)} ₺</td>
                            <td>
                                <button class="btn btn-secondary" onclick="customersPage.viewCustomer(${customer.id}, '${dashboardBase.escapeHtml(customer.name)}')">Görüntüle</button>
                                <button class="btn btn-secondary" onclick="customersPage.deleteCustomer(${customer.id})">Sil</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    filterCustomers(searchTerm) {
        const filtered = this.customers.filter(c => 
            c.name.toLowerCase().includes(searchTerm.toLowerCase())
        );
        this.displayCustomers(filtered);
    }

    sortCustomers(sortBy) {
        let sorted = [...this.customers];
        
        if (sortBy === 'name') {
            sorted.sort((a, b) => a.name.localeCompare(b.name));
        } else if (sortBy === 'date') {
            sorted.sort((a, b) => new Date(b.last_login_date || 0) - new Date(a.last_login_date || 0));
        } else if (sortBy === 'spending') {
            sorted.sort((a, b) => (b.total_spent || 0) - (a.total_spent || 0));
        }
        
        this.displayCustomers(sorted);
    }

    async viewCustomer(customerId, customerName) {
        try {
            const customerResponse = await fetch(`/api/customer/${encodeURIComponent(customerName)}`);
            const ordersResponse = await fetch(`/api/customer/${encodeURIComponent(customerName)}/get_orders`);
            const foodPercentageResponse = await fetch(`/api/get_food_percentage/${encodeURIComponent(customerName)}`);
            
            if (!customerResponse.ok || !ordersResponse.ok || !foodPercentageResponse.ok) {
                dashboardBase.showAlert('Müşteri detayları yüklenemedi', 'error');
                return;
            }

            const customerData = await customerResponse.json();
            const orders = await ordersResponse.json();
            const foodPercentage = await foodPercentageResponse.json();

            this.showCustomerDetailModal(customerData, orders, foodPercentage);
        } catch (error) {
            console.error('Error loading customer details:', error);
            dashboardBase.showAlert('Müşteri detayları yüklenirken hata oluştu', 'error');
        }
    }

    showCustomerDetailModal(customerData, orders, foodPercentage) {
        const modal = document.createElement('div');
        modal.className = 'modal show';
        modal.id = 'customerDetailModal';

        const foodPercentageHtml = Object.entries(foodPercentage)
            .map(([food, percentage]) => `<li>${dashboardBase.escapeHtml(food)}: %${percentage}</li>`)
            .join('');

        const ordersHtml = Array.isArray(orders) && orders.length > 0
            ? orders.map(order => `<li>${dashboardBase.escapeHtml(order)}</li>`).join('')
            : '<li>Sipariş bulunamadı</li>';

        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Müşteri Detayları: ${dashboardBase.escapeHtml(customerData.name)}</h2>
                    <button class="modal-close" onclick="document.getElementById('customerDetailModal').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="detail-section">
                        <h3>Genel Bilgiler</h3>
                        <p><strong>Adı:</strong> ${dashboardBase.escapeHtml(customerData.name)}</p>
                        <p><strong>Toplam Harcama:</strong> ${(customerData.total_spent || 0).toFixed(2)} ₺</p>
                    </div>

                    <div class="detail-section">
                        <h3>En Sevdiği Yemekler (İlk 5)</h3>
                        <ul>
                            ${foodPercentageHtml || '<li>Veri bulunamadı</li>'}
                        </ul>
                    </div>

                    <div class="detail-section">
                        <h3>Son Siparişler</h3>
                        <ul>
                            ${ordersHtml}
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="document.getElementById('customerDetailModal').remove()">Kapat</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.querySelector('.modal-overlay').addEventListener('click', () => {
            modal.remove();
        });
    }

    async deleteCustomer(customerId) {
        if (confirm('Bu müşteri silinecek. Emin misiniz?')) {
            try {
                const response = await fetch(`/api/user/${customerId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    dashboardBase.showAlert(data.message, 'success');
                    this.loadCustomers();
                } else {
                    const error = await response.json();
                    dashboardBase.showAlert(error.error || 'Müşteri silinirken hata oluştu', 'error');
                }
            } catch (error) {
                console.error('Error deleting customer:', error);
                dashboardBase.showAlert('Müşteri silinirken hata oluştu', 'error');
            }
        }
    }

    showAddCustomerModal() {
        window.location.href = '/dashboard/register';
    }
}

let customersPage;
document.addEventListener('DOMContentLoaded', () => {
    customersPage = new CustomersPage();
});
