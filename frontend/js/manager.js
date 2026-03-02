/**
 * manager.js — الكود الخاص بلوحة تحكم المدير المباشر
 * يعتمد على: shared.js, signature.js
 */

let currentRequestId = null;
let allRequests = [];
let filteredRequests = [];
let approvedRequests = [];
let rejectedRequests = [];
let currentView = 'pending'; // 'pending', 'approved', 'rejected', 'reports'
let filtersActive = false;

// ==================== التهيئة ====================

document.addEventListener('DOMContentLoaded', function () {
  const user = initDashboard();
  if (!user) return;

  enforceRoleAccess('manager');
  loadRequests();
  loadUserSignature();

  // إظهار قسم التقارير المالية لـ manager_finance
  if (user.username === 'manager_finance') {
    const el = document.getElementById('financeReportsMenuItem');
    if (el) el.style.display = 'flex';
  }

  // إظهار زر إنشاء الطلب لمدير تطوير الأعمال
  if (user.department === 'تطوير الأعمال') {
    const topActions = document.getElementById('topActions');
    if (topActions) topActions.style.display = 'flex';
  }

  // حفظ المحتوى الأصلي لـ resetToOriginalContent
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

  // عداد حروف ملاحظة الرفض
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
    const res = await apiFetch('/my/queue');
    if (!res.ok) {
      if (res.status === 401) logout();
      return;
    }

    const payload = await res.json();
    let requestsData = Array.isArray(payload) ? payload : (payload.requests || []);

    // إزالة التكرارات
    requestsData = [...new Map(requestsData.map(item => [item.id, item])).values()];
    allRequests = requestsData;
    filteredRequests = [...allRequests];

    await loadGlobalStats();
    updateStats();
    renderRequestsTable();
  } catch (error) {
    console.error('Error loading requests:', error);
  }
}

function updateStats() {
  const pending = allRequests.filter(r => (r.status || 'pending_manager') === 'pending_manager').length;
  document.getElementById('pendingRequests').textContent = pending;
}

async function loadGlobalStats() {
  try {
    // جلب المعتمدة والمرفوضة من الـ APIs المخصصة
    const [resAll, resApproved, resRejected] = await Promise.all([
      apiFetch('/requests'),
      apiFetch('/my/approved'),
      apiFetch('/my/rejected')
    ]);

    if (resAll.ok) {
      const all = await resAll.json();
      document.getElementById('totalRequests').textContent = all.length;
    }
    if (resApproved.ok) {
      const approved = await resApproved.json();
      document.getElementById('approvedRequests').textContent = Array.isArray(approved) ? approved.length : 0;
    }
    if (resRejected.ok) {
      const rejected = await resRejected.json();
      document.getElementById('rejectedRequests').textContent = Array.isArray(rejected) ? rejected.length : 0;
    }
  } catch (err) {
    console.warn('تعذر جلب الإحصائيات العامة:', err);
  }
}

// ==================== عرض الجداول ====================

function renderRequestsTable() {
  const tbody = document.getElementById('requestsTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const displayRequests = filtersActive ? filteredRequests : allRequests;

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
        ${status !== 'approved' && status !== 'rejected' ? `
          <button class="action-btn btn-approve" onclick="quickUpdateStatus(${request.id}, 'approve')">
            <i class="fas fa-check"></i> موافقة
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
    const approvedDate = request.approved_at ? new Date(request.approved_at).toLocaleDateString('en-US') : '-';

    row.innerHTML = `
      <td>${request.order_number || request.id}</td>
      <td>${request.requester}</td>
      <td>${request.department}</td>
      <td>${request.date || '-'}</td>
          <td>${formattedTotal}</td>
      <td><span class="status-badge status-${status}">${getStatusText(status)}</span></td>
          <td>${approvedDate}</td>
      <td>
        <button class="action-btn btn-view" onclick="viewRequest(${request.id})">
          <i class="fas fa-eye"></i> عرض
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });

  if (requests.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8">لا توجد طلبات معتمدة حالياً.</td></tr>`;
  }
}

