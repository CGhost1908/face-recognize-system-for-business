/**
 * Login System Frontend
 * Handles user authentication and UI interactions
 */

class LoginManager {
    constructor() {
        this.form = document.getElementById('loginForm');
        this.usernameInput = document.getElementById('username');
        this.passwordInput = document.getElementById('password');
        this.rememberMeCheckbox = document.getElementById('rememberMe');
        this.togglePasswordBtn = document.getElementById('togglePassword');
        this.loginBtn = document.getElementById('loginBtn');
        this.spinner = document.getElementById('spinner');

        this.init();
    }

    init() {
        this.attachEventListeners();
        this.restoreSavedUsername();
        this.setupAlerts();
    }

    attachEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleLogin(e));

        // Toggle password visibility
        this.togglePasswordBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.togglePasswordVisibility();
        });

        // Real-time validation
        this.usernameInput.addEventListener('blur', () => this.validateUsername());
        this.passwordInput.addEventListener('blur', () => this.validatePassword());

        // Forgot password
        document.getElementById('forgotPassword').addEventListener('click', (e) => {
            e.preventDefault();
            this.openForgotPasswordModal();
        });

        // Modal close button
        const closeBtn = document.querySelector('.close');
        closeBtn.addEventListener('click', () => this.closeForgotPasswordModal());

        // Forgot password form
        const forgotForm = document.getElementById('forgotPasswordForm');
        forgotForm.addEventListener('submit', (e) => this.handleForgotPassword(e));

        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            const modal = document.getElementById('forgotPasswordModal');
            if (e.target === modal) {
                this.closeForgotPasswordModal();
            }
        });

        // Clear error messages on input
        this.usernameInput.addEventListener('input', () => {
            this.clearErrorMessage('usernameError');
        });
        this.passwordInput.addEventListener('input', () => {
            this.clearErrorMessage('passwordError');
        });
    }

    setupAlerts() {
        // Check for query parameters indicating redirect from other pages
        const params = new URLSearchParams(window.location.search);
        if (params.get('session_expired')) {
            this.showAlert('Oturumunuz sona erdi. Lütfen tekrar giriş yapın.', 'info');
        }
        if (params.get('unauthorized')) {
            this.showAlert('Bu sayfaya erişim yetkiniz yok. Admin paneline giriş yapın.', 'error');
        }
    }

    togglePasswordVisibility() {
        const type = this.passwordInput.type === 'password' ? 'text' : 'password';
        this.passwordInput.type = type;
        
        // Update icon
        const eyeIcon = this.togglePasswordBtn.querySelector('.eye-icon');
        eyeIcon.textContent = type === 'password' ? '👁️' : '👁️‍🗨️';
    }

    validateUsername() {
        const username = this.usernameInput.value.trim();
        const errorElement = document.getElementById('usernameError');

        if (!username) {
            this.showFieldError('usernameError', 'Kullanıcı adı gereklidir');
            return false;
        }

        if (username.length < 3) {
            this.showFieldError('usernameError', 'Kullanıcı adı en az 3 karakter olmalıdır');
            return false;
        }

        if (!/^[a-zA-Z0-9_]*$/.test(username)) {
            this.showFieldError('usernameError', 'Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir');
            return false;
        }

        this.clearErrorMessage('usernameError');
        return true;
    }

    validatePassword() {
        const password = this.passwordInput.value;
        const errorElement = document.getElementById('passwordError');

        if (!password) {
            this.showFieldError('passwordError', 'Şifre gereklidir');
            return false;
        }

        if (password.length < 6) {
            this.showFieldError('passwordError', 'Şifre en az 6 karakter olmalıdır');
            return false;
        }

        this.clearErrorMessage('passwordError');
        return true;
    }

    showFieldError(elementId, message) {
        const element = document.getElementById(elementId);
        element.textContent = message;
        element.classList.add('show');

        // Add error class to input
        const inputId = elementId.replace('Error', '');
        const input = document.getElementById(inputId);
        if (input) {
            input.parentElement.classList.add('error');
        }
    }

    clearErrorMessage(elementId) {
        const element = document.getElementById(elementId);
        element.textContent = '';
        element.classList.remove('show');

        // Remove error class from input
        const inputId = elementId.replace('Error', '');
        const input = document.getElementById(inputId);
        if (input) {
            input.parentElement.classList.remove('error');
        }
    }

    async handleLogin(e) {
        e.preventDefault();

        // Validate inputs
        const isUsernameValid = this.validateUsername();
        const isPasswordValid = this.validatePassword();

        if (!isUsernameValid || !isPasswordValid) {
            return;
        }

        // Disable button and show spinner
        this.setLoginButtonLoading(true);

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: this.usernameInput.value.trim(),
                    password: this.passwordInput.value,
                    remember_me: this.rememberMeCheckbox.checked
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Save username if remember me is checked
                if (this.rememberMeCheckbox.checked) {
                    localStorage.setItem('saved_username', this.usernameInput.value.trim());
                } else {
                    localStorage.removeItem('saved_username');
                }

                // Save session token if provided
                if (data.token) {
                    sessionStorage.setItem('auth_token', data.token);
                }

                this.showAlert('Giriş başarılı! Yönlendiriliyorsunuz...', 'success');
                
                // Redirect after showing message
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                this.showAlert(data.message || 'Giriş başarısız. Kullanıcı adı veya şifreyi kontrol edin.', 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showAlert('Bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'error');
        } finally {
            this.setLoginButtonLoading(false);
        }
    }

    async handleForgotPassword(e) {
        e.preventDefault();

        const email = document.getElementById('resetEmail').value.trim();

        if (!email) {
            this.showAlert('E-posta adresi gereklidir.', 'error');
            return;
        }

        try {
            const response = await fetch('/api/forgot-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email })
            });

            const data = await response.json();

            if (response.ok) {
                this.showAlert('Şifre sıfırla bağlantısı e-posta adresinize gönderildi.', 'success');
                this.closeForgotPasswordModal();
                document.getElementById('forgotPasswordForm').reset();
            } else {
                this.showAlert(data.message || 'Bir hata oluştu.', 'error');
            }
        } catch (error) {
            console.error('Forgot password error:', error);
            this.showAlert('Bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'error');
        }
    }

    setLoginButtonLoading(isLoading) {
        this.loginBtn.disabled = isLoading;
        this.spinner.style.display = isLoading ? 'block' : 'none';
    }

    restoreSavedUsername() {
        const savedUsername = localStorage.getItem('saved_username');
        if (savedUsername) {
            this.usernameInput.value = savedUsername;
            this.rememberMeCheckbox.checked = true;
        }
    }

    showAlert(message, type = 'info') {
        let alertElement, messageElement;

        if (type === 'error') {
            alertElement = document.getElementById('errorAlert');
            messageElement = document.getElementById('errorMessage');
        } else if (type === 'success') {
            alertElement = document.getElementById('successAlert');
            messageElement = document.getElementById('successMessage');
        } else {
            alertElement = document.getElementById('infoAlert');
            messageElement = document.getElementById('alertMessage');
        }

        messageElement.textContent = message;
        alertElement.classList.add('show');

        // Auto-hide after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                alertElement.classList.remove('show');
            }, 5000);
        }
    }

    openForgotPasswordModal() {
        document.getElementById('forgotPasswordModal').classList.add('show');
    }

    closeForgotPasswordModal() {
        document.getElementById('forgotPasswordModal').classList.remove('show');
    }
}

// Initialize login manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});
