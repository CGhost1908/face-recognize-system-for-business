/**
 * UniFace Cafe Kiosk - Main Client Logic
 * Real-Time Face Recognition, Personalized Product Ranking, and Instant Order Flow
 */

let customer_name = null;
let current_user_type = 'guest';
let recognitionPollingInterval = null;
let all_products = [];
let active_category = 'all';
let cart = {}; // product_id -> { id, name, price, quantity, category }

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    getProducts();
    startContinuousRecognition();
});

// --- PRODUCT CATALOG & PERSONALIZED RECOMMENDATIONS ---

function getProducts(customer = null) {
    let url = '/api/products';
    if (customer) {
        url += '?customer_name=' + encodeURIComponent(customer);
    }

    fetch(url)
        .then(res => res.json())
        .then(data => {
            all_products = data.products || [];
            renderProducts();
        })
        .catch(err => {
            console.error('Error fetching products:', err);
        });
}

function normalizeCategoryStr(str) {
    if (!str) return '';
    return str.toLowerCase()
        .replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's')
        .replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ç/g, 'c')
        .replace(/[^a-z0-9]/g, '');
}

function filterCategory(category, tabBtn) {
    active_category = category;
    
    // Update active tab button style
    const tabs = document.querySelectorAll('.category-tabs .tab-btn');
    tabs.forEach(btn => btn.classList.remove('active'));
    if (tabBtn) tabBtn.classList.add('active');

    renderProducts();
}

function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;

    if (!all_products || all_products.length === 0) {
        grid.innerHTML = '<p class="empty-state">Menüde aktif ürün bulunmuyor.</p>';
        return;
    }

    const normActive = normalizeCategoryStr(active_category);
    const filtered = (active_category === 'all' || normActive === 'all' || normActive === 'tumu')
        ? all_products 
        : all_products.filter(p => normalizeCategoryStr(p.category) === normActive);

    grid.innerHTML = '';

    filtered.forEach(product => {
        const pid = product.id;
        const inCartQty = cart[pid] ? cart[pid].quantity : 0;
        const isFavorite = product.is_favorite || false;
        const isRecommended = product.is_recommended || false;
        const badgeText = product.badge || '';

        const card = document.createElement('div');
        card.className = `product-card ${isFavorite ? 'favorite-item' : ''} ${isRecommended ? 'recommended-item' : ''}`;
        card.dataset.id = pid;

        // Image URL fallback
        const imgUrl = product.image_url || '/static/images/placeholder.jpg';

        card.innerHTML = `
            ${badgeText ? `<div class="product-badge">${badgeText}</div>` : ''}
            <div class="product-img-wrap">
                <img src="${imgUrl}" alt="${product.product_name}" onerror="this.src='https://cdn.pixabay.com/photo/2015/07/12/14/26/coffee-842020_640.jpg'" />
            </div>
            <div class="product-body">
                <span class="product-category">${product.category}</span>
                <h3 class="product-title">${product.product_name}</h3>
                <p class="product-desc">${product.description || ''}</p>
                
                <div class="product-footer">
                    <span class="product-price">${parseFloat(product.price).toFixed(2)} ₺</span>
                    
                    <div class="product-action-box" id="action-box-${pid}">
                        ${inCartQty > 0 
                            ? `<div class="qty-counter">
                                 <button class="btn-qty minus" onclick="updateItemQuantity(${pid}, -1)">−</button>
                                 <span class="qty-number">${inCartQty}</span>
                                 <button class="btn-qty plus" onclick="updateItemQuantity(${pid}, 1)">+</button>
                               </div>`
                            : `<button class="btn-add-cart" onclick="updateItemQuantity(${pid}, 1)">
                                 <span class="material-symbols-outlined" style="font-size:16px;">add</span> Ekle
                               </button>`
                        }
                    </div>
                </div>
            </div>
        `;

        grid.appendChild(card);
    });
}

// --- SHOPPING CART MANAGEMENT ---

function updateItemQuantity(productId, delta) {
    const prod = all_products.find(p => p.id === productId);
    if (!prod) return;

    if (!cart[productId]) {
        cart[productId] = {
            id: prod.id,
            product_id: prod.id,
            name: prod.product_name,
            product_name: prod.product_name,
            price: parseFloat(prod.price),
            quantity: 0,
            category: prod.category
        };
    }

    cart[productId].quantity += delta;

    if (cart[productId].quantity <= 0) {
        delete cart[productId];
    }

    updateCartUI();
    updateProductCardAction(productId);
}