function renderRejectedRequestsTable(requestsToRender = null) {
  const tbody = document.getElementById('requestsTableBody');
  tbody.innerHTML = '';
  const requests = requestsToRender || rejectedRequests;

  requests.forEach(request => {
    const row = document.createElement('tr');
    const status = request.status || 'rejected';
    const formattedTotal = formatCurrency(request.total_amount, request.currency);
    const rejectedDate = request.rejected_at ? new Date(request.rejected_at).toLocaleDateString('en-US') : '-';

    row.innerHTML = `
      <td>${request.order_number || request.id}</td>
      <td>${request.requester}</td>
      <td>${request.department}</td>
      <td>${request.date || '-'}</td>
          <td>${formattedTotal}</td>
      <td><span class="status-badge status-${status}">${getStatusText(status)}</span></td>
          <td>${rejectedDate}</td>
      <td>
        <button class="action-btn btn-view" onclick="viewRequest(${request.id})">
          <i class="fas fa-eye"></i> عرض
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });

  if (requests.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8">لا توجد طلبات مرفوضة حالياً.</td></tr>`;
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
    const matchesStatus = !status || (request.status || 'pending_manager') === status;
    const matchesDepartment = !department || request.department === department;
    const matchesDateFrom = !dateFrom || (request.date && request.date >= dateFrom);
    const matchesDateTo = !dateTo || (request.date && request.date <= dateTo);
    return matchesSearch && matchesStatus && matchesDepartment && matchesDateFrom && matchesDateTo;
  });

  filtersActive = !!(search || status || department || dateFrom || dateTo);

  if (currentView === 'approved') renderApprovedRequestsTable(filtered);
  else if (currentView === 'rejected') renderRejectedRequestsTable(filtered);
  else { filteredRequests = filtered; renderRequestsTable(); }
}

// ==================== عرض تفاصيل الطلب ====================

