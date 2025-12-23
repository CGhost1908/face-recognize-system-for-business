
class ProductsPage {
    constructor() {
        this.products = [];
        this.init();
    }

    init() {
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
    }

    async loadProducts() {
        try {
            const response = await fetch('/api/get_products', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.products = data.products || [];
                this.displayProducts(this.products);
            } else if (response.status === 404) {
                // No products endpoint yet, show empty state
                this.displayProducts([]);
            }
        } catch (error) {
            console.error('Error loading products:', error);
            // Show empty state if endpoint doesn't exist yet
            this.displayProducts([]);
        }
    }

    displayProducts(products) {
        const container = document.getElementById('productsContainer');
        
        if (products.length === 0) {
            container.innerHTML = '<p class="empty">Hiç ürün bulunmamaktadır. <a href="#" onclick="productsPage.showAddProductModal()">Yeni ürün ekleyin</a></p>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Ürün Adı</th>
                        <th>Kategori</th>
                        <th>Fiyat</th>
                        <th style="text-align: end;">İşlemler</th>
                    </tr>
                </thead>
                <tbody>
                    ${products.map(product => `
                        <tr>
                            <td>${dashboardBase.escapeHtml(product.name)}</td>
                            <td>${dashboardBase.escapeHtml(product.category || '-')}</td>
                            <td>${(product.price || 0).toFixed(2)} ₺</td>
                            <td>
                                <button class="btn btn-secondary" onclick="productsPage.editProduct(${product.id})">Düzenle</button>
                                <button class="btn btn-secondary" onclick="productsPage.deleteProduct(${product.id})">Sil</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    filterProducts(searchTerm) {
        const filtered = this.products.filter(p => 
            p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (p.category && p.category.toLowerCase().includes(searchTerm.toLowerCase()))
        );
        this.displayProducts(filtered);
    }

    sortProducts(sortBy) {
        let sorted = [...this.products];
        
        if (sortBy === 'name') {
            sorted.sort((a, b) => a.name.localeCompare(b.name));
        } else if (sortBy === 'price') {
            sorted.sort((a, b) => (b.price || 0) - (a.price || 0));
        }
        
        this.displayProducts(sorted);
    }

    editProduct(productId) {
        const product = this.products.find(p => p.id === productId);
        if (product) {
            this.showEditProductModal(product);
        }
    }

    deleteProduct(productId) {
        if (confirm('Bu ürün silinecek. Emin misiniz?')) {
            this.performDelete(productId);
        }
    }

    async performDelete(productId) {
        try {
            dashboardBase.showAlert('Ürün siliniyor...', 'info');
            const response = await fetch(`/api/product/${productId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                dashboardBase.showAlert('Ürün başarıyla silindi', 'success');
                this.loadProducts();
            } else {
                const error = await response.json();
                dashboardBase.showAlert(error.error || 'Ürün silinirken hata oluştu', 'error');
            }
        } catch (error) {
            console.error('Error deleting product:', error);
            dashboardBase.showAlert('Sunucuya bağlanırken hata oluştu', 'error');
        }
    }

    showAddProductModal() {
        // Create modal HTML
        const modalHTML = `
            <div id="addProductModal" style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            ">
                <div style="
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 500px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                ">
                    <h2 style="margin-bottom: 20px; color: #333;">Yeni Ürün Ekle</h2>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Ürün Adı *</label>
                        <input type="text" id="productName" placeholder="Ürün adı" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Kategori (İsteğe Bağlı)</label>
                        <input type="text" id="productCategory" placeholder="Kategori" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Fiyat *</label>
                        <input type="number" id="productPrice" placeholder="0.00" min="0" step="0.01" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="display: flex; gap: 10px;">
                        <button onclick="productsPage.addProduct()" style="
                            flex: 1;
                            padding: 12px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            font-weight: 600;
                        ">Ekle</button>
                        <button onclick="productsPage.closeAddProductModal()" style="
                            flex: 1;
                            padding: 12px;
                            background: #e0e0e0;
                            color: #333;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            font-weight: 600;
                        ">İptal</button>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        const existingModal = document.getElementById('addProductModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    closeAddProductModal() {
        const modal = document.getElementById('addProductModal');
        if (modal) {
            modal.remove();
        }
    }

    showEditProductModal(product) {
        const modalHTML = `
            <div id="editProductModal" style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            ">
                <div style="
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 500px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                ">
                    <h2 style="margin-bottom: 20px; color: #333;">Ürün Düzenle</h2>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Ürün Adı *</label>
                        <input type="text" id="editProductName" value="${dashboardBase.escapeHtml(product.name)}" placeholder="Ürün adı" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Kategori (İsteğe Bağlı)</label>
                        <input type="text" id="editProductCategory" value="${dashboardBase.escapeHtml(product.category || '')}" placeholder="Kategori" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Fiyat *</label>
                        <input type="number" id="editProductPrice" value="${product.price || 0}" placeholder="0.00" min="0" step="0.01" style="
                            width: 100%;
                            padding: 10px;
                            border: 1px solid #ddd;
                            border-radius: 6px;
                            font-size: 14px;
                        ">
                    </div>

                    <div style="display: flex; gap: 10px;">
                        <button onclick="productsPage.updateProduct(${product.id})" style="
                            flex: 1;
                            padding: 12px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            font-weight: 600;
                        ">Kaydet</button>
                        <button onclick="productsPage.closeEditProductModal()" style="
                            flex: 1;
                            padding: 12px;
                            background: #e0e0e0;
                            color: #333;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            font-weight: 600;
                        ">İptal</button>
                    </div>
                </div>
            </div>
        `;

        const existingModal = document.getElementById('editProductModal');
        if (existingModal) {
            existingModal.remove();
        }

        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    closeEditProductModal() {
        const modal = document.getElementById('editProductModal');
        if (modal) {
            modal.remove();
        }
    }

    async updateProduct(productId) {
        const name = document.getElementById('editProductName').value.trim();
        const category = document.getElementById('editProductCategory').value.trim();
        const price = parseFloat(document.getElementById('editProductPrice').value);

        if (!name) {
            dashboardBase.showAlert('Lütfen ürün adı giriniz', 'error');
            return;
        }

        if (!price || price < 0) {
            dashboardBase.showAlert('Lütfen geçerli bir fiyat giriniz', 'error');
            return;
        }

        const productData = {
            product_name: name,
            category: category || null,
            price: price
        };

        try {
            dashboardBase.showAlert('Ürün günceleniyor...', 'info');

            const response = await fetch(`/api/product/${productId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(productData)
            });

            if (response.ok) {
                const result = await response.json();
                dashboardBase.showAlert(`"${name}" başarıyla güncellendi`, 'success');
                this.closeEditProductModal();
                this.loadProducts();
            } else {
                const error = await response.json();
                dashboardBase.showAlert(error.message || 'Ürün güncellenirken hata oluştu', 'error');
            }
        } catch (error) {
            console.error('Error updating product:', error);
            dashboardBase.showAlert('Sunucuya bağlanırken hata oluştu', 'error');
        }
    }