function updateProductCardAction(productId) {
    const box = document.getElementById(`action-box-${productId}`);
    if (!box) return;

    const inCartQty = cart[productId] ? cart[productId].quantity : 0;
    if (inCartQty > 0) {
        box.innerHTML = `
            <div class="qty-counter">
                <button class="btn-qty minus" onclick="updateItemQuantity(${productId}, -1)">−</button>
                <span class="qty-number">${inCartQty}</span>
                <button class="btn-qty plus" onclick="updateItemQuantity(${productId}, 1)">+</button>
            </div>
        `;
    } else {
        box.innerHTML = `
            <button class="btn-add-cart" onclick="updateItemQuantity(${productId}, 1)">
                <span class="material-symbols-outlined" style="font-size:16px;">add</span> Ekle
            </button>
        `;
    }
}

function updateCartUI() {
    const cartCountElem = document.getElementById('cartItemCount');
    const cartTotalElem = document.getElementById('cartTotalPrice');
    const cartBar = document.getElementById('cartBottomBar');

    let totalQty = 0;
    let totalPrice = 0.0;

    Object.values(cart).forEach(item => {
        totalQty += item.quantity;
        totalPrice += item.price * item.quantity;
    });

    if (cartCountElem) cartCountElem.innerText = `${totalQty} Ürün`;
    if (cartTotalElem) cartTotalElem.innerText = `${totalPrice.toFixed(2)} ₺`;

    if (cartBar) {
        if (totalQty > 0) {
            cartBar.classList.add('has-items');
        } else {
            cartBar.classList.remove('has-items');
        }
    }
}

// --- ORDER PLACEMENT FLOW ---

function orderFood() {
    const items = Object.values(cart).map(item => ({
        product_id: item.id,
        product_name: item.name,
        quantity: item.quantity,
        price: item.price
    }));

    if (items.length === 0) {
        alert("Lütfen menüden en az bir ürün seçiniz.");
        return;
    }

    const orderUser = customer_name || "Misafir";

    const payload = {
        user_name: orderUser,
        items: items
    };

    fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(response => {
        if (response.success) {
            alert(`🎉 ${response.message || 'Siparişiniz başarıyla alındı!'}\nToplam: ${response.total_amount.toFixed(2)} ₺`);
            
            // Clear cart
            cart = {};
            updateCartUI();
            
            // Refresh customer stats & re-rank favorites
            if (customer_name) {
                updateTotalSpent();
                updateFoodPercentage(customer_name);
                showOrderHistory();
                getProducts(customer_name);
            } else {
                getProducts();
            }
        } else {
            alert("❌ Sipariş verilemedi: " + (response.error || response.message));
        }
    })
    .catch(err => {
        console.error("Order placement error:", err);
        alert("Bağlantı hatası oluştu.");
    });
}

// --- REAL-TIME FACE RECOGNITION POLLING & USER UPDATES ---

function startContinuousRecognition() {
    if (recognitionPollingInterval) clearInterval(recognitionPollingInterval);

    recognitionPollingInterval = setInterval(() => {
        fetch('/api/current_recognized_person')
            .then(res => res.json())
            .then(response => {
                if (response.recognized && response.name) {
                    if (customer_name !== response.name) {
                        updateRecognizedUser(
                            response.name,
                            response.user_type || 'customer',
                            response.id,
                            response.image,
                            response.last_login_date,
                            response.total_spent
                        );
                    }
                } else {
                    if (customer_name !== null) {
                        clearRecognizedUser();
                    }
                }
            })
            .catch(err => {
                console.error('Recognition polling error:', err);
            });
    }, 600);
}

function updateRecognizedUser(name, userType, id, image, last_login_date, total_spent) {
    customer_name = name;
    current_user_type = userType;

    // 1. Update Header Greeting
    const nameElem = document.getElementById("recognized-name");
    if (nameElem) {
        nameElem.innerText = `Hoş Geldiniz, ${name}!`;
    }

    const greetingTitle = document.getElementById("kioskGreeting");
    const greetingSub = document.getElementById("kioskGreetingSub");
    if (greetingTitle) {
        greetingTitle.innerText = `Merhaba, ${name}`;
    }
    if (greetingSub) {
        greetingSub.innerText = `Damak zevkinize göre en çok tercih ettiğiniz favori lezzetleriniz en başta hazırlandı!`;
    }

    // 2. User Badge Pill
    const pill = document.getElementById("user-badge-pill");
    const renameBox = document.getElementById("guest-rename-box");
    if (pill) {
        if (userType === 'customer') {
            pill.className = "badge-pill customer";
            pill.innerText = "Kayıtlı Müşteri";
            if (renameBox) renameBox.style.display = 'none';
        } else {
            pill.className = "badge-pill guest";
            pill.innerText = "Misafir";
            if (renameBox) renameBox.style.display = 'block';
        }
    }

    // 3. User Avatar
    const imgElem = document.getElementById("recognized-image");
    if (imgElem && image) {
        imgElem.src = image.startsWith('data:') ? image : ("data:image/jpeg;base64," + image);
    }

    // 4. Last Login & Total Spent
    const lastLoginText = document.getElementById("last-login-text");
    if (lastLoginText) {
        lastLoginText.innerText = last_login_date || "Yeni Giriş";
    }

    const spentElem = document.getElementById("total-spent-text");
    if (spentElem) {
        spentElem.innerText = `${parseFloat(total_spent || 0).toFixed(2)} ₺`;
    }

    // 5. Update Favorite Foods Percentage & Past Orders
    updateFoodPercentage(name);
    showOrderHistory();

    // 6. Automatically Fetch Personalized Product Ranking for Recognized Customer!
    getProducts(name);
}