async function viewRequest(requestId) {
  // دائماً نجلب التفاصيل الكاملة من API لضمان وجود items والبيانات المحدّثة
  let request = null;
  try {
    const res = await apiFetch(`/requests/${requestId}`);
    if (res.ok) request = await res.json();
  } catch (e) { /* ignore */ }

  // fallback: ابحث في البيانات المحلية
  if (!request) request = allRequests.find(r => r.id === requestId);
  if (!request && currentView === 'approved') request = approvedRequests.find(r => r.id === requestId);
  if (!request && currentView === 'rejected') request = rejectedRequests.find(r => r.id === requestId);

  if (!request) { alert('لم يتم العثور على الطلب'); return; }

  currentRequestId = requestId;
  const formattedTotal = formatCurrency(request.total_amount, request.currency);
  const modalBody = document.getElementById('modalBody');

  // بناء محتوى المودال
  let itemsHTML = '';
  if (request.items && request.items.length > 0) {
    const user = getCurrentUser();
    const canActOnItems = currentView === 'pending'
      && request.status === 'pending_manager'
      && request.status !== 'approved'
      && request.status !== 'rejected'
      && request.status !== 'pending_finance'
      && request.status !== 'pending_disbursement'
      && request.status !== 'pending_procurement'
      && request.status !== 'completed';

    itemsHTML = `
      <div class="items-list">
        <h4>الأصناف المطلوبة</h4>
        <table class="items-table-modal">
          <thead>
            <tr>
              <th>#</th><th>اسم المادة</th><th>المواصفات</th><th>الوحدة</th>
              <th>الكمية</th><th>السعر</th><th>المجموع</th><th>الحالة</th>
              ${canActOnItems ? '<th>الإجراءات</th>' : ''}
            </tr>
          </thead>
          <tbody>
            ${request.items.map((item, i) => `
              <tr id="item-row-${item.id}" ${item.status === 'rejected' ? 'style="background:#fff5f5"' : ''}>
                <td>${i + 1}</td>
                <td>${item.item_name}</td>
                <td>${item.specification || '-'}</td>
                <td>${item.unit || '-'}</td>
                <td>${item.quantity}</td>
                <td>${item.price}</td>
                <td>${(item.quantity * item.price).toFixed(2)}</td>
                <td>
                  ${getItemStatusBadge(item.status)}
                  ${item.rejection_reason ? `<br><small style="color:red">${item.rejection_reason}</small>` : ''}
                </td>
                ${canActOnItems ? `
                  <td>
                    ${(!item.status || item.status === 'pending') ? `
                      <button class="action-btn btn-approve" onclick="approveItem(${request.id}, ${item.id})" style="font-size:11px;padding:4px 8px">✅</button>
                      <button class="action-btn btn-reject" onclick="rejectItem(${request.id}, ${item.id})" style="font-size:11px;padding:4px 8px">❌</button>
                    ` : (item.rejected_by ? `<small>رفض: ${item.rejected_by}</small>` : '')}
                  </td>
                ` : ''}
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="${canActOnItems ? 8 : 7}" style="text-align:left;font-weight:bold">المجموع الكلي:</td>
              <td style="font-weight:bold">${formattedTotal}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;
  }

  modalBody.innerHTML = `
    <div class="request-header">
      <h3>تفاصيل الطلب #${request.order_number || request.id}</h3>
      <div class="request-status">
        <span class="status-badge status-${request.status}">${getStatusText(request.status)}</span>
      </div>
    </div>
    <div class="detail-grid">
      <div class="detail-item"><span class="detail-label">رقم الطلب</span><span class="detail-value">${request.order_number || request.id}</span></div>
      <div class="detail-item"><span class="detail-label">مقدم الطلب</span><span class="detail-value">${request.requester}</span></div>
      <div class="detail-item"><span class="detail-label">القسم</span><span class="detail-value">${request.department}</span></div>
      <div class="detail-item"><span class="detail-label">تاريخ الطلب</span><span class="detail-value">${request.date || '-'}</span></div>
      <div class="detail-item"><span class="detail-label">موعد التسليم</span><span class="detail-value">${request.delivery_date || '-'}</span></div>
      <div class="detail-item"><span class="detail-label">عنوان التسليم</span><span class="detail-value">${request.delivery_address || '-'}</span></div>
      <div class="detail-item"><span class="detail-label">رمز المشروع</span><span class="detail-value">${request.project_code || '-'}</span></div>
      <div class="detail-item"><span class="detail-label">العملة</span><span class="detail-value">${request.currency || '-'}</span></div>
      <div class="detail-item"><span class="detail-label">المبلغ الإجمالي</span><span class="detail-value">${formattedTotal}</span></div>
      <div class="detail-item"><span class="detail-label">الحالة</span><span class="detail-value">${getStatusText(request.status)}</span></div>
    </div>
    ${itemsHTML}
  `;

  // إخفاء أزرار الموافقة/الرفض للطلبات المنتهية أو المتقدمة
  const modalActions = document.querySelector('.modal-actions');
  const nonActionableStatuses = ['approved', 'rejected', 'pending_finance', 'pending_disbursement', 'pending_procurement', 'completed'];
  const isNonActionable = nonActionableStatuses.includes(request.status) || currentView === 'approved' || currentView === 'rejected';

  if (isNonActionable) {
    modalActions.classList.add('hidden');
    let statusMsg = '';
    if (request.status === 'rejected') {
      statusMsg = '<div class="status-message rejected">❌ هذا الطلب تم رفضه</div>';
    } else if (currentView === 'rejected') {
      statusMsg = '<div class="status-message rejected">❌ هذا الطلب تم رفضه</div>';
    } else {
      statusMsg = `<div class="status-message approved">✅ تم اعتماد هذا الطلب — الحالة: ${getStatusText(request.status)}</div>`;
    }
    modalBody.insertAdjacentHTML('beforeend', statusMsg);
  } else {
    modalActions.classList.remove('hidden');
  }

  document.getElementById('requestModal').style.display = 'block';
}

function closeModal() {
  document.getElementById('requestModal').style.display = 'none';
  currentRequestId = null;
  document.querySelector('.modal-actions').classList.remove('hidden');
  document.querySelectorAll('.status-message').forEach(msg => msg.remove());
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
      alert(`تم ${action === 'approve' ? 'الموافقة على' : 'رفض'} الطلب بنجاح`);
      closeModal();
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
    // استخدام نظام التوقيع: إذا محفوظ → مباشرة، إلا → مودال
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
  event.target.closest('.menu-item').classList.add('active');
  document.querySelector('.page-title').textContent = 'الطلبات المعتمدة';

  // تحديث عناوين الجدول
  const thead = document.querySelector('.requests-table thead tr');
  if (thead) thead.innerHTML = `
    <th>رقم الطلب</th><th>مقدم الطلب</th><th>القسم</th>
    <th>تاريخ الطلب</th><th>المبلغ الإجمالي</th><th>الحالة</th>
    <th>تاريخ الاعتماد</th><th>الإجراءات</th>`;

  try {
    const res = await apiFetch('/my/approved');
    if (res.ok) { approvedRequests = await res.json(); renderApprovedRequestsTable(); }
    else if (res.status === 401) logout();
  } catch (e) { console.error('Error:', e); }
}

