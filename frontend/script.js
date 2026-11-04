'use strict';

const API_CONFIG = {
    useMock: false,
    baseUrl: (window.location.origin && window.location.origin.includes(':8000'))
        ? window.location.origin
        : 'http://127.0.0.1:8000',
    loginEndpoint: '/api/v1/auth/login',
    resetEndpoint: '/api/v1/auth/reset-password',
    mockDelayMs: 600,
    storageKey: 'ledger_remembered_username'
};

const DOM = {
    alertBanner: document.getElementById('alertBanner'),
    alertMessage: document.getElementById('alertMessage'),
    alertCloseBtn: document.getElementById('alertCloseBtn'),

    loginForm: document.getElementById('loginForm'),
    usernameInput: document.getElementById('username'),
    passwordInput: document.getElementById('password'),
    usernameError: document.getElementById('usernameError'),
    passwordError: document.getElementById('passwordError'),
    togglePasswordBtn: document.getElementById('togglePassword'),
    rememberMeCheckbox: document.getElementById('rememberMe'),
    submitBtn: document.getElementById('submitBtn'),
    btnQuickDemoLogin: document.getElementById('btnQuickDemoLogin'),

    forgotPasswordLink: document.getElementById('forgotPasswordLink'),
    forgotModal: document.getElementById('forgotModal'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    modalCancelBtn: document.getElementById('modalCancelBtn'),
    resetForm: document.getElementById('resetForm'),
    resetEmailInput: document.getElementById('resetEmail'),
    resetNewPasswordInput: document.getElementById('resetNewPassword'),
    resetEmailError: document.getElementById('resetEmailError'),
    resetPasswordError: document.getElementById('resetPasswordError'),
    modalSubmitBtn: document.getElementById('modalSubmitBtn'),

    currentYear: document.getElementById('currentYear')
};

let isSubmitting = false;
let alertTimeoutId = null;

document.addEventListener('DOMContentLoaded', () => {
    initDynamicYear();
    initRememberedUser();
    attachEventListeners();
});

function initDynamicYear() {
    if (DOM.currentYear) {
        DOM.currentYear.textContent = new Date().getFullYear();
    }
}

function initRememberedUser() {
    try {
        let savedUsername = localStorage.getItem(API_CONFIG.storageKey);
        if (savedUsername) {
            savedUsername = savedUsername.trim().replace(/^['"]+|['"]+$/g, '');
        }
        if (savedUsername && DOM.usernameInput && DOM.rememberMeCheckbox) {
            DOM.usernameInput.value = savedUsername;
            DOM.rememberMeCheckbox.checked = true;

            DOM.passwordInput.focus();
        }
    } catch (err) {
        console.warn('LocalStorage is disabled or restricted in this environment:', err);
    }
}

function attachEventListeners() {
    DOM.loginForm.addEventListener('submit', handleLoginSubmit);

    DOM.togglePasswordBtn.addEventListener('click', togglePasswordVisibility);

    DOM.usernameInput.addEventListener('blur', () => validateUsername(true));
    DOM.usernameInput.addEventListener('input', () => {
        if (DOM.usernameInput.classList.contains('is-invalid')) {
            validateUsername(false);
        }
    });

    DOM.passwordInput.addEventListener('blur', () => validatePassword(true));
    DOM.passwordInput.addEventListener('input', () => {
        if (DOM.passwordInput.classList.contains('is-invalid')) {
            validatePassword(false);
        }
    });

    DOM.alertCloseBtn.addEventListener('click', hideAlertBanner);

    DOM.forgotPasswordLink.addEventListener('click', (e) => {
        e.preventDefault();
        openForgotModal();
    });

    DOM.modalCloseBtn.addEventListener('click', closeForgotModal);
    DOM.modalCancelBtn.addEventListener('click', closeForgotModal);

    DOM.forgotModal.addEventListener('click', (e) => {
        if (e.target === DOM.forgotModal) {
            closeForgotModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !DOM.forgotModal.hasAttribute('hidden')) {
            closeForgotModal();
        }
    });

    if (DOM.btnQuickDemoLogin) {
        DOM.btnQuickDemoLogin.addEventListener('click', () => {
            DOM.usernameInput.value = 'admin123@gmail.com';
            DOM.passwordInput.value = 'admin123';
            clearFieldError(DOM.usernameInput, DOM.usernameError);
            clearFieldError(DOM.passwordInput, DOM.passwordError);
            handleLoginSubmit(new Event('submit'));
        });
    }

    DOM.resetForm.addEventListener('submit', handleResetSubmit);
}

function validateUsername(showError = true) {
    const value = DOM.usernameInput.value.trim();

    if (!value) {
        if (showError) {
            setFieldError(DOM.usernameInput, DOM.usernameError, 'Username or email is required.');
        }
        return false;
    }

    if (value.length < 2) {
        if (showError) {
            setFieldError(DOM.usernameInput, DOM.usernameError, 'Must be at least 2 characters.');
        }
        return false;
    }

    clearFieldError(DOM.usernameInput, DOM.usernameError);
    return true;
}

function validatePassword(showError = true) {
    const value = DOM.passwordInput.value;

    if (!value) {
        if (showError) {
            setFieldError(DOM.passwordInput, DOM.passwordError, 'Password is required.');
        }
        return false;
    }

    clearFieldError(DOM.passwordInput, DOM.passwordError);
    return true;
}

function setFieldError(inputElem, errorElem, message) {
    inputElem.classList.add('is-invalid');
    inputElem.classList.remove('is-valid');
    inputElem.setAttribute('aria-invalid', 'true');
    errorElem.textContent = message;
}

function clearFieldError(inputElem, errorElem) {
    inputElem.classList.remove('is-invalid');
    inputElem.classList.add('is-valid');
    inputElem.setAttribute('aria-invalid', 'false');
    errorElem.textContent = '';
}

function togglePasswordVisibility() {
    const isPassword = DOM.passwordInput.type === 'password';
    DOM.passwordInput.type = isPassword ? 'text' : 'password';

    DOM.togglePasswordBtn.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
    DOM.togglePasswordBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');

    const eyeShow = DOM.togglePasswordBtn.querySelector('.eye-show');
    const eyeHide = DOM.togglePasswordBtn.querySelector('.eye-hide');

    if (eyeShow && eyeHide) {
        eyeShow.style.display = isPassword ? 'none' : 'block';
        eyeHide.style.display = isPassword ? 'block' : 'none';
    }

    DOM.passwordInput.focus();
}

function showAlertBanner(type, message, autoDismissMs = 0) {
    if (alertTimeoutId) {
        clearTimeout(alertTimeoutId);
        alertTimeoutId = null;
    }

    DOM.alertBanner.classList.remove('alert-error', 'alert-success', 'alert-warning');
    DOM.alertBanner.classList.add(`alert-${type}`);
    DOM.alertMessage.textContent = message;
    DOM.alertBanner.removeAttribute('hidden');

    if (autoDismissMs > 0) {
        alertTimeoutId = setTimeout(() => {
            hideAlertBanner();
        }, autoDismissMs);
    }
}

function hideAlertBanner() {
    DOM.alertBanner.setAttribute('hidden', '');
    if (alertTimeoutId) {
        clearTimeout(alertTimeoutId);
        alertTimeoutId = null;
    }
}

async function handleLoginSubmit(event) {
    event.preventDefault();

    if (isSubmitting) return;

    hideAlertBanner();

    const isUsernameValid = validateUsername(true);
    const isPasswordValid = validatePassword(true);

    if (!isUsernameValid || !isPasswordValid) {
        showAlertBanner('error', 'Please resolve the highlighted errors before submitting.');
        return;
    }

    const username = DOM.usernameInput.value.trim();
    const password = DOM.passwordInput.value;
    const rememberMe = DOM.rememberMeCheckbox.checked;

    try {
        if (rememberMe) {
            localStorage.setItem(API_CONFIG.storageKey, username);
        } else {
            localStorage.removeItem(API_CONFIG.storageKey);
        }
    } catch (err) {
        console.warn('LocalStorage error:', err);
    }

    setSubmittingState(true);

    try {
        let loggedIn = false;
        await executeFastAPILogin(username, password);
        loggedIn = true;
    } catch (error) {
        showAlertBanner('error', error.message || 'Authentication failed. Please verify your credentials.');
    } finally {
        setSubmittingState(false);
    }
}

function setSubmittingState(loading) {
    isSubmitting = loading;
    DOM.submitBtn.disabled = loading;
    DOM.usernameInput.disabled = loading;
    DOM.passwordInput.disabled = loading;
    DOM.rememberMeCheckbox.disabled = loading;

    if (loading) {
        DOM.submitBtn.classList.add('is-loading');
    } else {
        DOM.submitBtn.classList.remove('is-loading');
    }
}

const UNIQUE_CREDENTIALS = {
    username: 'admin123@gmail.com',
    role: 'Lead Financial Controller'
};

function simulateMockLogin(username, password) {
    return new Promise((resolve) => {
        showAlertBanner('success', 'Access Granted! Welcome to Ledger Management System. Redirecting to Dashboard...', 3000);
        sessionStorage.setItem('ledger_access_token', 'mock-jwt-token-ledger-admin-xyz');
        setTimeout(() => {
            window.location.href = 'dashboard.html';
            resolve({ success: true, token: 'mock-jwt-token-ledger-admin-xyz' });
        }, 500);
    });
}

async function executeFastAPILogin(username, password) {
    const url = `${API_CONFIG.baseUrl}${API_CONFIG.loginEndpoint}`;

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        },
        body: formData
    });

    const data = await response.json();

    if (!response.ok) {
        const errorDetail = data && (data.detail || data.message) ? data.detail : 'Invalid credentials.';
        throw new Error(errorDetail);
    }

    showAlertBanner('success', 'Sign-in successful! Redirecting to Ledger Dashboard...', 3000);

    if (data.access_token) {
        sessionStorage.setItem('ledger_access_token', data.access_token);
    }
    if (data.user_email) {
        sessionStorage.setItem('ledger_user_email', data.user_email);
    }

    setTimeout(() => {
        window.location.href = 'dashboard.html';
    }, 450);

    return data;
}

