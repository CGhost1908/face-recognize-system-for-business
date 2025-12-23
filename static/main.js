let customer_name = null;
let recognitionInterval;

let products = [];

function getPreference(){
    if (!customer_name) return alert("Kullanıcı tanınmadı.");

    fetch(`/api/customer/${customer_name}/preferences`)
    .then(res => res.json())
    .then(response => {
        if (response.error) {
            alert("Tercih bulunamadı.");
        } else {
            const list = response.message;
            const metin = list.join("\n");
            alert("Tercihler:\n" + metin);
        }
    })
    .catch(err => {
        alert("Tercih verisi alınamadı.");
        console.error(err);
    });
}

function savePreference() {
    if (!customer_name) return alert("Kullanıcı tanınmadı.");

    const food = document.getElementById("food-name").value.trim();
    const preference = document.getElementById("food-pref").value.trim();

    if (!food || !preference) {
        return alert("Lütfen hem yemek adını hem tercihi gir.");
    }

    fetch(`/api/preferences/${customer_name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ food, preference })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        document.getElementById("food-name").value = "";
        document.getElementById("food-pref").value = "";
    })
    .catch(err => {
        alert("Tercih kaydedilemedi.");
        console.error(err);
    });
}


function updateFoodPercentage(customer_name){
    fetch(`/api/get_food_percentage/${customer_name}`)
    .then(res => res.json())
    .then(response => {
        console.log(response);
        const container = document.querySelector('.percentage');
        container.innerHTML = ''; 
        for (const [food, percent] of Object.entries(response)) {
            const p = document.createElement('p');
            p.textContent = `${food}: %${percent}`;
            container.appendChild(p);
        }
    })
    .catch(err => console.error(err));
}

function updateRecognizedUser(name, id, image, last_login_date){
    customer_name = name;

    document.getElementById("recognized-name").innerText = "Welcome " + name;

    document.querySelector(".user nav").style.display = "flex";

    let imageElement = document.getElementById("recognized-image");
    imageElement.src = "data:image/jpeg;base64," + image;
    imageElement.style.display = "block";

    addRecognizedCustomerToLastCustomers(name, image, last_login_date)
    updateLastLoginDate();
    updateTotalSpent();
    updateFoodPercentage(customer_name);
    showOrderHistory();
}

function showOrderHistory(){
    if (!customer_name) return;
    fetch(`/api/customer/${customer_name}/get_orders`)
    .then(res => res.json())
    .then(orders => {
        const orderHistory = document.querySelector('.order-history');
        orderHistory.innerHTML = '';
    
        console.log(orders);
    
        if(orders.length == 0){
            const createOrder = document.createElement('div');
            createOrder.classList.add('order-item');
            createOrder.innerHTML = "Henüz sipariş vermediniz.";
            orderHistory.appendChild(createOrder);
        }else{
            orders.forEach(order => {
                const createOrder = document.createElement('div');
                createOrder.classList.add('order-item');
                createOrder.innerHTML = order;
                orderHistory.appendChild(createOrder);
            });
        }
    })
    .catch(err => console.error(err));       
}

function updateTotalSpent(){
    if (!customer_name) return;
    fetch(`/api/customer/${customer_name}/total_spent`)
    .then(res => res.json())
    .then(response => {
        document.getElementById("total-spent-text").innerText = `${response.total_spent} ₺`;
    })
    .catch(err => console.error(err));
}

function updateLastLoginDate(){
    if (!customer_name) return;
    document.querySelector('.last-login-label').style.display = 'flex';
    fetch(`/api/customer/${customer_name}/last_login`)
    .then(res => res.json())
    .then(response => {
        document.getElementById("last-login-text").innerText = response.last_login || "Yok";
    })
    .catch(err => console.error(err));
}


document.querySelectorAll('.order-item').forEach(item => {
  let isScrolling = false;
  let startX;
  let scrollLeft;

  item.addEventListener('mousedown', e => {
    isScrolling = true;
    startX = e.clientX;
    scrollLeft = item.scrollLeft;
    item.classList.add('active');

    const onMouseMove = e => {
      if (!isScrolling) return;
      const distance = e.clientX - startX;
      item.scrollLeft = scrollLeft - distance;
    };

    const onMouseUp = () => {
      isScrolling = false;
      item.classList.remove('active');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });
});

//Weather
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            fetch('/api/weather', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ lat: lat, lon: lon })
            })
            .then(res => res.json())
            .then(data => {
                if (data.cod === 200) {
                    const weather = data.weather[0].description;
                    const temperature = data.main.temp;
                    const iconCode = data.weather[0].icon;
                    const iconUrl = `https://openweathermap.org/img/wn/${iconCode}@2x.png`;
                    document.querySelector(".location").textContent = data.name;
                    document.querySelector(".icon").src = iconUrl;
                    document.querySelector(".temperature").textContent = temperature + "°C";
                    document.querySelector("#temperature").value = temperature;
                } else {
                    alert("Hava durumu alınamadı.");
                    console.log(data);
                }
            })
            .catch(err => {
                console.error(err);
            });
        },
        error => {
            console.error(error);
        }
    );
}

