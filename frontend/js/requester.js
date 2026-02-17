/**
 * requester.js — كود خاص بواجهة مقدّم الطلب (index.html)
 * يعتمد على: shared.js
 */

let allRequests = [];
let currentRequestForModal = null;

// ==================== التهيئة ====================

document.addEventListener('DOMContentLoaded', function () {
    checkAuthUI();
    enforceRoleAccess('requester');
    bindNavigationEvents();

    // ربط عداد الإشعارات وزر "تعليم الكل كمقروء"
    const markBtn = document.getElementById('markTopNotificationsRead');
    if (markBtn) markBtn.addEventListener('click', markAllTopNotificationsRead);
});

// ==================== التحقق من المصادقة وعرض الواجهة ====================

function checkAuthUI() {
    const token = getToken();
    const user = getCurrentUser();
    const logoutBtn = document.getElementById('logoutBtn');
    const loginLink = document.getElementById('loginLink');
    const topBar = document.getElementById('topBar');

    if (token && user.role) {
        if (topBar) topBar.style.display = 'flex';
        if (logoutBtn) logoutBtn.style.display = 'none';
        if (loginLink) loginLink.style.display = 'none';
        document.body.classList.add('has-top-bar');
        updateUserDropdown(user);
        initTopNotifications();
    } else {
        if (topBar) topBar.style.display = 'none';
        if (logoutBtn) logoutBtn.style.display = 'none';
        if (loginLink) loginLink.style.display = 'inline-block';
        document.body.classList.remove('has-top-bar');
        teardownTopNotifications();
    }
}

function updateUserDropdown(user) {
    const roleNames = {
        requester: 'موظف طلبات', manager: 'مدير', finance: 'موظف مالية',
        disbursement: 'موظف صرف', admin: 'مدير النظام', procurement: 'موظف مشتريات',
    };
    const userName = user.full_name || user.name || user.username || 'مستخدم';
    const userRole = roleNames[user.role] || 'موظف';
    const dn = document.getElementById('dropdownUserName');
    const dr = document.getElementById('dropdownUserRole');
    if (dn) dn.textContent = userName;
    if (dr) dr.textContent = userRole;
}

// ==================== التحقق من الصلاحيات ====================

function enforceRoleAccess(requiredRole) {
    const user = getCurrentUser();
    if (!user.role) return;
    if (user.role !== requiredRole) {
        const redirects = {
            admin: 'admin-dashboard.html', manager: 'manager-dashboard.html',
            finance: 'finance-dashboard.html', disbursement: 'disbursement-dashboard.html',
        };
        window.location.href = redirects[user.role] || 'login.html';
    }
}

// ==================== التنقل بين الأقسام ====================