function clearRecognizedUser() {
    customer_name = null;
    current_user_type = 'guest';

    const nameElem = document.getElementById("recognized-name");
    if (nameElem) nameElem.innerText = "Müşteri Bekleniyor...";

    const greetingTitle = document.getElementById("kioskGreeting");
    const greetingSub = document.getElementById("kioskGreetingSub");
    if (greetingTitle) greetingTitle.innerText = "Menü & Hızlı Sipariş";
    if (greetingSub) greetingSub.innerText = "Kameraya bakarak giriş yaptığınızda favori ürünleriniz en başta listelenir.";

    const pill = document.getElementById("user-badge-pill");
    if (pill) {
        pill.className = "badge-pill guest";
        pill.innerText = "Misafir";
    }

    const renameBox = document.getElementById("guest-rename-box");
    if (renameBox) renameBox.style.display = 'none';

    const imgElem = document.getElementById("recognized-image");
    if (imgElem) {
        imgElem.src = "https://cdn.pixabay.com/photo/2023/02/18/11/00/icon-7797704_640.png";
    }

    const lastLoginText = document.getElementById("last-login-text");
    if (lastLoginText) lastLoginText.innerText = "--";

    const spentElem = document.getElementById("total-spent-text");
    if (spentElem) spentElem.innerText = "0.00 ₺";

    const percentage = document.querySelector('.percentage');
    if (percentage) percentage.innerHTML = 'Henüz sipariş verisi yok.';

    const orderHistory = document.querySelector('.order-history');
    if (orderHistory) orderHistory.innerHTML = 'Geçmiş sipariş bulunmuyor.';

    // Reset products to standard popularity ranking
    getProducts();
}

function updateFoodPercentage(customerName) {
    if (!customerName) return;
    fetch(`/api/get_food_percentage/${encodeURIComponent(customerName)}`)
        .then(res => res.json())
        .then(response => {
            const container = document.querySelector('.percentage');
            if (!container) return;
            container.innerHTML = '';
            const entries = Object.entries(response);
            if (entries.length === 0 || (entries.length === 1 && entries[0][0] === "Veri yok")) {
                container.innerHTML = 'Henüz sipariş verisi yok.';
                return;
            }
            entries.forEach(([food, percent]) => {
                const item = document.createElement('div');
                item.className = 'pref-stat-row';
                item.innerHTML = `
                    <span class="pref-name">${food}</span>
                    <span class="pref-val">%${percent}</span>
                `;
                container.appendChild(item);
            });
        })
        .catch(err => console.error(err));
}

function showOrderHistory() {
    if (!customer_name) return;
    fetch(`/api/customer/${encodeURIComponent(customer_name)}/get_orders`)
        .then(res => res.json())
        .then(orders => {
            const orderHistory = document.querySelector('.order-history');
            if (!orderHistory) return;
            orderHistory.innerHTML = '';

            if (!orders || orders.length === 0) {
                orderHistory.innerHTML = '<div class="order-item-empty">Geçmiş sipariş bulunmuyor.</div>';
            } else {
                orders.slice(0, 8).forEach(order => {
                    const div = document.createElement('div');
                    div.className = 'order-history-item';
                    div.innerHTML = `<span class="material-symbols-outlined history-icon">check_circle</span> <span>${order}</span>`;
                    orderHistory.appendChild(div);
                });
            }
        })
        .catch(err => console.error(err));
}

function updateTotalSpent() {
    if (!customer_name) return;
    fetch(`/api/customer/${encodeURIComponent(customer_name)}/total_spent`)
        .then(res => res.json())
        .then(response => {
            const spentElem = document.getElementById("total-spent-text");
            if (spentElem) {
                spentElem.innerText = `${parseFloat(response.total_spent || 0).toFixed(2)} ₺`;
            }
        })
        .catch(err => console.error(err));
}