async function showRejectedRequests() {
  currentView = 'rejected';
  document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
  event.target.closest('.menu-item').classList.add('active');
  document.querySelector('.page-title').textContent = 'الطلبات المرفوضة';

  // تحديث عناوين الجدول
  const thead = document.querySelector('.requests-table thead tr');
  if (thead) thead.innerHTML = `
    <th>رقم الطلب</th><th>مقدم الطلب</th><th>القسم</th>
    <th>تاريخ الطلب</th><th>المبلغ الإجمالي</th><th>الحالة</th>
    <th>تاريخ الرفض</th><th>الإجراءات</th>`;

  try {
    const res = await apiFetch('/my/rejected');
    if (res.ok) { rejectedRequests = await res.json(); renderRejectedRequestsTable(); }
    else if (res.status === 401) logout();
  } catch (e) { console.error('Error:', e); }
}

function showPendingRequests() {
  currentView = 'pending';
  document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
  document.querySelectorAll('.menu-item').forEach(item => {
    if (item.textContent.includes('طلبات الشراء')) item.classList.add('active');
  });
  resetToOriginalContent();
  document.querySelector('.page-title').textContent = 'طلبات الشراء - المدير المباشر';
  document.querySelector('.filters-section').style.display = 'block';
  document.querySelector('.requests-section').style.display = 'block';
  loadRequests();
}

function resetToOriginalContent() {
  const mainContent = document.querySelector('.main-content');
  if (window.originalMainContent) mainContent.innerHTML = window.originalMainContent;
}

// ==================== التقارير المالية ====================

function showFinanceReports() {
  currentView = 'reports';
  document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
  document.querySelectorAll('.menu-item').forEach(item => {
    if (item.textContent.includes('التقارير المالية')) item.classList.add('active');
  });

  const pageTitle = document.querySelector('.page-title');
  if (pageTitle) pageTitle.textContent = 'التقارير المالية';

  const filtersSection = document.querySelector('.filters-section');
  const requestsSection = document.querySelector('.requests-section');
  if (filtersSection) filtersSection.style.display = 'none';
  if (requestsSection) requestsSection.style.display = 'none';

  showFinanceReportsContent();
}

function showFinanceReportsContent() {
  const mainContent = document.querySelector('.main-content');
  if (!mainContent) return;

  mainContent.innerHTML = `
    <div class="reports-container" style="padding:20px;max-width:1200px;margin:0 auto;">
      <div style="text-align:center;margin-bottom:30px;padding:20px;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color:#2c3e50;margin-bottom:10px;">💰 التقارير المالية</h2>
        <p>إحصائيات شاملة للطلبات المالية المعتمدة</p>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-bottom:30px;">
        <div class="stat-card"><div class="stat-icon total">💵</div><div class="stat-info"><h3 id="totalApprovedAmount">$0.00</h3><p>إجمالي المبالغ المعتمدة</p></div></div>
        <div class="stat-card"><div class="stat-icon approved">📊</div><div class="stat-info"><h3 id="totalApprovedCount">0</h3><p>عدد الطلبات المعتمدة</p></div></div>
        <div class="stat-card"><div class="stat-icon pending">🏢</div><div class="stat-info"><h3 id="topDepartment">-</h3><p>الأقسام الأكثر طلباً</p></div></div>
        <div class="stat-card"><div class="stat-icon rejected">📈</div><div class="stat-info"><h3 id="averageAmount">$0.00</h3><p>متوسط قيمة الطلب</p></div></div>
      </div>
    </div>
  `;
  loadFinanceReportsData();
}

async function loadFinanceReportsData() {
  try {
    const res = await apiFetch('/my/approved');
    if (res.ok) calculateFinanceReports(await res.json());
  } catch (e) { console.error('Error:', e); }
}

function calculateFinanceReports(requests) {
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
}

// ==================== إنشاء طلب جديد ====================

