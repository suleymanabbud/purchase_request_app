/**
 * shared.js — الدوال المشتركة بين جميع لوحات التحكم
 * يُستدعى من: manager-dashboard, finance-dashboard, disbursement-dashboard, etc.
 */

const API_BASE = `${window.location.origin}/api`;

// ==================== Auth Helpers ====================

/**
 * جلب التوكن من localStorage
 */
function getToken() {
    return localStorage.getItem('token');
}

/**
 * جلب بيانات المستخدم الحالي
 */
function getCurrentUser() {
    try {
        return JSON.parse(localStorage.getItem('user') || '{}');
    } catch {
        return {};
    }
}

/**
 * التحقق من تسجيل الدخول — redirect إذا غير مسجّل
 */
function requireLogin() {
    const token = getToken();
    const user = getCurrentUser();
    if (!token || !user.username) {
        alert('⚠️ يجب تسجيل الدخول أولاً');
        window.location.href = 'login.html';
        return null;
    }
    window.currentUser = user;
    return user;
}

/**
 * تسجيل الخروج
 */
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}

/**
 * استدعاء API مع توكن
 */
async function apiFetch(endpoint, options = {}) {
    const token = getToken();
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(options.headers || {}),
    };

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
        logout();
        throw new Error('انتهت صلاحية الجلسة');
    }

    return response;
}

// ==================== Status Helpers ====================

/**
 * خريطة ترجمة الحالات
 */
const STATUS_MAP = {
    'pending_manager': 'في انتظار المراجعة',
    'pending_finance': 'تم الموافقة - في انتظار المالية',
    'pending_disbursement': 'تم الموافقة - في انتظار الصرف',
    'pending_procurement': 'في انتظار المشتريات',
    'approved': 'منتهي',
    'completed': 'مكتمل',
    'rejected': 'تم الرفض',
};

/**
 * ترجمة حالة الطلب إلى نص عربي
 */
function getStatusText(status) {
    return STATUS_MAP[status] || status || 'غير محدد';
}

/**
 * تحديد CSS class للحالة
 */
function getStatusClass(status) {
    if (!status) return 'status-pending';
    if (status.includes('pending')) return 'status-pending';
    if (status === 'approved' || status === 'completed') return 'status-approved';
    if (status === 'rejected') return 'status-rejected';
    return 'status-pending';
}

// ==================== Formatting ====================

/**
 * تنسيق المبالغ المالية
 */
function formatCurrency(amount, currency) {
    const num = parseFloat(amount) || 0;
    if (currency === 'USD') {
        return `$${num.toFixed(2)}`;
    }
    return `${num.toLocaleString()} ل.س`;
}

/**
 * تنسيق تاريخ للعرض
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        return new Date(dateStr).toLocaleDateString('ar-SA');
    } catch {
        return dateStr;
    }
}

// ==================== Notifications ====================

let _notifications = [];
let _notificationInterval = null;

/**
 * تحميل الإشعارات
 */
async function loadNotifications() {
    try {
        const res = await apiFetch('/notifications');
        if (!res.ok) return;
        _notifications = await res.json();
        updateNotificationBadge();
        renderNotificationsList();
    } catch (e) {
        console.warn('خطأ في تحميل الإشعارات:', e);
    }
}

/**
 * تحديث عداد الإشعارات
 */
function updateNotificationBadge() {
    const unread = _notifications.filter(n => !n.is_read).length;
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        badge.textContent = unread;
        badge.style.display = unread > 0 ? 'flex' : 'none';
    }
}

/**
 * عرض قائمة الإشعارات داخل البانل
 */
function renderNotificationsList() {
    const list = document.getElementById('notificationsList');
    if (!list) return;

    if (_notifications.length === 0) {
        list.innerHTML = '<li class="notif-empty">🔕 لا توجد إشعارات</li>';
        return;
    }

    list.innerHTML = _notifications.map(n => `
        <li class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}">
            <div class="notif-icon">${n.is_read ? '📭' : '📬'}</div>
            <div class="notif-body">
                <div class="notif-text">${n.message || 'إشعار جديد'}</div>
                <div class="notif-time">${formatDate(n.created_at)}</div>
            </div>
        </li>
    `).join('');

    // الضغط على الإشعار => تعليمه كمقروء
    list.querySelectorAll('.notif-item.unread').forEach(el => {
        el.addEventListener('click', () => {
            const id = parseInt(el.dataset.id);
            markNotificationRead(id);
            el.classList.remove('unread');
            const icon = el.querySelector('.notif-icon');
            if (icon) icon.textContent = '📭';
        });
    });
}

/**
 * تعليم إشعار كمقروء
 */
async function markNotificationRead(id) {
    try {
        await apiFetch(`/notifications/${id}/read`, { method: 'POST' });
        const n = _notifications.find(x => x.id === id);
        if (n) n.is_read = true;
        updateNotificationBadge();
    } catch (e) {
        console.warn('خطأ في تحديث الإشعار:', e);
    }
}