// --- GUEST SELF-NAMING / PROFILE CONVERSION ---

function openRenameModal() {
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('newCustomerNameInput');
    if (modal) {
        modal.style.display = 'flex';
        if (input) {
            input.value = '';
            input.focus();
        }
    }
}

function closeRenameModal() {
    const modal = document.getElementById('renameModal');
    if (modal) modal.style.display = 'none';
}

function submitRenameGuest() {
    const input = document.getElementById('newCustomerNameInput');
    const newName = input ? input.value.trim() : '';

    if (!newName) {
        alert("Lütfen adınızı giriniz.");
        return;
    }

    if (!customer_name) {
        alert("Aktif misafir bulunamadı.");
        return;
    }

    fetch('/api/rename_guest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            guest_name: customer_name,
            new_name: newName
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(`🎉 Hoş geldiniz, ${newName}! Profiliniz başarıyla oluşturuldu.`);
            closeRenameModal();
            customer_name = newName;
            updateRecognizedUser(newName, 'customer', 0, '', 'Şimdi', 0);
        } else {
            alert("Hata: " + data.error);
        }
    })
    .catch(err => {
        console.error("Rename guest error:", err);
        alert("Profil kaydedilemedi.");
    });
}

// --- MENU SUGGESTION MODAL ---

function openSuggestFood() {
    const modal = document.getElementById('suggestionModal');
    if (modal) modal.style.display = 'flex';
    suggestFood();
}

function closeSuggestModal() {
    const modal = document.getElementById('suggestionModal');
    if (modal) modal.style.display = 'none';
}

function suggestFood() {
    const customer = customer_name || '';
    fetch('/api/suggest_food?customer=' + encodeURIComponent(customer))
        .then(res => res.json())
        .then(response => {
            const resultBox = document.getElementById('suggestResult');
            const nameBox = document.getElementById('suggestedFoodName');
            if (resultBox && nameBox) {
                nameBox.innerText = response.food || 'Caffe Latte';
                resultBox.style.display = 'block';
            }
        })
        .catch(err => console.error("Food suggestion error:", err));
}

// --- FULLSCREEN FOCUS MODE ---

function toggleCameraFullscreen() {
    const overlay = document.getElementById('cameraFullscreenOverlay');
    const fullVideo = document.getElementById('fullscreenVideoFeed');
    const mainVideo = document.getElementById('videoFeed');
    if (!overlay || !fullVideo || !mainVideo) return;

    if (overlay.style.display === 'none' || overlay.style.display === '') {
        fullVideo.src = mainVideo.src;
        fullVideo.classList.remove('cover-mode');
        const btnText = document.getElementById('fitModeText');
        const btnIcon = document.getElementById('fitModeIcon');
        if (btnText) btnText.textContent = 'Tam Kadraj (Sığdır)';
        if (btnIcon) btnIcon.textContent = 'fit_screen';

        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    } else {
        fullVideo.src = '';
        overlay.style.display = 'none';
        document.body.style.overflow = 'auto';
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
    }
}

function toggleFullscreenFitMode() {
    const fullVideo = document.getElementById('fullscreenVideoFeed');
    const btnText = document.getElementById('fitModeText');
    const btnIcon = document.getElementById('fitModeIcon');
    if (!fullVideo) return;

    if (fullVideo.classList.contains('cover-mode')) {
        fullVideo.classList.remove('cover-mode');
        if (btnText) btnText.textContent = 'Tam Kadraj (Sığdır)';
        if (btnIcon) btnIcon.textContent = 'fit_screen';
    } else {
        fullVideo.classList.add('cover-mode');
        if (btnText) btnText.textContent = 'Ekranı Kapla';
        if (btnIcon) btnIcon.textContent = 'fullscreen';
    }
}

function toggleBrowserFullscreen() {
    const overlay = document.getElementById('cameraFullscreenOverlay');
    const target = overlay || document.documentElement;
    if (!document.fullscreenElement) {
        if (target.requestFullscreen) {
            target.requestFullscreen().catch(() => {});
        } else if (target.webkitRequestFullscreen) {
            target.webkitRequestFullscreen();
        } else if (target.msRequestFullscreen) {
            target.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen().catch(() => {});
        }
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || e.key === 'Esc') {
        const overlay = document.getElementById('cameraFullscreenOverlay');
        if (overlay && overlay.style.display === 'flex') {
            toggleCameraFullscreen();
        }
        closeSuggestModal();
        closeRenameModal();
    }
});





