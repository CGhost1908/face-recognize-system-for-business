
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
    const response = await fetch('/save-person', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name: name })
    });
    const result = await response.json();
    if (result.status === 'success') {
      messageDiv.textContent = result.message;
      messageDiv.className = 'success';
      nameInput.value = '';
    } else {
      messageDiv.textContent = result.message;
      messageDiv.className = 'error';
    }
  } catch (error) {
    messageDiv.textContent = 'Sunucuya bağlanırken bir hata oluştu.';
    messageDiv.className = 'error';
    console.error('Hata:', error);
  }
});