window.showCreateRequestModal = function () {
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'createRequestModal';
  modal.style.display = 'block';
  window.modalIsSaved = false;

  modal.innerHTML = `
    <div class="modal-content" style="width:95%;max-width:900px;max-height:95vh;overflow-y:auto;margin:2.5vh auto;">
      <div class="modal-header" style="background:linear-gradient(135deg,#698163,#4a5d45);">
        <h3 class="modal-title" style="color:white"><i class="fas fa-file-invoice"></i> إنشاء طلب شراء جديد</h3>
        <button class="close-btn" onclick="closeCreateRequestModal()" style="color:white">&times;</button>
      </div>
      <div class="modal-body" style="padding:30px;background:#f8f6f3;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:25px;">
          <div style="background:white;padding:20px;border-radius:12px;border-right:4px solid #698163;">
            <h4 style="color:#698163;margin-bottom:15px;border-bottom:1px solid #eee;padding-bottom:10px;"><i class="fas fa-user"></i> معلومات الطالب</h4>
            <div style="display:flex;flex-direction:column;gap:12px;">
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">مقدم الطلب:</label>
                <input type="text" id="modalRequester" placeholder="اسم مقدم الطلب" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">الإدارة:</label>
                <select id="modalDepartment" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
                  <option value="تطوير الأعمال">تطوير الأعمال</option><option value="مالية">مالية</option>
                  <option value="موارد بشرية">موارد بشرية</option><option value="تقنية المعلومات">تقنية المعلومات</option>
                </select>
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">عنوان التسليم:</label>
                <input type="text" id="modalDeliveryAddress" placeholder="عنوان التسليم" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">موعد التسليم:</label>
                <input type="date" id="modalDeliveryDate" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
            </div>
          </div>
          <div style="background:white;padding:20px;border-radius:12px;border-right:4px solid #b7a678;">
            <h4 style="color:#b7a678;margin-bottom:15px;border-bottom:1px solid #eee;padding-bottom:10px;"><i class="fas fa-file-alt"></i> معلومات الطلب</h4>
            <div style="display:flex;flex-direction:column;gap:12px;">
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">تاريخ الطلب:</label>
                <input type="date" id="modalOrderDate" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">رمز الطلب:</label>
                <input type="text" id="modalOrderNumber" value="PR-" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">رمز المشروع:</label>
                <input type="text" id="modalProjectCode" placeholder="رمز المشروع" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <label style="min-width:100px;font-weight:600;">العملة:</label>
                <select id="modalCurrency" required style="flex:1;padding:10px;border:2px solid #e0e0e0;border-radius:8px;">
                  <option value="SYP">الليرة السورية (SYP)</option><option value="USD" selected>الدولار الأمريكي (USD)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div style="background:white;padding:20px;border-radius:12px;margin-bottom:25px;">
          <h4 style="color:#2c3e50;margin-bottom:15px;border-bottom:2px solid #698163;padding-bottom:10px;"><i class="fas fa-list" style="color:#698163"></i> قائمة المواد</h4>
          <table class="items-table" id="modalItemsTable" style="width:100%;border-collapse:collapse;">
            <thead><tr style="background:#698163;color:white;">
              <th style="width:5%;padding:12px">#</th><th style="width:22%;padding:12px">اسم المادة</th><th style="width:28%;padding:12px">المواصفات</th>
              <th style="width:10%;padding:12px">الوحدة</th><th style="width:10%;padding:12px">العدد</th><th style="width:12%;padding:12px">السعر</th><th style="width:13%;padding:12px">المجموع</th>
            </tr></thead>
            <tbody id="modalItemsTableBody">
              <tr><td style="padding:10px;text-align:center">1</td>
                <td style="padding:8px"><textarea placeholder="اسم المادة" rows="2" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;resize:none;"></textarea></td>
                <td style="padding:8px"><textarea placeholder="المواصفات" rows="2" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;resize:none;"></textarea></td>
                <td style="padding:8px"><input type="text" placeholder="قطعة" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
                <td style="padding:8px"><input type="number" min="0" step="0.01" oninput="calculateModalGrandTotal()" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
                <td style="padding:8px"><input type="number" min="0" step="0.01" oninput="calculateModalGrandTotal()" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
                <td class="row-total" style="padding:10px;text-align:center;font-weight:600;color:#698163;">0.00</td>
              </tr>
            </tbody>
            <tfoot><tr style="background:#b7a678;color:white;">
              <td colspan="6" style="text-align:left;font-weight:bold;padding:15px;">المجموع الكلي:</td>
              <td id="modalGrandTotal" style="font-weight:bold;padding:15px;text-align:center;font-size:18px;">0.00 $</td>
            </tr></tfoot>
          </table>
          <button class="action-btn btn-approve" onclick="addModalRow()" style="margin-top:15px;padding:12px 25px;font-size:14px;">
            <i class="fas fa-plus"></i> إضافة صنف جديد
          </button>
        </div>

        <div style="text-align:center;padding:20px 0;">
          <button class="action-btn btn-approve" onclick="saveModalRequest()" style="padding:15px 50px;font-size:18px;border-radius:10px;">
            <i class="fas fa-save"></i> 💾 حفظ الطلب
          </button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // تعبئة البيانات التلقائية
  setTimeout(async () => {
    const user = getCurrentUser();
    const today = new Date().toISOString().split('T')[0];
    const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];

    const el = (id) => document.getElementById(id);
    if (el('modalDepartment')) el('modalDepartment').value = user.department || 'تطوير الأعمال';
    if (el('modalOrderDate')) el('modalOrderDate').value = today;
    if (el('modalDeliveryDate')) el('modalDeliveryDate').value = tomorrow;

    // توليد تلقائي لرمز الطلب
    if (el('modalOrderNumber')) {
      el('modalOrderNumber').value = generateOrderNumber();
      el('modalOrderNumber').readOnly = true;
      el('modalOrderNumber').style.backgroundColor = '#f0f0f0';
    }
    // توليد تلقائي لرمز المشروع
    if (el('modalProjectCode')) {
      const now = new Date();
      const rand = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
      el('modalProjectCode').value = `PRJ-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${rand}`;
      el('modalProjectCode').readOnly = true;
      el('modalProjectCode').style.backgroundColor = '#f0f0f0';
    }
  }, 100);
};

window.closeCreateRequestModal = function () {
  const modal = document.getElementById('createRequestModal');
  if (modal) modal.remove();
};

function addModalRow() {
  const tbody = document.getElementById('modalItemsTableBody');
  const rowCount = tbody.children.length + 1;
  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${rowCount}</td>
    <td><textarea placeholder="اسم المادة" rows="2" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;resize:none;"></textarea></td>
    <td><textarea placeholder="المواصفات" rows="2" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;resize:none;"></textarea></td>
    <td><input type="text" placeholder="قطعة" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
    <td><input type="number" min="0" step="0.01" oninput="calculateModalGrandTotal()" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
    <td><input type="number" min="0" step="0.01" oninput="calculateModalGrandTotal()" required style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;text-align:center;"></td>
    <td class="row-total" style="text-align:center;font-weight:600;color:#698163;">0.00</td>
  `;
  tbody.appendChild(row);
}

