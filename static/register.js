
const nameInput = document.getElementById('nameInput');
const captureBtn = document.getElementById('captureBtn');
const messageDiv = document.getElementById('message');
captureBtn.addEventListener('click', async () => {
  const name = nameInput.value.trim();
  if (name === '') {
    messageDiv.textContent = 'Lütfen bir isim girin.';
    messageDiv.className = 'error';
    return;
  }
  messageDiv.textContent = 'İşleniyor...';
  messageDiv.className = '';
  try {
    document.body.style.background = '#fff';
    document.body.style.color = '#000';
    
    const response = await fetch('/save-person', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name: name })
    });
    const result = await response.json();
    if (result.status === 'success') {
      document.body.style.background = '';
      document.body.style.color = '';
      messageDiv.textContent = result.message;
      messageDiv.className = 'success';
      nameInput.value = '';
    } else {
      document.body.style.background = '';
      document.body.style.color = '';
      messageDiv.textContent = result.message;
      messageDiv.className = 'error';
    }
  } catch (error) {
    document.body.style.background = '';
    document.body.style.color = '';
    messageDiv.textContent = 'Sunucuya bağlanırken bir hata oluştu.';
    messageDiv.className = 'error';
    console.error('Hata:', error);
  }
});


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
