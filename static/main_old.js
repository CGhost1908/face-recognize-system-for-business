
let customer_id = null;

function startRecognition() {
    eel.recognize_face()(function(response) {
        
    });
}

function registerUser() {
    let name = prompt("Yeni kullanıcının adını girin:");
    if (name) {
        eel.register_user(name)(function(response) {
            alert(response);
        });
    }
}


function orderFood() {
    const checkedBoxes = document.querySelectorAll('.items input[type="checkbox"]:checked');
    const values = Array.from(checkedBoxes).map(cb => cb.value);

    let total = 0;
    checkedBoxes.forEach(cb => {
        const price = parseFloat(cb.getAttribute('price')) || 0;
        total += price;
    });

    const weather = document.querySelector("#weather2").value;
    const temperature = document.querySelector("#temperature2").value;
    const meal = document.querySelector("#meal2").value;

    eel.order_food(customer_id, values, total)(function(response) {
        alert(`Toplam fiyat: ${total} TL`);
    });

    showOrderHistory();

    eel.update_order_history(customer_id)
}


function showFoodPercentage(customer_id) {
  eel.get_food_percentage(customer_id)(function(response) {
    const container = document.querySelector('.percentage');
    container.innerHTML = ''; 

    for (const [food, percent] of Object.entries(response)) {
      const p = document.createElement('p');
      p.textContent = `${food}: %${percent}`;
      container.appendChild(p);
    }
  });
}




eel.expose(update_recognized_user);
function update_recognized_user(name, id, image) {
    customer_id = id;

    document.getElementById("recognized-name").innerText = "Hoşgeldin " + name;
    // document.querySelector(".suggest-food-button").style.display = "block";

    document.querySelector(".suggest-food-button").removeAttribute("disabled");
    document.querySelector(".siparis-girisi").removeAttribute("disabled");

    document.querySelector(".user-text").style.display = "block";

    document.querySelector(".user nav").style.display = "flex";

    let imageElement = document.getElementById("recognized-image");
    imageElement.src = "data:image/jpeg;base64," + image;
    imageElement.style.display = "block";

    updateTotalSpent();
    showFoodPercentage(customer_id);

}

eel.expose(show_order_history);
function show_order_history(orders) {
    const orderHistory = document.querySelector('.order-history');
    orderHistory.innerHTML = '';
    orderHistory.style.display = 'flex';

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
    
}


function suggestFood() {
    const drink = document.querySelector("#beverage").value;
    const weather = document.querySelector("#weather").value;
    const temperature = document.querySelector("#temperature").value;
    const meal = document.querySelector("#meal").value;
    eel.suggest_food(drink, weather, temperature, meal)(function(response) {
        alert(`Önerilen Yemek: ${response.charAt(0).toUpperCase() + response.slice(1)}!`);
    });

    updateTotalSpent();
}

function updateTotalSpent(){
    eel.get_total_spent(customer_id)(function(response) {
        document.getElementById("total-spent-text").innerText = response;
    });
}