function showApp(appName) {
    document.querySelectorAll('.app-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const el = document.getElementById(appName);
    if (el) el.classList.add('active');
}

function bindNavigationEvents() {
    const trackCard = document.querySelector('[onclick="showApp(\'track-request\')"]');
    if (trackCard) {
        trackCard.addEventListener('click', function () {
            setTimeout(() => {
                if (document.getElementById('track-request') &&
                    document.getElementById('track-request').classList.contains('active')) {
                    loadRequests();
                }
            }, 100);
        });
    }
}

// ==================== قائمة المستخدم ====================

function toggleUserMenu() {
    const dropdown = document.getElementById('userDropdown');
    if (dropdown) dropdown.classList.toggle('open');
}

document.addEventListener('click', function (event) {
    const dropdown = document.getElementById('userDropdown');
    if (!dropdown || !dropdown.classList.contains('open')) return;
    const btn = dropdown.querySelector('.user-menu-btn');
    const menu = dropdown.querySelector('.dropdown-menu');
    if (btn && menu && !btn.contains(event.target) && !menu.contains(event.target)) {
        dropdown.classList.remove('open');
    }
});

// ==================== إشعارات خاصة بمقدم الطلب ====================

function showNotification(message, type = 'success') {
    const n = document.getElementById('notification');
    if (!n) return;
    n.textContent = message;
    n.className = `notification ${type}`;
    n.classList.add('show');
    setTimeout(() => n.classList.remove('show'), 3000);
}

let topNotifications = [];
let topNotificationsIntervalId = null;
let topNotificationsInitialized = false;

function initTopNotifications() {
    const btn = document.getElementById('topNotificationsBtn');
    const badge = document.getElementById('topNotificationsBadge');
    const panel = document.getElementById('topNotificationsPanel');
    if (!btn || !badge || !panel) return;

    if (topNotificationsInitialized) {
        if (topNotificationsIntervalId) clearInterval(topNotificationsIntervalId);
        loadTopNotifications(true);
        topNotificationsIntervalId = setInterval(() => loadTopNotifications(true), 60000);
        return;
    }

    // لا نضيف addEventListener هنا — onclick في HTML يتكفل بذلك
    // btn.addEventListener('click', toggleTopNotificationsPanel);
    document.addEventListener('click', handleTopNotificationsOutsideClick);
    topNotificationsInitialized = true;

    loadTopNotifications(true);
    topNotificationsIntervalId = setInterval(() => loadTopNotifications(true), 60000);
}

function teardownTopNotifications() {
    topNotifications = [];
    if (topNotificationsIntervalId) { clearInterval(topNotificationsIntervalId); topNotificationsIntervalId = null; }
    const badge = document.getElementById('topNotificationsBadge');
    const panel = document.getElementById('topNotificationsPanel');
    const list = document.getElementById('topNotificationsList');
    if (badge) { badge.style.display = 'none'; badge.textContent = '0'; }
    if (panel) { panel.classList.remove('active'); panel.style.display = 'none'; }
    if (list) list.innerHTML = '<li class="top-notifications-empty">لا توجد إشعارات حالياً.</li>';
}

async function loadTopNotifications(silent = false) {
    const token = getToken();
    if (!token) return;
    try {
        const res = await apiFetch('/notifications');
        if (!res.ok) return;
        const data = await res.json();
        topNotifications = Array.isArray(data) ? data : [];
        renderTopNotifications();
    } catch (error) {
        if (!silent) console.warn('خطأ أثناء جلب الإشعارات:', error);
    }
}

function renderTopNotifications() {
    const badge = document.getElementById('topNotificationsBadge');
    const list = document.getElementById('topNotificationsList');
    if (!badge || !list) return;

    const unreadCount = topNotifications.filter(n => !n.is_read).length;
    badge.textContent = unreadCount;
    badge.style.display = unreadCount > 0 ? 'inline-flex' : 'none';

    if (!topNotifications.length) {
        list.innerHTML = '<li class="top-notifications-empty">لا توجد إشعارات حالياً.</li>';
        return;
    }

    list.innerHTML = topNotifications.map(notif => {
        const createdAt = notif.created_at ? new Date(notif.created_at).toLocaleString('ar-SA') : '';
        const noteLine = notif.note ? `<small>ملاحظة: ${notif.note}</small>` : '';
        return `<li class="${notif.is_read ? '' : 'unread'}">
            <div>${notif.title || 'إشعار'}</div>
            <div>${notif.message || ''}</div>
            ${noteLine}
            <small>${createdAt}</small>
        </li>`;
    }).join('');
}

function toggleTopNotificationsPanel() {
    const panel = document.getElementById('topNotificationsPanel');
    if (!panel) return;
    const willOpen = !panel.classList.contains('active');
    panel.classList.toggle('active');
    panel.style.display = willOpen ? 'flex' : 'none';
    if (willOpen) loadTopNotifications(true);
}

function handleTopNotificationsOutsideClick(event) {
    const panel = document.getElementById('topNotificationsPanel');
    const btn = document.getElementById('topNotificationsBtn');
    if (!panel || !btn) return;
    if (!panel.contains(event.target) && !btn.contains(event.target)) {
        panel.classList.remove('active');
        panel.style.display = 'none';
    }
}

async function markAllTopNotificationsRead() {
    const token = getToken();
    if (!token) return;
    try {
        const res = await fetch(`${API_BASE}/notifications/read-all`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) await loadTopNotifications(true);
    } catch (error) {
        console.warn('تعذر تعليم الإشعارات كمقروءة:', error);
    }
}

// ==================== تحميل وعرض الطلبات ====================

function loadRequests() {
    const token = getToken();
    const user = getCurrentUser();

    if (!token || !user.id) {
        showNotification('يجب تسجيل الدخول أولاً', 'error');
        return;
    }

    const tbody = document.getElementById('requestsTableBody');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:#666;">جاري تحميل طلباتك...</td></tr>';

    fetch(`${API_BASE}/user/requests`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    })
        .then(response => {
            if (response.status === 401) {
                showNotification('انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى', 'error');
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = 'login.html';
                return;
            }
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json'))
                throw new Error('Response is not JSON');
            return response.json();
        })
        .then(data => {
            allRequests = data || [];
            displayRequests(allRequests);
            showNotification(`تم تحميل ${allRequests.length} من طلباتك`, 'success');
        })
        .catch(error => {
            console.error('Error loading requests:', error);
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:#e74c3c;">خطأ في تحميل طلباتك: ' + error.message + '</td></tr>';
            showNotification('خطأ في تحميل طلباتك: ' + error.message, 'error');
        });
}