function calculateModalGrandTotal() {
  const tbody = document.getElementById('modalItemsTableBody');
  let grandTotal = 0;
  tbody.querySelectorAll('tr').forEach(row => {
    const qty = parseFloat(row.querySelector('input[type="number"]:nth-of-type(1)')?.value) || 0;
    const price = parseFloat(row.querySelector('input[type="number"]:nth-of-type(2)')?.value) || 0;
    const total = qty * price;
    const totalCell = row.querySelector('.row-total');
    if (totalCell) totalCell.textContent = total.toFixed(2);
    grandTotal += total;
  });
  const el = document.getElementById('modalGrandTotal');
  if (el) el.textContent = grandTotal.toFixed(2) + ' $';
}

function generateOrderNumber() {
  const now = new Date();
  const y = now.getFullYear(), m = String(now.getMonth() + 1).padStart(2, '0'), d = String(now.getDate()).padStart(2, '0');
  return `PR-${y}${m}${d}-${Math.floor(Math.random() * 1000).toString().padStart(3, '0')}`;
}

async function saveModalRequest() {
  try {
    const val = (id) => document.getElementById(id)?.value.trim();
    const requester = val('modalRequester');
    const department = val('modalDepartment');
    const deliveryAddress = val('modalDeliveryAddress');
    const deliveryDate = val('modalDeliveryDate');
    const orderDate = val('modalOrderDate');
    const projectCode = val('modalProjectCode');

    if (!requester) { alert('يرجى ملء حقل مقدم الطلب'); return; }
    if (!department) { alert('يرجى ملء حقل القسم'); return; }
    if (!deliveryAddress) { alert('يرجى ملء حقل عنوان التسليم'); return; }
    if (!deliveryDate) { alert('يرجى ملء حقل موعد التسليم'); return; }

    const items = [];
    document.getElementById('modalItemsTableBody').querySelectorAll('tr').forEach(row => {
      const textareas = row.querySelectorAll('textarea');
      const inputs = row.querySelectorAll('input');
      const name = textareas[0]?.value.trim();
      const spec = textareas[1]?.value.trim();
      const unit = inputs[0]?.value.trim();
      const qty = parseFloat(inputs[1]?.value) || 0;
      const price = parseFloat(inputs[2]?.value) || 0;
      if (name && qty > 0 && price > 0) {
        items.push({ item_name: name, specification: spec, unit, quantity: qty, price, total: qty * price });
      }
    });

    if (items.length === 0) { alert('يرجى إضافة عنصر واحد على الأقل'); return; }

    const res = await apiFetch('/requests', {
      method: 'POST',
      body: JSON.stringify({
        requester, department, delivery_address: deliveryAddress, delivery_date: deliveryDate,
        project_code: projectCode, order_number: val('modalOrderNumber'), currency: val('modalCurrency'),
        items, total_amount: items.reduce((s, i) => s + i.total, 0),
      }),
    });

    if (res.ok) {
      alert('تم حفظ الطلب بنجاح!');
      closeCreateRequestModal();
      loadRequests();
    } else {
      const error = await res.json();
      alert(`خطأ في حفظ الطلب: ${error.error}`);
    }
  } catch (error) {
    console.error('خطأ في حفظ الطلب:', error);
    alert('خطأ في حفظ الطلب');
  }
}