    async addProduct() {
        const name = document.getElementById('productName').value.trim();
        const category = document.getElementById('productCategory').value.trim();
        const price = parseFloat(document.getElementById('productPrice').value);

        if (!name) {
            dashboardBase.showAlert('Lütfen ürün adı giriniz', 'error');
            return;
        }

        if (!price || price < 0) {
            dashboardBase.showAlert('Lütfen geçerli bir fiyat giriniz', 'error');
            return;
        }

        const productData = {
            product_name: name,
            category: category || null,
            price: price
        };

        try {
            dashboardBase.showAlert('Ürün ekleniyor...', 'info');

            const response = await fetch('/api/add_product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(productData)
            });

            if (response.ok) {
                const result = await response.json();
                dashboardBase.showAlert(`"${name}" başarıyla eklendi`, 'success');
                this.closeAddProductModal();
                this.loadProducts();
            } else {
                const error = await response.json();
                dashboardBase.showAlert(error.message || 'Ürün eklenirken hata oluştu', 'error');
            }
        } catch (error) {
            console.error('Error adding product:', error);
            dashboardBase.showAlert('Sunucuya bağlanırken hata oluştu', 'error');
        }
    }
}

let productsPage;
document.addEventListener('DOMContentLoaded', () => {
    productsPage = new ProductsPage();
});