function displayRequests(requests) {
    const tbody = document.getElementById('requestsTableBody');
    if (requests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:#666;">لا توجد طلبات لك بعد</td></tr>';
        return;
    }

    tbody.innerHTML = requests.map(request => {
        const statusClass = getStatusClass(request.status);
        const stageText = getStageText(request.current_stage, request.status);

        let createdDate = 'غير محدد';
        if (request.created_at) {
            createdDate = new Date(request.created_at).toLocaleDateString('en-GB', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }

        const currency = request.currency || 'SYP';
        const currencySymbol = (currency === 'USD' || currency === 'دولار') ? '$' : 'ل.س';

        return `
            <tr>
                <td>${request.order_number || 'غير محدد'}</td>
                <td>${request.requester || 'غير محدد'}</td>
                <td>${request.department || 'غير محدد'}</td>
                <td>${request.total_amount ? `${request.total_amount} ${currencySymbol}` : 'غير محدد'}</td>
                <td>${createdDate}</td>
                <td><span class="status-badge ${statusClass}">${stageText}</span></td>
                <td>
                    <button class="action-btn" onclick="viewRequest(${request.id})">عرض</button>
                    ${(request.status === 'approved' || request.status === 'completed' || request.status === 'pending_procurement')
                ? `<button class="action-btn" onclick="printRequest(${request.id})">طباعة</button>` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

function getStageText(stage, status) {
    switch (stage) {
        case 'manager': return 'مرحلة المدير المباشر';
        case 'finance': return 'مرحلة المالية';
        case 'disbursement': return 'مرحلة أمر الصرف';
        case 'procurement': return 'مرحلة المشتريات';
    }
    return getStatusText(status);
}

function filterRequests() {
    const statusFilter = document.getElementById('statusFilter').value;
    const orderNumberFilter = document.getElementById('orderNumberFilter').value.toLowerCase();

    let filtered = allRequests;
    if (statusFilter) filtered = filtered.filter(r => r.status === statusFilter);
    if (orderNumberFilter) filtered = filtered.filter(r => (r.order_number || '').toLowerCase().includes(orderNumberFilter));
    displayRequests(filtered);
}

// ==================== عرض تفاصيل الطلب ====================

async function viewRequest(requestId) {
    try {
        const res = await apiFetch(`/requests/${requestId}`);
        if (!res.ok) { showNotification('فشل في جلب تفاصيل الطلب', 'error'); return; }
        const request = await res.json();
        currentRequestForModal = request;
        showRequestModal(request);
    } catch (error) {
        console.error('خطأ في جلب تفاصيل الطلب:', error);
        showNotification('حدث خطأ في جلب تفاصيل الطلب', 'error');
    }
}

function showRequestModal(request) {
    const modal = document.getElementById('requestModal');
    const modalBody = document.getElementById('modalBody');
    const formattedTotal = formatCurrency(request.total_amount, request.currency);
    const createdDate = request.created_at
        ? new Date(request.created_at).toLocaleDateString('en-US')
        : (request.date ? new Date(request.date).toLocaleDateString('en-US') : 'غير محدد');

    let itemsTable = '';
    if (request.items && request.items.length > 0) {
        itemsTable = `
            <h3>الأصناف المطلوبة</h3>
            <table class="items-table">
                <thead><tr><th>اسم الصنف</th><th>الوحدة</th><th>الكمية</th><th>السعر</th><th>المجموع</th></tr></thead>
                <tbody>
                    ${request.items.map(item => `
                        <tr>
                            <td>${item.item_name || item.name || 'غير محدد'}</td>
                            <td>${item.unit || 'غير محدد'}</td>
                            <td>${item.quantity || 0}</td>
                            <td>${item.price || 0}</td>
                            <td>${item.total || ((item.quantity || 0) * (item.price || 0))}</td>
                        </tr>
                        ${item.specification ? `<tr><td colspan="5" style="font-style:italic;color:#666;">المواصفات: ${item.specification}</td></tr>` : ''}
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    modalBody.innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><span class="detail-label">رقم الطلب</span><span class="detail-value">${request.order_number || request.id}</span></div>
            <div class="detail-item"><span class="detail-label">مقدم الطلب</span><span class="detail-value">${request.requester || 'غير محدد'}</span></div>
            <div class="detail-item"><span class="detail-label">القسم</span><span class="detail-value">${request.department || 'غير محدد'}</span></div>
            <div class="detail-item"><span class="detail-label">تاريخ الطلب</span><span class="detail-value">${createdDate}</span></div>
            <div class="detail-item"><span class="detail-label">موعد التسليم</span><span class="detail-value">${request.delivery_date || 'غير محدد'}</span></div>
            <div class="detail-item"><span class="detail-label">عنوان التسليم</span><span class="detail-value">${request.delivery_address || 'غير محدد'}</span></div>
            <div class="detail-item"><span class="detail-label">كود المشروع</span><span class="detail-value">${request.project_code || 'غير محدد'}</span></div>
            <div class="detail-item"><span class="detail-label">العملة</span><span class="detail-value">${request.currency || 'ل.س'}</span></div>
            <div class="detail-item"><span class="detail-label">المبلغ الإجمالي</span><span class="detail-value">${formattedTotal}</span></div>
            <div class="detail-item"><span class="detail-label">الحالة</span><span class="detail-value">${getStatusText(request.status)}</span></div>
        </div>
        ${itemsTable}
    `;

    // إخفاء/إظهار زر الطباعة حسب حالة الطلب
    const printBtn = modal.querySelector('.btn-primary');
    if (printBtn) {
        const canPrint = request.status === 'approved' || request.status === 'completed' || request.status === 'pending_procurement';
        printBtn.style.display = canPrint ? 'inline-block' : 'none';
    }

    modal.style.display = 'flex';
}

function closeRequestModal() {
    document.getElementById('requestModal').style.display = 'none';
    currentRequestForModal = null;
}

// ==================== الطباعة ====================

function printCurrentRequest() {
    if (!currentRequestForModal) return;
    const request = currentRequestForModal;
    const signatures = request.signatures || {};
    const approval = request.approval_data || {};
    const approvalDates = request.approval_dates || {};

    // بناء جدول الأصناف
    let itemsTable = '';
    if (request.items && request.items.length > 0) {
        itemsTable = request.items.map(item => `
            <tr>
                <td>${item.item_name || item.name || ''}</td>
                <td>${item.unit || ''}</td>
                <td>${item.quantity || 0}</td>
                <td>${item.price || 0}</td>
                <td>${item.total || ((item.quantity || 0) * (item.price || 0))}</td>
            </tr>
            ${item.specification ? `<tr><td colspan="5" style="font-style:italic;color:#666;padding:5px;">المواصفات: ${item.specification}</td></tr>` : ''}
        `).join('');
    }

    const sigCell = (role) => {
        const sig = signatures[role];
        if (sig) return `<div style="text-align:center;padding:5px;"><img src="${sig}" style="max-width:100%;max-height:60px;object-fit:contain;border:1px solid #ddd;border-radius:4px;"></div>`;
        return '<div style="text-align:center;color:#999;font-size:11px;">لا يوجد توقيع</div>';
    };

    const fmtDate = (dateStr) => {
        if (!dateStr) return '';
        try {
            if (typeof dateStr === 'string' && dateStr.includes('T')) {
                return new Date(dateStr).toLocaleDateString('en-GB', { year: 'numeric', month: '2-digit', day: '2-digit' });
            }
            if (typeof dateStr === 'string' && dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
                const [y, m, d] = dateStr.split('-');
                return `${d}/${m}/${y}`;
            }
            return dateStr;
        } catch { return dateStr; }
    };

    const approvalTable = `
        <tr>
            <td class="approval-label">الاسم</td>
            <td><input type="text" class="approval-input" value="${approval.requester_name || request.requester || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.manager_name || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.finance_name || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.disbursement_name || ''}" readonly></td>
        </tr>
        <tr>
            <td class="approval-label">المنصب</td>
            <td><input type="text" class="approval-input" value="${approval.requester_position || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.manager_position || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.finance_position || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${approval.disbursement_position || ''}" readonly></td>
        </tr>
        <tr>
            <td class="approval-label">التاريخ</td>
            <td><input type="text" class="approval-input" value="${fmtDate(approvalDates.requester) || fmtDate(approval.requester_date) || (request.created_at ? new Date(request.created_at).toLocaleDateString('en-GB') : '')}" readonly></td>
            <td><input type="text" class="approval-input" value="${fmtDate(approvalDates.manager) || fmtDate(approval.manager_date) || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${fmtDate(approvalDates.finance) || fmtDate(approval.finance_date) || ''}" readonly></td>
            <td><input type="text" class="approval-input" value="${fmtDate(approvalDates.disbursement) || fmtDate(approval.disbursement_date) || ''}" readonly></td>
        </tr>
        <tr class="signature-row">
            <td class="approval-label">التوقيع</td>
            <td class="signature-cell"></td>
            <td class="signature-cell">${sigCell('manager')}</td>
            <td class="signature-cell">${sigCell('finance')}</td>
            <td class="signature-cell">${sigCell('disbursement')}</td>
        </tr>
    `;

    const baseUrl = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1);

    const printContent = `
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>طلب شراء</title>
    <link rel="stylesheet" href="${baseUrl}css/fonts.css">
    <link rel="stylesheet" href="${baseUrl}css/style.css" />
</head>
<body>
    <div class="document-container">
        <div><div class="sarh">صرح القابضة</div><div class="sarh">Sarh Holding</div></div>
        <div class="main-title">طلب شراء - Purchase Request</div>

        <div class="header">
            <div class="supplier-info">
                <div class="info-row"><span class="info-label">مقدم الطلب:</span><input type="text" class="info-input" value="${request.requester || ''}" readonly></div>
                <div class="info-row"><span class="info-label">القسم الطالب:</span><input type="text" class="info-input" value="${request.department || ''}" readonly></div>
                <div class="info-row"><span class="info-label">عنوان التسليم:</span><input type="text" class="info-input" value="${request.delivery_address || ''}" readonly></div>
                <div class="info-row"><span class="info-label">موعد التسليم:</span><input type="date" class="info-input" value="${request.delivery_date || ''}" readonly></div>
            </div>
            <div class="company-info">
                <div class="info-row"><span class="info-label">تاريخ طلب الشراء:</span><input type="date" class="info-input" value="${request.date || (request.created_at ? new Date(request.created_at).toISOString().split('T')[0] : '')}" readonly></div>
                <div class="info-row"><span class="info-label">رمز طلب الشراء:</span><input type="text" class="info-input" value="${request.order_number || request.id}" readonly></div>
                <div class="info-row"><span class="info-label">كود المشروع:</span><input type="text" class="info-input" value="${request.project_code || ''}" readonly></div>
                <div class="info-row"><span class="info-label">العملة:</span>
                    <select class="currency-select" readonly>
                        <option value="SYP" ${request.currency === 'SYP' ? 'selected' : ''}>ليرة سورية</option>
                        <option value="USD" ${request.currency === 'USD' ? 'selected' : ''}>دولار أمريكي</option>
                        <option value="EUR" ${request.currency === 'EUR' ? 'selected' : ''}>يورو</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="table-section">
            <div class="section-title">الأصناف المطلوبة</div>
            <table class="items-table">
                <thead><tr><th>اسم الصنف</th><th>الوحدة</th><th>الكمية</th><th>السعر</th><th>المجموع</th></tr></thead>
                <tbody>${itemsTable}</tbody>
                <tfoot><tr><td colspan="4" class="total-label">المجموع الإجمالي:</td><td class="total-amount">${formatCurrency(request.total_amount, request.currency)}</td></tr></tfoot>
            </table>
        </div>

        <div class="approval-section">
            <div class="section-title">جدول الموافقات</div>
            <table class="approval-table">
                <thead><tr><th style="width:12%">#</th><th style="width:14%">الطالب</th><th style="width:16%">المدير المباشر</th><th style="width:16%">الإدارة المالية</th><th style="width:14%">أمر الصرف</th></tr></thead>
                <tbody>${approvalTable}</tbody>
            </table>
        </div>
    </div>
</body>
</html>`;

    const printWindow = window.open('', '_blank');
    printWindow.document.write(printContent);
    printWindow.document.close();

    printWindow.onload = function () {
        const images = printWindow.document.querySelectorAll('img');
        let imagesToLoad = images.length;
        const doPrint = () => { setTimeout(() => printWindow.print(), 300); };
        if (imagesToLoad === 0) { doPrint(); return; }
        images.forEach(img => {
            if (img.complete) { imagesToLoad--; if (imagesToLoad === 0) doPrint(); }
            else { img.onload = img.onerror = () => { imagesToLoad--; if (imagesToLoad === 0) doPrint(); }; }
        });
        setTimeout(doPrint, 2000);
    };
}

function printRequest(requestId) {
    viewRequest(requestId);
    setTimeout(() => printCurrentRequest(), 500);
}

// ==================== تسجيل خروج مخصص ====================

function showCustomConfirm(message, onConfirm) {
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:10000;backdrop-filter:blur(5px)';
    const content = document.createElement('div');
    content.style.cssText = 'background:#fff;padding:30px;border-radius:15px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.3);max-width:400px;margin:20px;';
    content.innerHTML = `<h3 style="margin-bottom:20px;color:#698163;font-size:24px;">${message}</h3>
        <div style="display:flex;gap:15px;justify-content:center;">
            <button id="confirmBtn" style="background:linear-gradient(135deg,#e74c3c,#c0392b);color:#fff;border:none;padding:12px 25px;border-radius:8px;cursor:pointer;font-size:16px;font-weight:bold;">نعم، تسجيل الخروج</button>
            <button id="cancelBtn" style="background:linear-gradient(135deg,#95a5a6,#7f8c8d);color:#fff;border:none;padding:12px 25px;border-radius:8px;cursor:pointer;font-size:16px;font-weight:bold;">إلغاء</button>
        </div>`;
    modal.appendChild(content);
    document.body.appendChild(modal);
    document.getElementById('confirmBtn').onclick = () => { document.body.removeChild(modal); if (onConfirm) onConfirm(); };
    document.getElementById('cancelBtn').onclick = () => document.body.removeChild(modal);
    modal.onclick = (e) => { if (e.target === modal) document.body.removeChild(modal); };
}

// Override logout from shared.js for this page's custom UX
function logout() {
    showCustomConfirm('هل أنت متأكد من تسجيل الخروج؟', function () {
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.innerHTML = '🚪 جاري تسجيل الخروج... <span class="loading-spinner"></span>';
            logoutBtn.disabled = true;
        }
        teardownTopNotifications();
        setTimeout(() => {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            showNotification('تم تسجيل الخروج بنجاح', 'success');
            setTimeout(() => window.location.reload(), 1500);
        }, 1000);
    });
}

// ==================== الحركة الأولية ====================

document.body.style.opacity = '0';
document.body.style.transition = 'opacity 0.5s ease-out';
setTimeout(() => { document.body.style.opacity = '1'; }, 100);
