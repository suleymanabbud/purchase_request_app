/**
 * admin.js — الكود الخاص بلوحة تحكم الإدارة (Admin)
 * يعتمد على: shared.js
 */

let currentRequestId = null;
let allRequests = [];
let filteredRequests = [];

// ==================== التهيئة ====================

document.addEventListener('DOMContentLoaded', function () {
    const user = initDashboard();
    if (!user) return;

    enforceRoleAccess('admin');
    loadRequests();
    loadAccountTypes();

    // فلاتر البحث المباشر
    const ids = ['searchInput', 'statusFilter', 'departmentFilter', 'dateFromFilter', 'dateToFilter'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', applyFilters);
    });

    // عداد حروف الرفض
    const rejectTA = document.getElementById('rejectNoteTextarea');
    if (rejectTA) rejectTA.addEventListener('input', updateRejectCharCount);
});

// ==================== التحقق من الصلاحيات ====================

function enforceRoleAccess(requiredRole) {
    const user = getCurrentUser();
    if (!user.role) return;
    if (user.role !== requiredRole) {
        const redirects = {
            manager: 'manager-dashboard.html',
            finance: 'finance-dashboard.html',
            disbursement: 'disbursement-dashboard.html',
            requester: 'index.html',
        };
        window.location.href = redirects[user.role] || 'login.html';
    }
}

// ==================== تحميل الطلبات ====================

async function loadRequests() {
    try {
        const res = await apiFetch('/requests');
        if (!res.ok) {
            if (res.status === 401) logout();
            return;
        }
        allRequests = await res.json();
        filteredRequests = [...allRequests];
        updateStats();
        renderRequestsTable();
    } catch (error) {
        console.error('Error loading requests:', error);
    }
}

function updateStats() {
    const total = allRequests.length;
    const pending = allRequests.filter(r => {
        const s = r.status || 'pending_manager';
        return s === 'pending_manager' || s === 'pending_finance' || s === 'pending_disbursement';
    }).length;
    const approved = allRequests.filter(r => (r.status || 'pending_manager') === 'approved').length;
    const rejected = allRequests.filter(r => (r.status || 'pending_manager') === 'rejected').length;

    document.getElementById('totalRequests').textContent = total;
    document.getElementById('pendingRequests').textContent = pending;
    document.getElementById('approvedRequests').textContent = approved;
    document.getElementById('rejectedRequests').textContent = rejected;
}

// ==================== عرض الجدول ====================

