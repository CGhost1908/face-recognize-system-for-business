
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


document.addEventListener("DOMContentLoaded", (event) => { 
});