function getProducts(){
    fetch('/api/get_products', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        products = data.products || [];
        console.log(products);
        listProducts();
    })
    .catch(err => {
        console.error('Error fetching products:', err);
    });
}

// const foods = [
//   'mantı', 'köfte', 'makarna', 'tost', 'burger', 'balık', 'pizza',
//   'çorba', 'menemen', 'kumpir', 'pilav', 'lahmacun', 'simit', 'yumurta',
//   'patates kızartması', 'sosisli', 'salata', 'gözleme', 'döner'
// ];

// const drinks = [
//   'kola', 'fanta', 'sprite', 'ayran', 'limonata', 'milkshake',
//   'çay', 'kahve', 'su', 'soğuk çay', 'portakal suyu', 'elma suyu',
//   'şalgam', 'soda', 'nescafe'
// ];

// function setupAutocomplete(inputId, resultsId, list) {
//     const input = document.getElementById(inputId);
//     const results = document.getElementById(resultsId);

//     input.addEventListener('input', () => {
//         const query = input.value.toLowerCase().trim();
//         results.innerHTML = '';

//         if(!query){
//             results.style.display = 'none';
//             return;
//         }

//         const matches = list.filter(item => item.toLowerCase().includes(query));
//         matches.forEach(match => {
//             const div = document.createElement('div');
//             div.className = 'autocomplete-item';
//             div.textContent = match;
//             div.addEventListener('click', () => {
//                 input.value = match;
//                 results.innerHTML = '';
//             });
//             results.appendChild(div);
//         });

//         console.log(query)
//         if (matches.length === 0){
//             results.style.display = 'none';
//         }else{
//             results.style.display = 'block';
//         }
//     });

//     input.addEventListener('keydown', (e) => {
//         if (e.key === 'Enter') {
//           const first = results.querySelector('.autocomplete-item');
//           if (first) first.click();
//         }
//     });

//     document.addEventListener('click', (e) => {
//         if(!results.contains(e.target) && e.target !== input){
//             results.innerHTML = '';
//             results.style.display = 'none';
//         }
//     });
// }

// document.addEventListener('DOMContentLoaded', function() {

// });


// function addFood() {
//     const input = document.getElementById('food-input');
//     const value = input.value.trim().toLowerCase();
//     if (foods.includes(value)) {
//         const container = document.getElementById('food-autocomplete-wrapper');
//         const item = document.createElement('div');
//         item.textContent = value;
//         item.className = 'added-item';
//         const preferenceInput = document.createElement('input');
//         preferenceInput.type = 'text';
//         preferenceInput.placeholder = 'Write your preference';
//         preferenceInput.className = 'preference-input';
//         item.appendChild(preferenceInput);
//         container.querySelector('div').insertBefore(item, input);
//         input.value = '';
//     }
// }

// function addDrink() {
//     const input = document.getElementById('drink-input');
//     const value = input.value.trim().toLowerCase();
//     if (drinks.includes(value)) {
//         const container = document.getElementById('drink-autocomplete-wrapper');
//         const item = document.createElement('div');
//         item.textContent = value;
//         item.className = 'added-item';
//         container.querySelector('div').insertBefore(item, input);
//         input.value = '';
//     }
// }