function renderRequestsTable() {
    const tbody = document.getElementById('requestsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    filteredRequests.forEach(request => {
        const row = document.createElement('tr');
        const status = request.status || 'pending_manager';
        const formattedTotal = formatCurrency(request.total_amount, request.currency);

        row.innerHTML = `
            <td>${request.order_number || request.id}</td>
            <td>${request.requester}</td>
            <td>${request.department}</td>
            <td>${request.date || '-'}</td>
            <td>${formattedTotal}</td>
            <td><span class="status-badge status-${status}">${getStatusText(status)}</span></td>
            <td>
                <button class="action-btn btn-view" onclick="viewRequest(${request.id})">
                    <i class="fas fa-eye"></i> عرض
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// ==================== الفلاتر ====================

function applyFilters() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const status = document.getElementById('statusFilter').value;
    const department = document.getElementById('departmentFilter').value;
    const dateFrom = document.getElementById('dateFromFilter').value;
    const dateTo = document.getElementById('dateToFilter').value;

    filteredRequests = allRequests.filter(request => {
        const matchesSearch = !search ||
            (request.order_number && request.order_number.toLowerCase().includes(search)) ||
            request.requester.toLowerCase().includes(search);
        const requestStatus = request.status || 'pending_manager';
        const matchesStatus = !status || requestStatus === status;
        const matchesDepartment = !department || request.department === department;
        const matchesDateFrom = !dateFrom || (request.date && request.date >= dateFrom);
        const matchesDateTo = !dateTo || (request.date && request.date <= dateTo);
        return matchesSearch && matchesStatus && matchesDepartment && matchesDateFrom && matchesDateTo;
    });

    renderRequestsTable();
}

// ==================== عرض تفاصيل الطلب ====================

async function viewRequest(requestId) {
    const request = allRequests.find(r => r.id === requestId);
    if (!request) return;

    currentRequestId = requestId;
    const formattedTotal = formatCurrency(request.total_amount, request.currency);
    const modalBody = document.getElementById('modalBody');

    modalBody.innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><span class="detail-label">رقم الطلب</span><span class="detail-value">${request.order_number || request.id}</span></div>
            <div class="detail-item"><span class="detail-label">مقدم الطلب</span><span class="detail-value">${request.requester}</span></div>
            <div class="detail-item"><span class="detail-label">القسم</span><span class="detail-value">${request.department}</span></div>
            <div class="detail-item"><span class="detail-label">تاريخ الطلب</span><span class="detail-value">${request.date || '-'}</span></div>
            <div class="detail-item"><span class="detail-label">موعد التسليم</span><span class="detail-value">${request.delivery_date || '-'}</span></div>
            <div class="detail-item"><span class="detail-label">عنوان التسليم</span><span class="detail-value">${request.delivery_address || '-'}</span></div>
            <div class="detail-item"><span class="detail-label">رمز المشروع</span><span class="detail-value">${request.project_code || '-'}</span></div>
            <div class="detail-item"><span class="detail-label">العملة</span><span class="detail-value">${request.currency || '-'}</span></div>
        </div>
        <div class="items-list">
            <h4>قائمة المواد المطلوبة:</h4>
            <table class="items-table-modal">
                <thead><tr>
                    <th>اسم المادة</th><th>المواصفات</th><th>الوحدة</th><th>العدد</th>
                    <th>السعر</th><th>المجموع</th>
                </tr></thead>
                <tbody>
                    ${request.items ? request.items.map(item => `
                        <tr>
                            <td>${item.item_name || '-'}</td>
                            <td>${item.specification || '-'}</td>
                            <td>${item.unit || '-'}</td>
                            <td>${item.quantity || 0}</td>
                            <td>${formatCurrency(item.price || 0, request.currency)}</td>
                            <td>${formatCurrency(item.total || 0, request.currency)}</td>
                        </tr>
                    `).join('') : '<tr><td colspan="6">لا توجد مواد</td></tr>'}
                </tbody>
                <tfoot><tr style="font-weight:bold;background:#f8f9fa;">
                    <td colspan="5">المجموع الكلي</td>
                    <td>${formattedTotal}</td>
                </tr></tfoot>
            </table>
        </div>
    `;

    document.getElementById('requestModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('requestModal').style.display = 'none';
    currentRequestId = null;
}

// ==================== الموافقة / الرفض ====================

function showRejectModal() {
    document.getElementById('rejectModal').style.display = 'block';
    document.getElementById('rejectNoteTextarea').value = '';
    document.getElementById('rejectNoteTextarea').focus();
    updateRejectCharCount();
}

function closeRejectModal() {
    document.getElementById('rejectModal').style.display = 'none';
    document.getElementById('rejectNoteTextarea').value = '';
}

function updateRejectCharCount() {
    const textarea = document.getElementById('rejectNoteTextarea');
    const charCount = document.getElementById('rejectNoteCharCount');
    if (textarea && charCount) {
        const count = textarea.value.length;
        charCount.textContent = count;
        charCount.style.color = count > 500 ? '#e74c3c' : '#7f8c8d';
    }
}

async function confirmReject() {
    const note = document.getElementById('rejectNoteTextarea').value.trim();
    if (!note) { alert('⚠️ يجب إضافة ملاحظة توضح سبب الرفض'); return; }
    if (note.length > 500) { alert('⚠️ الملاحظة طويلة جداً. الحد الأقصى 500 حرف'); return; }
    await updateStatus('reject', note);
    closeRejectModal();
}

async function updateStatus(action, note = '') {
    if (!currentRequestId) return;
    try {
        const res = await apiFetch(`/requests/${currentRequestId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ action, note: note.trim() }),
        });
        if (res.ok) {
            const result = await res.json();
            alert(`تم ${action === 'approve' ? 'الموافقة على' : 'رفض'} الطلب بنجاح`);
            closeModal();
            if (result) {
                if (result.total != null) document.getElementById('totalRequests').textContent = result.total;
                if (result.approved != null) document.getElementById('approvedRequests').textContent = result.approved;
                if (result.rejected != null) document.getElementById('rejectedRequests').textContent = result.rejected;
            }
            await loadRequests();
        } else {
            const error = await res.json();
            alert(`خطأ: ${error.error}`);
        }
    } catch (error) {
        alert('خطأ في تحديث حالة الطلب');
        console.error('Error updating status:', error);
    }
}

async function quickUpdateStatus(requestId, action) {
    if (action === 'reject') {
        currentRequestId = requestId;
        showRejectModal();
        return;
    }
    try {
        const res = await apiFetch(`/requests/${requestId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ action, note: '' }),
        });
        if (res.ok) {
            const result = await res.json();
            alert(`تم ${action === 'approve' ? 'الموافقة على' : 'رفض'} الطلب بنجاح`);
            if (result) {
                if (result.total != null) document.getElementById('totalRequests').textContent = result.total;
                if (result.approved != null) document.getElementById('approvedRequests').textContent = result.approved;
                if (result.rejected != null) document.getElementById('rejectedRequests').textContent = result.rejected;
            }
            await loadRequests();
        } else {
            const error = await res.json();
            alert(`خطأ: ${error.error}`);
        }
    } catch (error) {
        alert('خطأ في تحديث حالة الطلب');
        console.error('Error updating status:', error);
    }
}

