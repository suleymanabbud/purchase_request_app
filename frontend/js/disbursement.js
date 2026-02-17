/**
 * disbursement.js — الكود الخاص بلوحة تحكم أمر الصرف
 * يعتمد على: shared.js, signature.js
 */

let currentRequestId = null;
let allRequests = [];
let filteredRequests = [];
let approvedRequests = [];
let rejectedRequests = [];
let currentView = 'pending'; // 'pending', 'approved', 'rejected', 'reports'

// ==================== التهيئة ====================

document.addEventListener('DOMContentLoaded', function () {
    const user = initDashboard();
    if (!user) return;

    enforceRoleAccess('disbursement');
    loadRequests();
    loadUserSignature();

    // حفظ المحتوى الأصلي
    const mainContent = document.querySelector('.main-content');
    if (mainContent) window.originalMainContent = mainContent.innerHTML;

    // فلاتر البحث المباشر
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const departmentFilter = document.getElementById('departmentFilter');
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (statusFilter) statusFilter.addEventListener('change', applyFilters);
    if (departmentFilter) departmentFilter.addEventListener('change', applyFilters);
    if (dateFromFilter) dateFromFilter.addEventListener('change', applyFilters);
    if (dateToFilter) dateToFilter.addEventListener('change', applyFilters);

    // عداد حروف الرفض
    const rejectTextarea = document.getElementById('rejectNoteTextarea');
    if (rejectTextarea) rejectTextarea.addEventListener('input', updateRejectCharCount);
});

// ==================== التحقق من الصلاحيات ====================

function enforceRoleAccess(requiredRole) {
    const user = getCurrentUser();
    if (!user.role) return;
    if (user.role !== requiredRole) {
        const redirects = {
            admin: 'admin-dashboard.html',
            manager: 'manager-dashboard.html',
            finance: 'finance-dashboard.html',
            requester: 'index.html',
        };
        window.location.href = redirects[user.role] || 'login.html';
    }
}

// ==================== تحميل الطلبات ====================

async function loadRequests() {
    try {
        const res = await apiFetch('/my/queue');
        if (!res.ok) {
            if (res.status === 401) logout();
            return;
        }

        const payload = await res.json();
        let requestsData = Array.isArray(payload) ? payload : (payload.requests || []);

        allRequests = requestsData;
        filteredRequests = [...allRequests];

        if (!Array.isArray(payload)) {
            const el = (id) => document.getElementById(id);
            if (payload.total !== undefined && el('totalRequests')) el('totalRequests').textContent = payload.total;
            if (payload.approved !== undefined && el('approvedRequests')) el('approvedRequests').textContent = payload.approved;
            if (payload.rejected !== undefined && el('rejectedRequests')) el('rejectedRequests').textContent = payload.rejected;
            if (payload.pending !== undefined && el('pendingRequests')) el('pendingRequests').textContent = payload.pending;
        }

        updateStats();
        renderRequestsTable();
    } catch (error) {
        console.error('Error loading requests:', error);
    }
}

function updateStats() {
    const pending = allRequests.filter(r => (r.status || 'pending_manager') === 'pending_disbursement').length;
    document.getElementById('pendingRequests').textContent = pending;
}

async function loadGlobalStats() {
    try {
        const res = await apiFetch('/requests');
        if (!res.ok) return;
        const all = await res.json();
        document.getElementById('totalRequests').textContent = all.length;
        document.getElementById('approvedRequests').textContent = all.filter(r => r.status === 'approved').length;
        document.getElementById('rejectedRequests').textContent = all.filter(r => r.status === 'rejected').length;
    } catch (err) {
        console.warn('تعذر جلب الإحصائيات العامة:', err);
    }
}

// ==================== عرض الجدول ====================

function renderRequestsTable() {
    const tbody = document.getElementById('requestsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const displayRequests = filteredRequests.filter(r => {
        const status = r.status || 'pending_manager';
        return status === 'pending_disbursement';
    });

    displayRequests.forEach(request => {
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
        ${request.status !== 'approved' && request.status !== 'rejected' ? `
          <button class="action-btn btn-approve" onclick="quickUpdateStatus(${request.id}, 'approve')">
            <i class="fas fa-check"></i> إصدار أمر الصرف
          </button>
          <button class="action-btn btn-reject" onclick="quickUpdateStatus(${request.id}, 'reject')">
            <i class="fas fa-times"></i> رفض
          </button>
        ` : ''}
      </td>
    `;
        tbody.appendChild(row);
    });
}

function renderApprovedRequestsTable(requestsToRender = null) {
    const tbody = document.getElementById('requestsTableBody');
    tbody.innerHTML = '';
    const requests = requestsToRender || approvedRequests;

    requests.forEach(request => {
        const row = document.createElement('tr');
        const status = request.status || 'approved';
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

    if (requests.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7">لا توجد طلبات معتمدة حالياً.</td></tr>`;
    }
}

