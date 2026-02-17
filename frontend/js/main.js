const API_BASE = `${window.location.origin}/api`;
// ================== تحقق من تسجيل الدخول ==================
document.addEventListener('DOMContentLoaded', function () {
  const token = localStorage.getItem('token');
  const userStr = localStorage.getItem('user');
  if (!token || !userStr) {
    alert('⚠️ يجب تسجيل الدخول أولاً');
    window.location.href = 'login.html';
    return;
  }
  // حفظ بيانات المستخدم في متغيرات عامة
  window.currentUser = JSON.parse(userStr);
  // مثال: window.currentUser.role, window.currentUser.department
  // تعبئة حقل القسم تلقائيًا للطالب (حقل مقدم الطلب يبقى فارغاً ليملأه الموظف)
  if (window.currentUser.role === 'requester') {
    const departmentEl = document.getElementById('department');
    if (departmentEl) {
      departmentEl.innerHTML = '';
      const opt = document.createElement('option');
      opt.value = window.currentUser.department;
      opt.textContent = window.currentUser.department;
      departmentEl.appendChild(opt);
      departmentEl.value = window.currentUser.department;
      departmentEl.setAttribute('readonly', 'readonly');
    }
  }

  // ملء أسماء المدراء في جدول الموافقات
  fillApprovalManagerNames();
});

