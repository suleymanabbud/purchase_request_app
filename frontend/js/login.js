/**
 * صفحة تسجيل الدخول — login.js
 */

const API_BASE = '/api';

// ──────────────────────────────────────
// خريطة التوجيه حسب الدور
// ──────────────────────────────────────

const ROLE_REDIRECT = {
    admin: 'admin-dashboard.html',
    manager: 'manager-dashboard.html',
    finance: 'finance-dashboard.html',
    disbursement: 'disbursement-dashboard.html',
    procurement: 'procurement-dashboard.html',
    requester: 'index.html',
};

function redirectByRole(role) {
    window.location.href = ROLE_REDIRECT[role] || 'index.html';
}


// ──────────────────────────────────────
// رسائل الحالة
// ──────────────────────────────────────

function showError(message) {
    const el = document.getElementById('errorMessage');
    el.textContent = message;
    el.style.display = 'block';
    document.getElementById('successMessage').style.display = 'none';
}

function showSuccess(message) {
    const el = document.getElementById('successMessage');
    el.textContent = message;
    el.style.display = 'block';
    document.getElementById('errorMessage').style.display = 'none';
}

function hideMessages() {
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('successMessage').style.display = 'none';
}

function setLoading(loading) {
    document.getElementById('loginBtn').disabled = loading;
    document.getElementById('loading').style.display = loading ? 'block' : 'none';
}


// ──────────────────────────────────────
// تسجيل الدخول
// ──────────────────────────────────────

document.getElementById('loginForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    hideMessages();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();

    if (!username || !password) {
        showError('يرجى إدخال اسم المستخدم وكلمة المرور');
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('user', JSON.stringify(data.user));
            showSuccess('تم تسجيل الدخول بنجاح');
            setTimeout(() => redirectByRole(data.user.role), 1000);
        } else {
            showError(data.error || 'خطأ في تسجيل الدخول');
        }
    } catch {
        showError('خطأ في الاتصال بالخادم');
    } finally {
        setLoading(false);
    }
});


// ──────────────────────────────────────
// توجيه تلقائي إذا المستخدم مسجل
// ──────────────────────────────────────

window.addEventListener('load', function () {
    const token = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');

    if (token && userStr) {
        fetch(`${API_BASE}/me`, {
            headers: { Authorization: `Bearer ${token}` },
        })
            .then((res) => {
                if (res.ok) {
                    redirectByRole(JSON.parse(userStr).role);
                }
            })
            .catch(() => {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
            });
    }
});