function renderRejectedRequestsTable(requestsToRender = null) {
    const tbody = document.getElementById('requestsTableBody');
    tbody.innerHTML = '';
    const requests = requestsToRender || rejectedRequests;

    requests.forEach(request => {
        const row = document.createElement('tr');
        const formattedTotal = formatCurrency(request.total_amount, request.currency);

        row.innerHTML = `
      <td>${request.order_number || request.id}</td>
      <td>${request.requester}</td>
      <td>${request.department}</td>
      <td>${request.date || '-'}</td>
      <td>${formattedTotal}</td>
      <td><span class="status-badge status-rejected">تم الرفض</span></td>
      <td>
        <button class="action-btn btn-view" onclick="viewRequest(${request.id})">
          <i class="fas fa-eye"></i> عرض
        </button>
      </td>
    `;
        tbody.appendChild(row);
    });

    if (requests.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7">لا توجد طلبات مرفوضة حالياً.</td></tr>`;
    }
}

// ==================== الفلاتر ====================

function applyFilters() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const status = document.getElementById('statusFilter').value;
    const department = document.getElementById('departmentFilter').value;
    const dateFrom = document.getElementById('dateFromFilter').value;
    const dateTo = document.getElementById('dateToFilter').value;

    let targetArray = currentView === 'approved' ? approvedRequests
        : currentView === 'rejected' ? rejectedRequests
            : allRequests;

    const filtered = targetArray.filter(request => {
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

    if (currentView === 'approved') renderApprovedRequestsTable(filtered);
    else if (currentView === 'rejected') renderRejectedRequestsTable(filtered);
    else { filteredRequests = filtered; renderRequestsTable(); }
}

// ==================== عرض تفاصيل الطلب ====================

async function viewRequest(requestId) {
    let request = allRequests.find(r => r.id === requestId);
    if (!request && currentView === 'approved') request = approvedRequests.find(r => r.id === requestId);
    if (!request && currentView === 'rejected') request = rejectedRequests.find(r => r.id === requestId);

    if (!request) {
        try {
            const res = await apiFetch(`/requests/${requestId}`);
            if (res.ok) request = await res.json();
        } catch (e) { /* ignore */ }
    }
    if (!request) { alert('لم يتم العثور على الطلب'); return; }

    currentRequestId = requestId;
    const formattedTotal = formatCurrency(request.total_amount || 0, request.currency);
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

    // إخفاء أزرار الموافقة/الرفض إذا لم نكن في عرض الطابور
    const actions = document.querySelector('#requestModal .modal-actions');
    if (actions) {
        const status = (request.status || '').toLowerCase();
        if ((currentView && currentView !== 'pending') || status === 'approved' || status === 'rejected') {
            actions.style.display = 'none';
        } else {
            actions.style.display = 'flex';
        }
    }
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

async function updateStatus(action, note = '', signature = null) {
    if (!currentRequestId) return;
    try {
        const res = await apiFetch(`/requests/${currentRequestId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ action, note: note.trim(), signature }),
        });
        if (res.ok) {
            const result = await res.json();
            alert(`تم ${action === 'approve' ? 'إصدار أمر الصرف ل' : 'رفض'} الطلب بنجاح`);
            closeModal();
            if (result && (result.total != null || result.approved != null || result.rejected != null)) {
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
    if (action === 'approve') {
        currentRequestId = requestId;
        showSignatureModal(function (sig) {
            updateStatus('approve', '', sig);
        });
        return;
    }
}

// ==================== التنقل بين العروض ====================

async function showApprovedRequests() {
    currentView = 'approved';
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.textContent.includes('الطلبات المعتمدة')) item.classList.add('active');
    });
    document.querySelector('.page-title').textContent = 'الطلبات المعتمدة';
    document.querySelector('.filters-section').style.display = 'block';
    document.querySelector('.requests-section').style.display = 'block';

    try {
        const res = await apiFetch('/requests?status=approved');
        if (res.ok) {
            const payload = await res.json();
            approvedRequests = Array.isArray(payload) ? payload : (payload.requests || []);
            await loadGlobalStats();
            renderApprovedRequestsTable();
        } else if (res.status === 401) logout();
    } catch (e) { console.error('Error:', e); }
}

async function showRejectedRequests() {
    currentView = 'rejected';
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.textContent.includes('الطلبات المرفوضة')) item.classList.add('active');
    });
    document.querySelector('.page-title').textContent = 'الطلبات المرفوضة';
    document.querySelector('.filters-section').style.display = 'block';
    document.querySelector('.requests-section').style.display = 'block';

    try {
        const res = await apiFetch('/requests?status=rejected');
        if (res.ok) {
            const payload = await res.json();
            rejectedRequests = Array.isArray(payload) ? payload : (payload.requests || []);
            await loadGlobalStats();
            renderRejectedRequestsTable();
        } else if (res.status === 401) logout();
    } catch (e) { console.error('Error:', e); }
}

function showPendingRequests() {
    currentView = 'pending';
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.textContent.includes('طلبات الشراء')) item.classList.add('active');
    });
    resetToOriginalContent();
    document.querySelector('.page-title').textContent = 'طلبات الشراء - أمر الصرف';
    document.querySelector('.filters-section').style.display = 'block';
    document.querySelector('.requests-section').style.display = 'block';
    loadRequests();
}

function resetToOriginalContent() {
    const mainContent = document.querySelector('.main-content');
    if (window.originalMainContent) mainContent.innerHTML = window.originalMainContent;
}

// ==================== تقارير الصرف ====================

function showDisbursementReports() {
    currentView = 'reports';
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.textContent.includes('تقارير الصرف')) item.classList.add('active');
    });

    const pageTitle = document.querySelector('.page-title');
    if (pageTitle) pageTitle.textContent = 'تقارير الصرف';

    const filtersSection = document.querySelector('.filters-section');
    const requestsSection = document.querySelector('.requests-section');
    if (filtersSection) filtersSection.style.display = 'none';
    if (requestsSection) requestsSection.style.display = 'none';

    showReportsContent();
}

function showReportsContent() {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) return;

    const reportsHTML = `
    <div style="padding:20px;max-width:1200px;margin:0 auto;">
      <div style="text-align:center;margin-bottom:30px;padding:20px;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color:#2c3e50;margin-bottom:10px;">📊 تقارير الصرف</h2>
        <p>إحصائيات شاملة لطلبات الصرف المعتمدة</p>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-bottom:30px;">
        <div class="stat-card"><div class="stat-icon total">💰</div><div class="stat-info"><h3 id="totalApprovedAmount">$0.00</h3><p>إجمالي المبالغ المعتمدة</p></div></div>
        <div class="stat-card"><div class="stat-icon approved">📋</div><div class="stat-info"><h3 id="totalApprovedCount">0</h3><p>عدد الطلبات المعتمدة</p></div></div>
        <div class="stat-card"><div class="stat-icon pending">🏢</div><div class="stat-info"><h3 id="topDepartment">-</h3><p>الأقسام الأكثر طلباً</p></div></div>
        <div class="stat-card"><div class="stat-icon rejected">📈</div><div class="stat-info"><h3 id="averageAmount">$0.00</h3><p>متوسط قيمة الطلب</p></div></div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:20px;">
        <div style="background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
          <h3 style="color:#2c3e50;margin-bottom:20px;text-align:center;">📊 توزيع الطلبات حسب القسم</h3>
          <div id="chartBars" style="display:flex;align-items:end;gap:10px;height:200px;padding:20px 0;">
            <div style="text-align:center;color:#7f8c8d;font-style:italic;padding:20px;width:100%;">جاري تحميل البيانات...</div>
          </div>
        </div>
        <div style="background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
          <h3 style="color:#2c3e50;margin-bottom:20px;text-align:center;">📅 الطلبات المعتمدة هذا الشهر</h3>
          <div id="monthlyStats" style="display:flex;flex-direction:column;gap:15px;">
            <div style="text-align:center;color:#7f8c8d;font-style:italic;padding:20px;">جاري تحميل البيانات...</div>
          </div>
        </div>
      </div>
    </div>
  `;

    mainContent.innerHTML = reportsHTML;
    loadReportsData();
}

async function loadReportsData() {
    try {
        const res = await apiFetch('/my/approved');
        if (res.ok) calculateReports(await res.json());
        else if (res.status === 401) logout();
    } catch (e) { console.error('Error:', e); }
}

function calculateReports(requests) {
    const totalAmount = requests.reduce((s, r) => s + (r.total_amount || 0), 0);
    const totalCount = requests.length;
    const avgAmount = totalCount > 0 ? totalAmount / totalCount : 0;

    const deptCounts = {};
    requests.forEach(r => { deptCounts[r.department] = (deptCounts[r.department] || 0) + 1; });
    const topDept = Object.keys(deptCounts).length > 0
        ? Object.keys(deptCounts).reduce((a, b) => deptCounts[a] > deptCounts[b] ? a : b) : 'لا توجد بيانات';

    const el = (id) => document.getElementById(id);
    if (el('totalApprovedAmount')) el('totalApprovedAmount').textContent = `$${totalAmount.toFixed(2)}`;
    if (el('totalApprovedCount')) el('totalApprovedCount').textContent = totalCount;
    if (el('topDepartment')) el('topDepartment').textContent = topDept;
    if (el('averageAmount')) el('averageAmount').textContent = `$${avgAmount.toFixed(2)}`;

    updateCharts(deptCounts, requests);
    updateMonthlyStats(requests);
}

function updateCharts(departmentCounts, requests) {
    const chartBars = document.getElementById('chartBars');
    if (!chartBars) return;

    if (Object.keys(departmentCounts).length === 0) {
        chartBars.innerHTML = '<div style="text-align:center;color:#7f8c8d;font-style:italic;padding:20px;width:100%;">لا توجد بيانات للعرض</div>';
        return;
    }

    const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6'];
    chartBars.innerHTML = Object.entries(departmentCounts).map(([dept, count], i) => {
        const percentage = (count / requests.length) * 100;
        return `
      <div style="flex:1;display:flex;flex-direction:column;justify-content:end;align-items:center;border-radius:5px 5px 0 0;position:relative;min-height:20px;height:${percentage}%;background:${colors[i % colors.length]};">
        <span style="position:absolute;bottom:-25px;font-size:12px;color:#2c3e50;font-weight:bold;">${dept}</span>
        <span style="position:absolute;top:-25px;font-size:11px;color:#7f8c8d;">${count} طلبات</span>
      </div>
    `;
    }).join('');
}

function updateMonthlyStats(requests) {
    const monthlyStats = document.getElementById('monthlyStats');
    if (!monthlyStats) return;

    if (requests.length === 0) {
        monthlyStats.innerHTML = '<div style="text-align:center;color:#7f8c8d;font-style:italic;padding:20px;">لا توجد طلبات معتمدة هذا الشهر</div>';
        return;
    }

    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    const weeks = [];
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    let weekStart = new Date(firstDay);
    let weekNumber = 1;

    while (weekStart <= lastDay) {
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);
        if (weekEnd > lastDay) weekEnd.setTime(lastDay.getTime());
        weeks.push({ number: weekNumber, start: new Date(weekStart), end: new Date(weekEnd), count: 0 });
        weekStart.setDate(weekStart.getDate() + 7);
        weekNumber++;
    }

    requests.forEach(request => {
        if (request.approved_at) {
            const approvedDate = new Date(request.approved_at);
            if (approvedDate.getMonth() === currentMonth && approvedDate.getFullYear() === currentYear) {
                weeks.forEach(week => {
                    if (approvedDate >= week.start && approvedDate <= week.end) week.count++;
                });
            }
        }
    });

    monthlyStats.innerHTML = weeks.map(week => `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:#f8f9fa;border-radius:5px;">
      <span style="font-weight:bold;color:#2c3e50;">الأسبوع ${week.number}</span>
      <span style="color:#3498db;font-weight:bold;">${week.count} طلبات</span>
    </div>
  `).join('');
}

// ==================== إغلاق المودال بالنقر خارجه ====================

window.onclick = function (event) {
    if (event.target === document.getElementById('requestModal')) closeModal();
    if (event.target === document.getElementById('rejectModal')) closeRejectModal();
    if (event.target === document.getElementById('signatureModal')) closeSignatureModal();
};
