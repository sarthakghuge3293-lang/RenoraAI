document.addEventListener('DOMContentLoaded', () => {
    const togglePassword = document.getElementById('togglePassword');
    const password = document.getElementById('password');
    const loginForm = document.getElementById('adminLoginForm');
    const loginBtn = document.getElementById('loginBtn');
    const btnText = loginBtn.querySelector('.btn-text');
    const btnIcon = loginBtn.querySelector('.btn-icon');
    const spinner = document.getElementById('loginSpinner');

    togglePassword.addEventListener('click', function () {
        const type = password.getAttribute('type') === 'password' ? 'text' : 'password';
        password.setAttribute('type', type);
        this.classList.toggle('bi-eye-fill');
        this.classList.toggle('bi-eye-slash-fill');
    });

    loginForm.addEventListener('submit', function() {
        btnText.classList.add('d-none');
        btnIcon.classList.add('d-none');
        spinner.classList.remove('d-none');
        loginBtn.disabled = true;
    });
});