function openForgotModal() {
    DOM.resetEmailInput.value = DOM.usernameInput.value.includes('@') ? DOM.usernameInput.value : '';
    DOM.resetEmailError.textContent = '';
    if (DOM.resetPasswordError) DOM.resetPasswordError.textContent = '';
    DOM.resetEmailInput.classList.remove('is-invalid', 'is-valid');
    DOM.forgotModal.removeAttribute('hidden');
    DOM.resetEmailInput.focus();
}

function closeForgotModal() {
    DOM.forgotModal.setAttribute('hidden', '');
    DOM.forgotPasswordLink.focus();
}

async function handleResetSubmit(event) {
    event.preventDefault();
    const email = DOM.resetEmailInput.value.trim();
    const newPassword = DOM.resetNewPasswordInput ? DOM.resetNewPasswordInput.value.trim() : '';

    if (!email) {
        DOM.resetEmailInput.classList.add('is-invalid');
        DOM.resetEmailError.textContent = 'Please enter your username or registered email address.';
        return;
    }

    if (!newPassword) {
        if (DOM.resetPasswordError) DOM.resetPasswordError.textContent = 'Please enter your desired new password.';
        return;
    }

    DOM.resetEmailInput.classList.remove('is-invalid');
    DOM.resetEmailError.textContent = '';
    if (DOM.resetPasswordError) DOM.resetPasswordError.textContent = '';
    DOM.modalSubmitBtn.disabled = true;
    DOM.modalSubmitBtn.classList.add('is-loading');

    try {
        const res = await fetch(`${API_CONFIG.baseUrl}/api/v1/auth/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                new_password: newPassword
            })
        });

        const data = await res.json();
        if (res.ok) {
            closeForgotModal();
            showAlertBanner('success', data.message || 'Password successfully updated! Redirecting to Dashboard...', 5000);
            if (data.access_token) {
                sessionStorage.setItem('ledger_access_token', data.access_token);
            }
            if (data.user_email) {
                sessionStorage.setItem('ledger_user_email', data.user_email);
                try {
                    localStorage.setItem(API_CONFIG.storageKey, data.user_email);
                } catch (e) {}
            }
            DOM.usernameInput.value = data.user_email || email;
            DOM.passwordInput.value = newPassword;
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 500);
        } else {
            throw new Error(data.detail || 'Password reset failed. Please verify credentials.');
        }
    } catch (e) {
        if (DOM.resetEmailError) {
            DOM.resetEmailError.textContent = e.message || 'Failed to reset password.';
        }
    } finally {
        DOM.modalSubmitBtn.disabled = false;
        DOM.modalSubmitBtn.classList.remove('is-loading');
    }
}