function listProducts(){
    const items = document.querySelector('.items');
    if (!items || !products || products.length === 0) {
        items.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #999;">No products available</p>';
        return;
    }
    
    items.innerHTML = '';
    
    const groupedProducts = {};
    products.forEach(product => {
        const category = product.category || 'Diğer';
        if (!groupedProducts[category]) {
            groupedProducts[category] = [];
        }
        groupedProducts[category].push(product);
    });
    
    Object.keys(groupedProducts).sort().forEach(category => {
        const categoryHeader = document.createElement('div');
        categoryHeader.className = 'category-header';
        categoryHeader.innerHTML = `<h2>${category}</h2>`;
        categoryHeader.style.gridColumn = '1 / -1';
        items.appendChild(categoryHeader);
        
        groupedProducts[category].forEach(product => {
            const productItem = document.createElement('div');
            productItem.className = 'product-item';
            productItem.innerHTML = `
                <div class="product-header">
                    <h3>${product.name}</h3>
                </div>
                <div class="product-price">${product.price}₺</div>
                <button class="product-add-btn" onclick="addProductToOrder('${product.name}', ${product.price}, this)">Add</button>
            `;
            items.appendChild(productItem);
        });
    });
}

function addProductToOrder(productName, productPrice, btn) {
    if (!btn) return;
    
    const quantityControls = document.createElement('div');
    quantityControls.className = 'product-qty-controls';
    quantityControls.dataset.productName = productName;
    quantityControls.dataset.productPrice = productPrice;
    quantityControls.innerHTML = `
        <button class="qty-decrease" onclick="decreaseProductQty(this, '${productName}', ${productPrice})">−</button>
        <input type="number" class="product-quantity" value="1" min="1" readonly>
        <button class="qty-increase" onclick="increaseProductQty(this, '${productName}', ${productPrice})">+</button>
    `;
    
    btn.replaceWith(quantityControls);
}

function increaseProductQty(btn, productName, price) {
    const controls = btn.closest('.product-qty-controls');
    const quantityInput = controls.querySelector('.product-quantity');
    quantityInput.value = parseInt(quantityInput.value) + 1;
}

function decreaseProductQty(btn, productName, price) {
    const controls = btn.closest('.product-qty-controls');
    const quantityInput = controls.querySelector('.product-quantity');
    const currentQty = parseInt(quantityInput.value);
    
    if (currentQty > 1) {
        quantityInput.value = currentQty - 1;
    } else {
        const productItem = controls.closest('.product-item');
        const addBtn = document.createElement('button');
        addBtn.className = 'product-add-btn';
        addBtn.textContent = 'Ekle';
        addBtn.onclick = function() {
            addProductToOrder(productName, price, this);
        };
        controls.replaceWith(addBtn);
    }
}

function orderFood(){
    const productGrid = document.querySelector('.items');
    const values = [];
    let total = 0;

    const qtyControls = productGrid.querySelectorAll('.product-qty-controls');
    qtyControls.forEach(control => {
        const productName = control.dataset.productName;
        const productPrice = parseFloat(control.dataset.productPrice);
        const quantity = parseInt(control.querySelector('.product-quantity').value) || 0;
        
        for (let i = 0; i < quantity; i++) {
            values.push(productName);
        }
        total += productPrice * quantity;
    });

    if (!customer_name) return alert("Kullanıcı girisi yapin.");
    
    if (values.length === 0) return alert("Lütfen ürün seçiniz.");

    fetch(`/api/order_food/${customer_name}`,{
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: customer_name,
            foods: values,
            total: total
        })
    })
    .then(res => res.json())
    .then(response => {
        alert(response.message);    
        showOrderHistory();
        updateTotalSpent();
        updateFoodPercentage(customer_name);
        
        const qtyControls = productGrid.querySelectorAll('.product-qty-controls');
        qtyControls.forEach(control => {
            const productName = control.dataset.productName;
            const productPrice = parseFloat(control.dataset.productPrice);
            const addBtn = document.createElement('button');
            addBtn.className = 'product-add-btn';
            addBtn.textContent = 'Ekle';
            addBtn.onclick = function() {
                addProductToOrder(productName, productPrice, this);
            };
            control.replaceWith(addBtn);
        });
    })
    .catch(err => alert("Hata: " + err));
}