// ================== ملء أسماء المدراء في جدول الموافقات ==================
async function fillApprovalManagerNames() {
  try {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/approval-managers`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
      console.warn('تعذر جلب أسماء المدراء');
      return;
    }

    const managers = await response.json();

    // حقول جدول الموافقات (الاسم والمنصب)
    const approvalInputs = document.querySelectorAll('.approval-input');

    // ملء اسم الطالب في حقل الطالب
    if (window.currentUser && approvalInputs[0]) {
      approvalInputs[0].value = window.currentUser.full_name || window.currentUser.username;
    }

    // ملء منصب الطالب
    if (approvalInputs[4]) {
      approvalInputs[4].value = 'موظف ' + (window.currentUser?.department || '');
    }

    // ملء اسم المدير المباشر
    if (managers.direct_manager && approvalInputs[1]) {
      approvalInputs[1].value = managers.direct_manager;
    }

    // ملء منصب المدير المباشر
    if (managers.direct_manager_position && approvalInputs[5]) {
      approvalInputs[5].value = managers.direct_manager_position;
    }

    // ملء اسم المدير المالي
    if (managers.finance_manager && approvalInputs[2]) {
      approvalInputs[2].value = managers.finance_manager;
    }

    // ملء منصب المدير المالي
    if (managers.finance_manager_position && approvalInputs[6]) {
      approvalInputs[6].value = managers.finance_manager_position;
    }

    // ملء اسم آمر الصرف
    if (managers.disbursement_manager && approvalInputs[3]) {
      approvalInputs[3].value = managers.disbursement_manager;
    }

    // ملء منصب آمر الصرف
    if (managers.disbursement_manager_position && approvalInputs[7]) {
      approvalInputs[7].value = managers.disbursement_manager_position;
    }

  } catch (error) {
    console.warn('خطأ في جلب أسماء المدراء:', error);
  }
}

// ================== الإشعارات ==================
let requesterNotifications = [];
let notificationIntervalId = null;

function initNotifications() {
  const btn = document.getElementById('notificationsBtn');
  const badge = document.getElementById('notificationsBadge');
  const popover = document.getElementById('notificationsPopover');
  const list = document.getElementById('notificationsList');
  const closeBtn = document.getElementById('closeNotifications');
  const markReadBtn = document.getElementById('markNotificationsRead');

  if (!btn || !badge || !popover || !list) {
    return;
  }

  btn.addEventListener('click', () => {
    popover.classList.toggle('active');
    if (popover.classList.contains('active')) {
      loadRequesterNotifications();
    }
  });

  closeBtn?.addEventListener('click', () => {
    popover.classList.remove('active');
  });

  markReadBtn?.addEventListener('click', markAllRequesterNotificationsRead);

  document.addEventListener('click', (event) => {
    if (!popover.contains(event.target) && !btn.contains(event.target)) {
      popover.classList.remove('active');
    }
  });

  loadRequesterNotifications();
  if (notificationIntervalId) {
    clearInterval(notificationIntervalId);
  }
  notificationIntervalId = setInterval(loadRequesterNotifications, 60_000);
}

async function loadRequesterNotifications() {
  try {
    const response = await fetch(`${API_BASE}/notifications`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    });
    if (!response.ok) return;
    requesterNotifications = await response.json();
    renderRequesterNotifications();
  } catch (error) {
    console.warn('تعذر جلب الإشعارات', error);
  }
}

function renderRequesterNotifications() {
  const badge = document.getElementById('notificationsBadge');
  const list = document.getElementById('notificationsList');
  if (!badge || !list) return;

  const unread = requesterNotifications.filter((n) => !n.is_read).length;
  if (unread > 0) {
    badge.textContent = unread;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }

  if (!requesterNotifications.length) {
    list.innerHTML = '<li>لا توجد إشعارات حالياً.</li>';
    return;
  }

  list.innerHTML = requesterNotifications.map((notif) => {
    const createdAt = notif.created_at ? new Date(notif.created_at).toLocaleString('ar-SA') : '';
    const noteLine = notif.note ? `<small>ملاحظة: ${notif.note}</small>` : '';
    return `<li class="${notif.is_read ? '' : 'unread'}">
        <strong>${notif.title}</strong>
        <div>${notif.message}</div>
        ${noteLine}
        <small>${createdAt}</small>
    </li>`;
  }).join('');
}

async function markAllRequesterNotificationsRead() {
  try {
    const response = await fetch(`${API_BASE}/notifications/read-all`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    });
    if (response.ok) {
      await loadRequesterNotifications();
    }
  } catch (error) {
    console.warn('تعذر تحديث الإشعارات', error);
  }
}

// ================== تهيئة التواريخ ==================
document.getElementById('orderDate').value = new Date().toISOString().split('T')[0];
document.getElementById('deliveryDate').value = new Date().toISOString().split('T')[0];

// ================== توليد رقم الطلب (الجزء الرقمي فقط) ==================
// يعيد فقط اللاحقة مثل: 20251008-0930 بدون "PR-"
function generateOrderNumberSuffix() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const t = String(now.getHours()).padStart(2, '0') + String(now.getMinutes()).padStart(2, '0');
  return `${y}${m}${d}-${t}`;
}

// يضمن أن القيمة تبدأ دائمًا بـ PR-
function ensurePRPrefix(val = "") {
  let v = String(val).toUpperCase();
  // إزالة أي "PR" سابقة ثم إضافة "PR-"
  v = v.replace(/^PR-?/i, "");
  return "PR-" + v;
}

// ضبط قيمة حقل رقم الطلب عند التحميل
const orderNumberInput = document.getElementById('orderNumber');
if (!orderNumberInput.value.trim() || orderNumberInput.value.trim() === 'PR-') {
  // إن كان الحقل فارغًا أو فقط PR-: نولّد قيمة افتراضية بصيغة PR-YYYYMMDD-HHMM
  orderNumberInput.value = 'PR-' + generateOrderNumberSuffix();
} else {
  // إن كانت فيه قيمة: نضمن وجود البادئة PR-
  orderNumberInput.value = ensurePRPrefix(orderNumberInput.value);
}
// جعل الحقل للقراءة فقط — لا يحتاج التعديل اليدوي
orderNumberInput.readOnly = true;
orderNumberInput.style.backgroundColor = '#f0f0f0';
orderNumberInput.style.cursor = 'not-allowed';

// توليد رمز المشروع تلقائياً
const projectCodeInput = document.getElementById('projectCode');
if (projectCodeInput && (!projectCodeInput.value.trim())) {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const rand = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
  projectCodeInput.value = `PRJ-${y}${m}${d}-${rand}`;
  projectCodeInput.readOnly = true;
  projectCodeInput.style.backgroundColor = '#f0f0f0';
  projectCodeInput.style.cursor = 'not-allowed';
}

// منع حذف البادئة "PR-"
orderNumberInput.addEventListener('keydown', (e) => {
  const pos = orderNumberInput.selectionStart ?? 0;
  // منع حذف الأحرف الثلاثة الأولى (P,R,-)
  if ((e.key === 'Backspace' || e.key === 'Delete') && pos <= 3) {
    e.preventDefault();
  }
});

// في كل إدخال، نعيد فرض البادئة PR-
orderNumberInput.addEventListener('input', () => {
  const caret = orderNumberInput.selectionStart ?? 0;
  const before = orderNumberInput.value.length;
  orderNumberInput.value = ensurePRPrefix(orderNumberInput.value);
  const after = orderNumberInput.value.length;
  // الحفاظ على موضع المؤشر قدر الإمكان
  const diff = after - before;
  const newPos = Math.max(3, caret + diff);
  orderNumberInput.setSelectionRange(newPos, newPos);
});

// ================== إدارة الجدول والحساب ==================
let rowCounter = 1;

function addNewRow() {
  rowCounter++;
  const tbody = document.getElementById('itemsBody');
  const tr = document.createElement('tr');
  // ملاحظة: استخدمنا textarea في عمودي الاسم والمواصفات (اتساقًا مع الصف الأول)
  tr.innerHTML = `
    <td>${rowCounter}</td>
    <td><textarea placeholder="اسم المادة / الخدمة" rows="2" required></textarea></td>
    <td><textarea placeholder="المواصفات الفنية" rows="2"></textarea></td>
    <td><input type="text" placeholder="قطعة" required></td>
    <td><input type="number" min="0" step="0.01" oninput="calculateGrandTotal()" required></td>
    <td><input type="number" min="0" step="0.01" oninput="calculateGrandTotal()" required></td>
    <td class="row-total">0.00</td>
  `;
  tbody.appendChild(tr);

  // إعادة تعيين حالة الحفظ عند إضافة صف جديد
  resetSaveStatus();

  // إضافة مستمعات الأحداث للصف الجديد
  const newInputs = tr.querySelectorAll('input, textarea');
  newInputs.forEach(input => {
    input.addEventListener('input', resetSaveStatus);
    input.addEventListener('change', resetSaveStatus);
  });
}

function calculateGrandTotal() {
  const tbody = document.getElementById('itemsBody');
  const rows = tbody.querySelectorAll('tr');
  let grand = 0;
  rows.forEach(row => {
    const qtyEl = row.cells[4].querySelector('input');
    const priceEl = row.cells[5].querySelector('input');
    const qty = parseFloat(qtyEl && qtyEl.value || 0) || 0;
    const price = parseFloat(priceEl && priceEl.value || 0) || 0;
    const total = qty * price;
    grand += total;
    const cell = row.querySelector('.row-total');
    if (cell) cell.textContent = total.toFixed(2);
  });
  const currency = document.getElementById('currency').value;
  const sym = currency === 'USD' ? '$' : 'ل.س';
  document.getElementById('grandTotal').textContent = grand.toFixed(2) + ' ' + sym;
}

document.getElementById('currency').addEventListener('change', calculateGrandTotal);

// متغير لتتبع حالة الحفظ
let isDocumentSaved = false;

// إعادة تعيين حالة الحفظ عند تعديل النموذج
function resetSaveStatus() {
  isDocumentSaved = false;
  const printBtn = document.getElementById('printBtn');
  if (printBtn) {
    printBtn.disabled = true;
    printBtn.title = 'يجب حفظ الطلب أولاً';
  }
}

// إضافة مستمعات الأحداث لإعادة تعيين حالة الحفظ
document.addEventListener('DOMContentLoaded', function () {
  // إعادة تعيين حالة الحفظ عند تغيير أي حقل
  const inputs = document.querySelectorAll('input, textarea, select');
  inputs.forEach(input => {
    input.addEventListener('input', resetSaveStatus);
    input.addEventListener('change', resetSaveStatus);
  });
});

function printDocument() {
  if (!isDocumentSaved) {
    alert('⚠️ لا يمكن الطباعة قبل حفظ الطلب. يرجى الحفظ أولاً.');
    return;
  }
  window.print();
}

// ================== الحفظ مع التحقق ==================
function savePurchaseRequest() {
  calculateGrandTotal(); // حساب المجموع قبل الإرسال

  // عناصر الحقول الإلزامية
  const requesterEl = document.getElementById('requester');
  const departmentEl = document.getElementById('department');
  const deliveryAddressEl = document.getElementById('deliveryAddress');
  const deliveryDateEl = document.getElementById('deliveryDate');
  const projectCodeEl = document.getElementById('projectCode');

  // تحقق وجود العناصر
  if (!requesterEl || !departmentEl || !deliveryAddressEl || !deliveryDateEl || !projectCodeEl) {
    alert('⚠️ هناك عناصر مفقودة من الصفحة. تأكد من IDs.');
    return;
  }

  // قراءة القيم
  const requester = requesterEl.value.trim();
  const department = departmentEl.value.trim();
  const deliveryAddress = deliveryAddressEl.value.trim();
  const deliveryDate = deliveryDateEl.value.trim();
  const projectCode = projectCodeEl.value.trim();

  // تحقق الإلزامية
  if (!requester || !department || !deliveryAddress || !deliveryDate || !projectCode) {
    alert('⚠️ يرجى تعبئة جميع الحقول الإلزامية قبل الحفظ.');
    return;
  }

  // تحقق من وجود عناصر على الأقل
  const itemsRows = document.querySelectorAll('#itemsBody tr');
  if (itemsRows.length === 0) {
    alert('⚠️ يجب إضافة عنصر واحد على الأقل.');
    return;
  }

  // فرض البادئة PR- والتأكد من وجود لاحقة
  orderNumberInput.value = ensurePRPrefix(orderNumberInput.value.trim());
  if (orderNumberInput.value === 'PR-') {
    alert('⚠️ يجب أن يحتوي رمز الطلب على قيمة بعد "PR-". مثال: PR-20251008-0930');
    return;
  }

  const grandText = document.getElementById('grandTotal').textContent;
  const totalAmount = parseFloat(grandText.replace(/[^0-9.]/g, '')) || 0;

  // جمع بيانات جدول الموافقات
  const approvalInputs = document.querySelectorAll('.approval-input');
  const approvalData = {
    requester_name: approvalInputs[0]?.value || '',
    requester_position: approvalInputs[4]?.value || '',
    manager_name: approvalInputs[1]?.value || '',
    manager_position: approvalInputs[5]?.value || '',
    finance_name: approvalInputs[2]?.value || '',
    finance_position: approvalInputs[6]?.value || '',
    disbursement_name: approvalInputs[3]?.value || '',
    disbursement_position: approvalInputs[7]?.value || '',
    requester_date: approvalInputs[8]?.value || '',
    manager_date: approvalInputs[9]?.value || '',
    finance_date: approvalInputs[10]?.value || '',
    disbursement_date: approvalInputs[11]?.value || ''
  };

  const payload = {
    requester: requester,
    department: department,
    delivery_address: deliveryAddress,
    delivery_date: deliveryDate,
    project_code: projectCode,
    order_number: orderNumberInput.value, // يبدأ بـ PR- ومضمون
    currency: document.getElementById('currency').value,
    total_amount: totalAmount,
    approval_data: approvalData,
    items: []
  };

  console.log('🔍 Debug - approvalData:', approvalData);
  console.log('🔍 Debug - payload:', payload);

  // جمع الأصناف مع التحقق من الإلزامية
  let hasValidItem = false;
  document.querySelectorAll('#itemsBody tr').forEach((row, index) => {
    const nameEl = row.cells[1].querySelector('textarea, input');
    const specEl = row.cells[2].querySelector('textarea, input');
    const unitEl = row.cells[3].querySelector('input');

    const qtyEl = row.cells[4].querySelector('input');
    const priceEl = row.cells[5].querySelector('input');

    const name = (nameEl && nameEl.value || '').trim();
    const spec = (specEl && specEl.value || '').trim();
    const unit = (unitEl && unitEl.value || '').trim();
    const qty = parseFloat(qtyEl && qtyEl.value || 0) || 0;
    const price = parseFloat(priceEl && priceEl.value || 0) || 0;

    // تحقق من أن العنصر له بيانات
    if (name || qty || price || spec || unit) {
      // تحقق من الحقول الإلزامية للعنصر
      if (!name) {
        alert(`⚠️ يجب إدخال اسم المادة/الخدمة في الصف ${index + 1}`);
        return;
      }
      if (!unit) {
        alert(`⚠️ يجب إدخال نوع الوحدة في الصف ${index + 1}`);
        return;
      }
      if (qty <= 0) {
        alert(`⚠️ يجب إدخال كمية صحيحة في الصف ${index + 1}`);
        return;
      }
      if (price <= 0) {
        alert(`⚠️ يجب إدخال سعر صحيح في الصف ${index + 1}`);
        return;
      }

      payload.items.push({
        item_name: name,
        specification: spec,
        unit: unit,
        quantity: qty,
        price: price
      });
      hasValidItem = true;
    }
  });

  // تحقق من وجود عنصر صحيح واحد على الأقل
  if (!hasValidItem) {
    alert('⚠️ يجب إدخال عنصر واحد صحيح على الأقل مع جميع البيانات المطلوبة.');
    return;
  }

  // إرسال مع الـ token
  const token = localStorage.getItem('token');
  if (!token) {
    alert('⚠️ يجب تسجيل الدخول أولاً');
    window.location.href = 'login.html';
    return;
  }

  fetch(`${API_BASE}/requests`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  })
    .then(r => {
      if (r.status === 401) {
        alert('⚠️ انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = 'login.html';
        return;
      }
      return r.json();
    })
    .then(res => {
      if (res && res.error) {
        alert('حدث خطأ: ' + res.error);
        isDocumentSaved = false;
      }
      else if (res && res.id) {
        alert('✅ تم الحفظ بنجاح. رقم المعرف: ' + res.id);
        isDocumentSaved = true;
        const printBtn = document.getElementById('printBtn');
        if (printBtn) {
          printBtn.disabled = false;
          printBtn.title = '';
        }
      }
      else {
        alert('❌ حدث خطأ غير متوقع');
        isDocumentSaved = false;
      }
    })
    .catch(err => alert('خطأ اتصال بالخادم: ' + err));
}

// (اختياري) عرض كل الطلبات
function loadAll() {
  fetch(`${API_BASE}/requests`)
    .then(r => r.json())
    .then(data => {
      console.log('جميع الطلبات:', data);
      alert('تم جلب ' + data.length + ' طلبًا. افتح Console للاطلاع.');
    })
    .catch(() => alert('تعذر الجلب من الخادم'));
}