// ==================== إدارة أنواع الحسابات ====================

async function loadAccountTypes() {
    try {
        const res = await apiFetch('/account-types');
        if (res.ok) {
            const accountTypes = await res.json();
            displayAccountTypes(accountTypes);
        } else {
            document.getElementById('accountTypesContent').innerHTML =
                '<p style="color: #e74c3c;">خطأ في تحميل أنواع الحسابات</p>';
        }
    } catch (error) {
        console.error('Error loading account types:', error);
        document.getElementById('accountTypesContent').innerHTML =
            '<p style="color: #e74c3c;">خطأ في تحميل أنواع الحسابات</p>';
    }
}

function displayAccountTypes(accountTypes) {
    const content = document.getElementById('accountTypesContent');
    if (accountTypes.length === 0) {
        content.innerHTML = '<p style="color:#7f8c8d;text-align:center;">لا توجد أنواع حسابات محملة</p>';
        return;
    }

    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:15px;">';
    accountTypes.forEach(account => {
        const indent = account.parent_id ? '20px' : '0px';
        const borderColor = account.is_root ? '#e74c3c' : '#3498db';
        const bgColor = account.is_root ? '#fdf2f2' : '#f8f9fa';
        html += `
            <div style="background:${bgColor};padding:15px;border-radius:8px;border:1px solid ${borderColor};margin-left:${indent};">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <h4 style="color:#2c3e50;margin:0;">${account.name} ${account.is_root ? '🏠' : '📁'}</h4>
                    <span style="background:${borderColor};color:white;padding:4px 8px;border-radius:4px;font-size:12px;">${account.id}</span>
                </div>
                <p style="color:#7f8c8d;margin:5px 0;font-size:14px;">${account.name_en}</p>
                ${account.parent_name ? `<p style="color:#e67e22;font-size:12px;margin:0;">← تابع لـ: ${account.parent_name}</p>` : ''}
                ${account.description ? `<p style="color:#2c3e50;font-size:13px;margin:0;">${account.description}</p>` : ''}
            </div>
        `;
    });
    html += '</div>';
    content.innerHTML = html;
}

async function uploadAccountTypes() {
    const fileInput = document.getElementById('excelFile');
    const file = fileInput.files[0];

    if (!file) { alert('يرجى اختيار ملف Excel أولاً'); return; }
    if (!file.name.match(/\.(xlsx|xls)$/)) { alert('يرجى اختيار ملف Excel صالح (.xlsx أو .xls)'); return; }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/upload/account-types`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` },
            body: formData,
        });
        if (res.ok) {
            const result = await res.json();
            alert(`تم رفع الملف بنجاح! تم تحميل ${result.count} نوع حساب`);
            loadAccountTypes();
            fileInput.value = '';
        } else {
            const error = await res.json();
            alert(`خطأ في رفع الملف: ${error.error}`);
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        alert('خطأ في رفع الملف');
    }
}

// ==================== إغلاق المودال بالنقر خارجه ====================

window.onclick = function (event) {
    if (event.target === document.getElementById('requestModal')) closeModal();
    if (event.target === document.getElementById('rejectModal')) closeRejectModal();
};