function openSuggestFood(){
    document.querySelector('.suggestion').style.display = 'flex';
}

function scrollVerticalLeft(scrollable){
    scrollable.scrollBy({ left: -100, behavior: 'smooth' });
}

function scrollVerticalRight(scrollable){
    scrollable.scrollBy({ left: 100, behavior: 'smooth' });
}

document.addEventListener('click', function(event) {
    if(event.target === document.querySelector('.suggestion') && event.target != document.querySelector('.suggestion-popup')){
        document.querySelector('.suggestion').style.display = 'none';
    }
})

function suggestFood() {
    const drink = document.querySelector("#beverage").value;
    const weather = document.querySelector("#weather").value;
    const temperature = document.querySelector("#temperature").value;
    const meal = document.querySelector("#meal").value;

    fetch('/api/suggest_food', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({drink, weather, temperature, meal})
    })
    .then(res => res.json())
    .then(response => {
        alert(`Önerilen Yemek: ${response.suggestion}!`);
    })
    .catch(err => alert("Hata: " + err));
}

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

function triggerRecognize(){
    fetch('/api/recognize', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
    })
    .then(res => res.json())
    .then(response => {
        if(response.error){
            alert(response.error);
            console.error("Yüz tanınamadı.");
            return;
        }
        updateRecognizedUser(response.name, response.id, response.image, response.last_login_date);
    })
    .catch(error =>{
        alert(error);
        console.error(error);
    });
}

function toggleCameraMode(){
    const videoFeed = document.getElementById('videoFeed');
    if (videoFeed.style.display === 'none' || videoFeed.style.display === '') {
        videoFeed.style.display = 'flex';
    } else {
        videoFeed.style.display = 'none';
    }
}

function getLastCustomersOnLoad(){
    fetch('/api/get_last_customers', {
        method:'POST',
        headers:{
            'Content-Type':'application/json'
        },
        body: JSON.stringify({ count:5 })
    })
    .then(res=>res.json())
    .then(response=>{
        const container=document.querySelector('.last-customers');
        container.innerHTML='';

        response.customers.forEach(customer=>{
            const div=document.createElement('div');
            div.className='customer-item';
            div.id='lastLoginCustomer'+customer.name;
            div.innerHTML=`
                <img src="data:image/jpeg;base64,${customer.image}" alt="${customer.name}" />
                <div class="last-user-info">
                    <p><b>${customer.name}</b></p>
                    <p>${customer.last_login_date}</p>
                </div>
            `;
            container.appendChild(div);
        });
    });
}

function addRecognizedCustomerToLastCustomers(name, image, last_login_date){
    const container = document.querySelector('.last-customers');

    if(document.getElementById('lastLoginCustomer' + name)){
        container.removeChild(document.getElementById('lastLoginCustomer' + name));
    }

    const div = document.createElement('div');
    div.className='customer-item';
    div.id='lastLoginCustomer'+name;
    div.innerHTML=`
        <img src="data:image/jpeg;base64,${image}" alt="${name}" />
        <div class="last-user-info">
            <p><b>${name}</b></p>
            <p>${last_login_date}</p>
        </div>
    `;
    container.insertBefore(div, container.firstChild);
}


document.addEventListener("DOMContentLoaded", (event) => { 
    let camValue = localStorage.getItem('cam_number');
    if(camValue == 0 || camValue == 1 || camValue == 2 || camValue == 3 || camValue == 4 || camValue == 5){
        console.log("set cam", camValue);
        document.getElementById(`cam${localStorage.getItem('cam_number')}`).click();
    }else if(!camValue){
        console.log("no cam selected, set to 0");
        document.getElementById(`cam0`).click();
    }else{
        console.log("ip cam entered", camValue);
        fetch('/api/cam_changed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ cam_number: camValue })
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
        })
        .catch(error => {
            console.error('Hata:', error);
        });
        document.getElementById(`camCustom`).checked = true
    }

    // setupAutocomplete('food-input', 'food-results', foods);
    // setupAutocomplete('drink-input', 'drink-results', drinks);

    getLastCustomersOnLoad();
    getProducts();
    listProducts();
});