// ==================== الموافقة على البنود ====================

async function approveItem(requestId, itemId) {
  try {
    const res = await apiFetch(`/requests/${requestId}/items/${itemId}/action`, {
      method: 'POST', body: JSON.stringify({ action: 'approve' }),
    });
    if (res.ok) {
      updateItemUI(itemId, 'approved');
      updateLocalRequestData(requestId, itemId, 'approved');
    } else { const e = await res.json(); alert(`خطأ: ${e.error}`); }
  } catch (e) { alert('حدث خطأ أثناء الاتصال بالخادم'); }
}

async function rejectItem(requestId, itemId) {
  const reason = prompt('يرجى إدخال سبب رفض هذا البند:');
  if (reason === null) return;
  if (!reason.trim()) { alert('يجب ذكر سبب الرفض!'); return; }

  try {
    const res = await apiFetch(`/requests/${requestId}/items/${itemId}/action`, {
      method: 'POST', body: JSON.stringify({ action: 'reject', reason }),
    });
    if (res.ok) {
      updateItemUI(itemId, 'rejected', reason);
      updateLocalRequestData(requestId, itemId, 'rejected', reason);
    } else { const e = await res.json(); alert(`خطأ: ${e.error}`); }
  } catch (e) { alert('حدث خطأ أثناء الاتصال بالخادم'); }
}

function updateItemUI(itemId, status, reason = '') {
  const row = document.getElementById(`item-row-${itemId}`);
  if (!row) return;
  row.cells[7].innerHTML = `${getItemStatusBadge(status)}${reason ? `<br><small style="color:red">${reason}</small>` : ''}`;
  row.cells[8].innerHTML = status === 'rejected' ? `<small>رفض: ${getCurrentUser().full_name}</small>` : '';
  row.style.backgroundColor = status === 'rejected' ? '#fff5f5' : '';
}

function updateLocalRequestData(requestId, itemId, status, reason = '') {
  const req = allRequests.find(r => r.id === requestId);
  if (req?.items) {
    const item = req.items.find(i => i.id === itemId);
    if (item) { item.status = status; item.rejection_reason = reason; }
  }
}

function getItemStatusBadge(status) {
  status = status || 'pending';
  const labels = { pending: 'معلق', approved: 'معتمد', rejected: 'مرفوض' };
  const styles = { pending: 'background:#fff3cd;color:#856404;', approved: 'background:#d4edda;color:#155724;', rejected: 'background:#f8d7da;color:#721c24;' };
  return `<span style="padding:2px 6px;border-radius:4px;font-size:11px;${styles[status] || ''}">${labels[status] || status}</span>`;
}

// ==================== إغلاق المودال بالنقر خارجه ====================

window.onclick = function (event) {
  if (event.target === document.getElementById('requestModal')) closeModal();
  if (event.target === document.getElementById('rejectModal')) closeRejectModal();
  if (event.target === document.getElementById('signatureModal')) closeSignatureModal();
};
