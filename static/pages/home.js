/**
 * Home Page Functionality
 */

class HomePage {
    constructor() {
        this.init();
    }

    init() {
        this.loadDashboardData();
    }

    async loadDashboardData() {
        try {
            const response = await fetch('/api/get_users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify()
            });

            if (response.ok) {
                const data = await response.json();
                this.displayRecentCustomers(data.customers);
                
                document.getElementById('totalCustomers').textContent = data.customers.length;

                const totalSpent = data.customers.reduce((sum, c) => sum + (c.total_spent || 0), 0);
                document.getElementById('totalRevenue').textContent = `${totalSpent.toFixed(2)} ₺`;
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            dashboardBase.showAlert('Veri yükleme hatası', 'error');
        }

        try {
            const response = await fetch('/api/get_orders', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify()
            });

            if (response.ok) {
                const data = await response.json();
                
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                
                const todaysOrders = data.filter(order => {
                    if (!order.order_date) return false;
                    const orderDate = new Date(order.order_date);
                    orderDate.setHours(0, 0, 0, 0);
                    return orderDate.getTime() === today.getTime();
                });
                
                const todayOrderCount = todaysOrders.length;
                
                if (document.getElementById('todayOrders')) {
                    document.getElementById('todayOrders').textContent = todayOrderCount;
                }
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            dashboardBase.showAlert('Veri yükleme hatası', 'error');
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
                <td>${dashboardBase.escapeHtml(customer.name)}</td>
                <td>${customer.last_login_date || 'Hiç'}</td>
                <td>${(customer.total_spent || 0).toFixed(2)} ₺</td>
            </tr>
        `).join('');
    }
}

let homePage;
document.addEventListener('DOMContentLoaded', () => {
    homePage = new HomePage();
});
