class ProductsPage {
    constructor() {
        this.products = [];
        this.selectedCustomer = "";
        this.init();
    }

    init() {
        this.loadCustomers();
        this.setupEventListeners();
        this.loadProducts();
    }

    setupEventListeners() {
        const addProductBtn = document.getElementById('addProductBtn');
        if (addProductBtn) {
            addProductBtn.addEventListener('click', () => this.showAddProductModal());
        }

        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.filterProducts(e.target.value));
        }

        const sortBy = document.getElementById('sortBy');
        if (sortBy) {
            sortBy.addEventListener('change', (e) => this.sortProducts(e.target.value));
        }

        const customerSelect = document.getElementById('customerSelect');
        if (customerSelect) {
            customerSelect.addEventListener('change', (e) => {
                this.selectedCustomer = e.target.value;
                this.loadProducts();
            });
        }
    }

    async loadCustomers() {
        try {
            const res = await fetch('/api/users');
            if (res.ok) {
                const data = await res.json();
                const select = document.getElementById('customerSelect');
                if (select && data.users) {
                    select.innerHTML = '<option value="">-- Tüm Müşteriler (Genel Popülerlik) --</option>';
                    data.users.forEach(u => {
                        const opt = document.createElement('option');
                        opt.value = u.name;
                        const label = u.user_type === 'guest' ? ` Misafir: ${u.name}` : ` Müşteri: ${u.name}`;
                        opt.textContent = label;
                        select.appendChild(opt);
                    });
                }
            }
        } catch (err) {
            console.error('Error loading customer list:', err);
        }
    }

    async loadProducts() {
        try {
            const url = this.selectedCustomer 
                ? `/api/products?customer_name=${encodeURIComponent(this.selectedCustomer)}`
                : '/api/products';

            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                this.products = data.products || [];
                this.displayProducts(this.products);
            }
        } catch (error) {
            console.error('Error loading products:', error);
            this.displayProducts([]);
        }
    }

    displayProducts(products) {
        const container = document.getElementById('productsContainer');
        
        if (products.length === 0) {
            container.innerHTML = '<div style="padding: 30px; text-align: center; color: #888;">Hiç ürün bulunmamaktadır.</div>';
            return;
        }

        let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px;">';

        products.forEach(p => {
            const isRec = p.is_recommended;
            const badgeHtml = isRec 
                ? `<span style="position: absolute; top: 12px; right: 12px; background: linear-gradient(135deg, #FF9800, #F57C00); color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; box-shadow: 0 2px 8px rgba(255,152,0,0.4);">⭐ Sizin İçin Önerilen</span>`
                : '';

            const userOrdersBadge = p.user_order_count > 0 
                ? `<span style="font-size: 11px; color: #40c4ff; display: block; margin-top: 4px;"><i class="fas fa-history"></i> Daha önce ${p.user_order_count} kez sipariş verildi</span>`
                : '';

            const cardBorder = isRec ? 'border: 2px solid #FF9800; box-shadow: 0 4px 15px rgba(255,152,0,0.2);' : 'border: 1px solid rgba(255,255,255,0.08);';

            html += `
                <div style="position: relative; background: #1e2430; border-radius: 14px; padding: 18px; ${cardBorder} display: flex; flex-direction: column; justify-space-between;">
                    ${badgeHtml}
                    <div>
                        <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #888; font-weight: 600;">${p.category || 'Genel'}</span>
                        <h3 style="margin: 8px 0 6px 0; font-size: 18px; color: #fff;">${p.product_name}</h3>
                        <p style="font-size: 13px; color: #aaa; margin-bottom: 12px; min-height: 36px;">${p.description || ''}</p>
                        ${userOrdersBadge}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.05);">
                        <span style="font-size: 20px; font-weight: bold; color: #00e676;">${p.price.toFixed(2)} ₺</span>
                        <button onclick="productsPage.quickOrder(${p.id}, '${p.product_name}')" style="background: #00e676; color: #000; font-weight: bold; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; transition: all 0.2s;">
                            + Sipariş Ver
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    filterProducts(searchTerm) {
        const filtered = this.products.filter(p => 
            p.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (p.category && p.category.toLowerCase().includes(searchTerm.toLowerCase()))
        );
        this.displayProducts(filtered);
    }

    sortProducts(sortBy) {
        let sorted = [...this.products];
        if (sortBy === 'recommended') {
            sorted.sort((a, b) => (b.score || 0) - (a.score || 0));
        } else if (sortBy === 'name') {
            sorted.sort((a, b) => a.product_name.localeCompare(b.product_name));
        } else if (sortBy === 'price_desc') {
            sorted.sort((a, b) => b.price - a.price);
        } else if (sortBy === 'price_asc') {
            sorted.sort((a, b) => a.price - b.price);
        }
        this.displayProducts(sorted);
    }

    async quickOrder(productId, productName) {
        let targetUser = this.selectedCustomer;
        if (!targetUser) {
            targetUser = prompt("Sipariş verilecek Müşteri / Misafir adını giriniz:");
            if (!targetUser) return;
        }

        try {
            const res = await fetch('/api/orders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_name: targetUser,
                    items: [{ product_id: productId, quantity: 1 }]
                })
            });

            const data = await res.json();
            if (data.success) {
                alert(`✅ ${targetUser} için 1x ${productName} siparişi alındı! (Tutar: ${data.total_amount.toFixed(2)} ₺)`);
                this.loadProducts();
            } else {
                alert(`❌ Sipariş hatası: ${data.error}`);
            }
        } catch (err) {
            console.error('Order error:', err);
            alert('Sipariş verilirken sunucu hatası oluştu.');
        }
    }

    showAddProductModal() {
        const name = prompt("Yeni Ürün Adı:");
        if (!name) return;
        const category = prompt("Kategori (Kahve, Yiyecek, Tatlı vb.):") || "Genel";
        const priceStr = prompt("Fiyat (TL):");
        const price = parseFloat(priceStr);
        if (isNaN(price)) return alert("Geçersiz fiyat!");

        fetch('/api/add_product', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_name: name, category: category, price: price })
        }).then(() => this.loadProducts());
    }
}

let productsPage;
document.addEventListener('DOMContentLoaded', () => {
    productsPage = new ProductsPage();
});