/**
 * تعليم كل الإشعارات كمقروءة
 */
async function markAllNotificationsRead() {
    try {
        await apiFetch('/notifications/read-all', { method: 'POST' });
        _notifications.forEach(n => n.is_read = true);
        updateNotificationBadge();
        renderNotificationsList();
    } catch (e) {
        console.warn('خطأ:', e);
    }
}

/**
 * بدء التحديث التلقائي للإشعارات
 */
function startNotificationPolling(intervalMs = 30000) {
    loadNotifications();
    _notificationInterval = setInterval(loadNotifications, intervalMs);
}

/**
 * إيقاف التحديث التلقائي
 */
function stopNotificationPolling() {
    if (_notificationInterval) {
        clearInterval(_notificationInterval);
        _notificationInterval = null;
    }
}

/**
 * فتح/إغلاق لوحة الإشعارات
 */
function toggleNotificationsPanel() {
    const panel = document.getElementById('notificationsPanel');
    if (!panel) return;
    panel.classList.toggle('open');

    // إغلاق عند النقر خارج البانل
    if (panel.classList.contains('open')) {
        setTimeout(() => {
            document.addEventListener('click', _closeNotifOnOutsideClick);
        }, 10);
    }
}

function _closeNotifOnOutsideClick(e) {
    const panel = document.getElementById('notificationsPanel');
    const bell = document.getElementById('notificationBell');
    if (panel && !panel.contains(e.target) && bell && !bell.contains(e.target)) {
        panel.classList.remove('open');
        document.removeEventListener('click', _closeNotifOnOutsideClick);
    }
}

/**
 * إنشاء عناصر الإشعارات ديناميكياً (زر + بانل)
 */
function _injectNotificationUI() {
    // نستهدف .user-info (الظاهرة دائماً) — لا .top-actions (قد تكون مخفية)
    const container = document.querySelector('.user-info') || document.querySelector('.top-bar');
    if (!container) return;

    // تجنب الحقن المزدوج
    if (document.getElementById('notificationBell')) return;

    // زر الإشعارات — نستخدم emoji لضمان الظهور
    const bell = document.createElement('div');
    bell.id = 'notificationBell';
    bell.className = 'notification-bell';
    bell.innerHTML = `
        <span class="bell-icon">🔔</span>
        <span class="badge" id="notificationBadge" style="display:none;">0</span>
    `;
    bell.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleNotificationsPanel();
    });
    // نضيفه كآخر عنصر — في RTL سيظهر على اليمين (أقرب للمستخدم)
    container.appendChild(bell);

    // لوحة الإشعارات
    const panel = document.createElement('div');
    panel.id = 'notificationsPanel';
    panel.className = 'notifications-panel';
    panel.innerHTML = `
        <div class="notif-panel-header">
            <span>🔔 الإشعارات</span>
            <button class="notif-mark-all" onclick="markAllNotificationsRead()">
                ✓✓ تعليم الكل كمقروء
            </button>
        </div>
        <ul class="notif-list" id="notificationsList">
            <li class="notif-empty">⏳ جاري التحميل...</li>
        </ul>
    `;
    document.body.appendChild(panel);
}

// ==================== Signature Helpers ====================

/**
 * تحميل التوقيع المحفوظ وعرضه
 */
async function loadSavedSignature(previewElementId = 'signaturePreview') {
    try {
        const res = await apiFetch('/my-signature');
        if (!res.ok) return null;
        const data = await res.json();
        if (data.signature) {
            const preview = document.getElementById(previewElementId);
            if (preview) {
                preview.innerHTML = `<img src="${data.signature}" style="max-width:100%;max-height:100%;object-fit:contain" alt="التوقيع">`;
            }
            return data.signature;
        }
        return null;
    } catch (e) {
        console.warn('خطأ في تحميل التوقيع:', e);
        return null;
    }
}

/**
 * حفظ التوقيع
 */
async function saveSignature(signatureData) {
    try {
        const res = await apiFetch('/my-signature', {
            method: 'POST',
            body: JSON.stringify({ signature: signatureData }),
        });
        const data = await res.json();
        if (res.ok) {
            return { success: true, ...data };
        }
        return { success: false, error: data.error };
    } catch (e) {
        return { success: false, error: e.message };
    }
}

// ==================== Initialize ====================

/**
 * تهيئة عامة — تُستدعى من DOMContentLoaded في كل dashboard
 */
function initDashboard() {
    const user = requireLogin();
    if (!user) return null;

    // عرض اسم المستخدم
    const nameEl = document.getElementById('userName');
    if (nameEl) nameEl.textContent = `مرحباً، ${user.full_name || user.username}`;

    const avatarEl = document.getElementById('userAvatar');
    if (avatarEl) avatarEl.textContent = (user.full_name || user.username || 'م').charAt(0);

    // إنشاء عناصر الإشعارات ديناميكياً
    _injectNotificationUI();

    // تحميل التوقيع والإشعارات
    loadSavedSignature();
    startNotificationPolling();

    return user;
}
