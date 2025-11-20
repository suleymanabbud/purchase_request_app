'use strict';

const currentHost = window.location.hostname;
const API_BASE = `http://${currentHost}:5000/api`;

let allRequests = [];
let filteredRequests = [];
let currentRequest = null;
let currentListMode = 'pending'; // pending | completed
let notifications = [];

const elements = {
    tableBody: document.getElementById('requestsTableBody'),
    statusFilter: document.getElementById('statusFilter'),
    searchInput: document.getElementById('searchInput'),
    statPending: document.getElementById('statPending'),
    statAdjusted: document.getElementById('statAdjusted'),
    statCompleted: document.getElementById('statCompleted'),
    statCancelled: document.getElementById('statCancelled'),
    btnRefresh: document.getElementById('btnRefresh'),
    btnLogout: document.getElementById('btnLogout'),
    btnNotifications: document.getElementById('btnNotifications'),
    notifCount: document.getElementById('notifCount'),
    notificationsPanel: document.getElementById('notificationsPanel'),
    notificationsList: document.getElementById('notificationsList'),
    btnMarkAllRead: document.getElementById('btnMarkAllRead'),
    menuPending: document.getElementById('menuPending'),
    menuCompleted: document.getElementById('menuCompleted'),
    modal: document.getElementById('requestModal'),
    modalTitle: document.getElementById('modalTitle'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    detailGrid: document.getElementById('detailGrid'),
    itemsTable: document.getElementById('itemsTable'),
    procurementNote: document.getElementById('procurementNote'),
    btnSaveChanges: document.getElementById('btnSaveChanges'),
    btnMarkPurchased: document.getElementById('btnMarkPurchased'),
    btnCancelRequest: document.getElementById('btnCancelRequest'),
};

function checkAuth() {
    const token = localStorage.getItem('token');
    const userRaw = localStorage.getItem('user');
    if (!token || !userRaw) {
        window.location.href = 'login.html';
        return;
    }
    try {
        const user = JSON.parse(userRaw);
        if (user.role !== 'procurement' && user.role !== 'admin') {
            window.location.href = 'login.html';
        }
    } catch (err) {
        console.warn('Failed to parse user payload', err);
        window.location.href = 'login.html';
    }
}

async function loadRequests() {
    try {
        const params = new URLSearchParams();
        if (currentListMode === 'completed') {
            params.set('status', 'completed');
        }
        const response = await fetch(`${API_BASE}/procurement/requests?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        });
        if (!response.ok) {
            if (response.status === 401) {
                logout();
            }
            throw new Error('تعذر جلب الطلبات');
        }
        allRequests = await response.json();
        applyFilters();
        updateStats();
    } catch (error) {
        console.error('Error loading procurement requests:', error);
        alert('حدث خطأ أثناء جلب طلبات المشتريات');
    }
}

function applyFilters() {
    const statusValue = elements.statusFilter.value;
    const search = elements.searchInput.value.trim().toLowerCase();
    filteredRequests = allRequests.filter((req) => {
        const matchesStatus = !statusValue
            ? true
            : (statusValue === 'completed'
                ? req.status === 'completed'
                : req.procurement_status === statusValue);
        const matchesSearch = !search
            || (req.order_number && req.order_number.toLowerCase().includes(search))
            || (req.requester && req.requester.toLowerCase().includes(search));
        return matchesStatus && matchesSearch;
    });
    renderRequestsTable();
}

function renderRequestsTable() {
    elements.tableBody.innerHTML = '';
    if (!filteredRequests.length) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="6">لا توجد طلبات في هذه القائمة.</td>`;
        elements.tableBody.appendChild(row);
        return;
    }
    filteredRequests.forEach((req) => {
        const row = document.createElement('tr');
        const statusChip = getStatusChip(req);
        row.innerHTML = `
            <td>${req.order_number || req.id}</td>
            <td>${req.requester || '-'}</td>
            <td>${req.department || '-'}</td>
            <td>${formatCurrency(req.total_amount, req.currency)}</td>
            <td>${statusChip}</td>
            <td>
                <button class="action-btn btn-view" data-id="${req.id}"><i class="fas fa-edit"></i> إدارة</button>
            </td>
        `;
        elements.tableBody.appendChild(row);
    });
}

function getStatusChip(req) {
    const status = req.procurement_status || 'pending';
    const map = {
        pending: { text: 'قيد المعالجة', cls: 'status-pending', icon: 'fa-clock' },
        adjusted: { text: 'تم التعديل', cls: 'status-adjusted', icon: 'fa-sync' },
        purchased: { text: 'تم الشراء', cls: 'status-purchased', icon: 'fa-check' },
        cancelled: { text: 'ملغى', cls: 'status-cancelled', icon: 'fa-ban' },
    };
    const meta = map[status] || map.pending;
    return `<span class="status-chip ${meta.cls}"><i class="fas ${meta.icon}"></i> ${meta.text}</span>`;
}

function updateStats() {
    const pending = allRequests.filter((r) => r.procurement_status === 'pending' && r.status !== 'completed').length;
    const adjusted = allRequests.filter((r) => r.procurement_status === 'adjusted').length;
    const completed = allRequests.filter((r) => r.status === 'completed').length;
    const cancelled = allRequests.filter((r) => r.procurement_status === 'cancelled').length;
    elements.statPending.textContent = pending;
    elements.statAdjusted.textContent = adjusted;
    elements.statCompleted.textContent = completed;
    elements.statCancelled.textContent = cancelled;
}

function formatCurrency(value, currency) {
    if (!value) return '0';
    if (currency === 'USD') {
        return `$${Number(value).toFixed(2)}`;
    }
    return `${Number(value).toLocaleString()} ل.س`;
}

function bindTableEvents() {
    elements.tableBody.addEventListener('click', (event) => {
        const actionBtn = event.target.closest('button[data-id]');
        if (!actionBtn) return;
        const id = Number(actionBtn.dataset.id);
        const request = allRequests.find((r) => r.id === id);
        if (!request) return;
        openModal(request);
    });
}

function openModal(request) {
    currentRequest = structuredClone(request);
    elements.modalTitle.textContent = `تفاصيل الطلب #${request.order_number || request.id}`;
    renderDetailGrid(request);
    renderItemsTable(request);
    elements.procurementNote.value = request.procurement_note || '';
    elements.modal.classList.add('active');
}

function closeModal() {
    elements.modal.classList.remove('active');
    currentRequest = null;
    elements.procurementNote.value = '';
}

function renderDetailGrid(request) {
    const fields = [
        { label: 'مقدم الطلب', value: request.requester },
        { label: 'القسم', value: request.department },
        { label: 'التاريخ', value: request.created_at ? new Date(request.created_at).toLocaleDateString('ar-SA') : '-' },
        { label: 'موعد التسليم', value: request.delivery_date || '-' },
        { label: 'عنوان التسليم', value: request.delivery_address || '-' },
        { label: 'رمز المشروع', value: request.project_code || '-' },
        { label: 'المبلغ الإجمالي', value: formatCurrency(request.total_amount, request.currency) },
        { label: 'حالة المشتريات', value: getStatusChip(request) },
    ];
    elements.detailGrid.innerHTML = fields.map(({ label, value }) => `
        <div class="detail-box">
            <div class="detail-label">${label}</div>
            <div class="detail-value">${value || '-'}</div>
        </div>
    `).join('');
}

function renderItemsTable(request) {
    const tbody = elements.itemsTable.querySelector('tbody');
    tbody.innerHTML = '';
    (request.items || []).forEach((item, index) => {
        const row = document.createElement('tr');
        row.dataset.id = item.id;
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><input type="text" class="input-item-name" value="${item.item_name || ''}"></td>
            <td><input type="text" class="input-spec" value="${item.specification || ''}"></td>
            <td><input type="text" class="input-unit" value="${item.unit || ''}"></td>
            <td><input type="number" class="input-qty" min="0" step="0.01" value="${item.quantity ?? 0}"></td>
            <td><input type="number" class="input-price" min="0" step="0.01" value="${item.price ?? 0}"></td>
            <td class="row-total">${Number(item.total || 0).toFixed(2)}</td>
        `;
        tbody.appendChild(row);
    });
    tbody.querySelectorAll('.input-qty, .input-price').forEach((input) => {
        input.addEventListener('input', handleItemChange);
    });
    tbody.querySelectorAll('.input-item-name, .input-spec, .input-unit').forEach((input) => {
        input.addEventListener('input', markRowDirty);
    });
}

function markRowDirty(event) {
    const row = event.target.closest('tr');
    if (row) {
        row.dataset.dirty = 'true';
    }
}

function handleItemChange(event) {
    const row = event.target.closest('tr');
    if (!row) return;
    const qty = Number(row.querySelector('.input-qty').value) || 0;
    const price = Number(row.querySelector('.input-price').value) || 0;
    const total = qty * price;
    row.querySelector('.row-total').textContent = total.toFixed(2);
    row.dataset.dirty = 'true';
}

function collectItemsPayload() {
    const rows = elements.itemsTable.querySelectorAll('tbody tr');
    const items = [];
    rows.forEach((row) => {
        const itemId = Number(row.dataset.id);
        items.push({
            id: itemId,
            item_name: row.querySelector('.input-item-name').value.trim(),
            specification: row.querySelector('.input-spec').value.trim(),
            unit: row.querySelector('.input-unit').value.trim(),
            quantity: Number(row.querySelector('.input-qty').value) || 0,
            price: Number(row.querySelector('.input-price').value) || 0,
        });
    });
    return items;
}

function getNoteValue() {
    return elements.procurementNote.value.trim();
}

async function updateRequest(payload) {
    if (!currentRequest) return;
    try {
        const response = await fetch(`${API_BASE}/procurement/requests/${currentRequest.id}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'فشل تحديث الطلب');
        }
        alert(data.message || 'تم حفظ التعديلات');
        closeModal();
        await loadRequests();
        await loadNotifications(true);
    } catch (error) {
        console.error('Error updating procurement request:', error);
        alert(error.message || 'حدث خطأ أثناء حفظ التعديلات');
    }
}

function validateNote(note) {
    if (!note) {
        alert('يرجى إدخال ملاحظة تشرح التعديل أو سبب الإجراء.');
        return false;
    }
    return true;
}

async function handleSaveChanges() {
    const note = getNoteValue();
    if (!validateNote(note)) return;
    const items = collectItemsPayload();
    await updateRequest({
        procurement_status: 'adjusted',
        note,
        items,
        assigned_to: getCurrentUsername(),
    });
}

async function handleMarkPurchased() {
    const note = getNoteValue();
    if (!validateNote(note)) return;
    const items = collectItemsPayload();
    await updateRequest({
        procurement_status: 'purchased',
        note,
        items,
        mark_completed: true,
        assigned_to: getCurrentUsername(),
    });
}

async function handleCancelRequest() {
    if (!currentRequest) return;
    const confirmCancel = confirm('هل أنت متأكد من إلغاء هذا الطلب؟');
    if (!confirmCancel) return;
    const note = getNoteValue();
    if (!validateNote(note)) return;
    await updateRequest({
        procurement_status: 'cancelled',
        note,
        mark_completed: true,
        assigned_to: getCurrentUsername(),
    });
}

function getCurrentUsername() {
    try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.username || null;
    } catch (err) {
        return null;
    }
}

function bindModalActions() {
    elements.modalCloseBtn.addEventListener('click', closeModal);
    elements.btnSaveChanges.addEventListener('click', handleSaveChanges);
    elements.btnMarkPurchased.addEventListener('click', handleMarkPurchased);
    elements.btnCancelRequest.addEventListener('click', handleCancelRequest);
    elements.modal.addEventListener('click', (event) => {
        if (event.target === elements.modal) {
            closeModal();
        }
    });
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}

function bindLayoutActions() {
    elements.btnRefresh.addEventListener('click', () => {
        loadRequests();
        loadNotifications(true);
    });
    elements.btnLogout.addEventListener('click', logout);
    elements.btnNotifications.addEventListener('click', toggleNotificationsPanel);
    elements.btnMarkAllRead.addEventListener('click', markAllNotificationsRead);
    elements.searchInput.addEventListener('input', applyFilters);
    elements.statusFilter.addEventListener('change', applyFilters);
    elements.menuPending.addEventListener('click', (event) => {
        event.preventDefault();
        currentListMode = 'pending';
        setMenuActive(elements.menuPending);
        loadRequests();
    });
    elements.menuCompleted.addEventListener('click', (event) => {
        event.preventDefault();
        currentListMode = 'completed';
        setMenuActive(elements.menuCompleted);
        loadRequests();
    });
}

function setMenuActive(activeEl) {
    [elements.menuPending, elements.menuCompleted].forEach((el) => {
        el.classList.toggle('active', el === activeEl);
    });
}

async function loadNotifications(silent = false) {
    try {
        const response = await fetch(`${API_BASE}/notifications`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        });
        if (!response.ok) return;
        notifications = await response.json();
        renderNotifications();
    } catch (error) {
        if (!silent) {
            console.warn('Failed to load notifications', error);
        }
    }
}

function renderNotifications() {
    const unreadCount = notifications.filter((n) => !n.is_read).length;
    if (unreadCount > 0) {
        elements.notifCount.textContent = String(unreadCount);
        elements.notifCount.style.display = 'flex';
    } else {
        elements.notifCount.style.display = 'none';
    }
    if (!notifications.length) {
        elements.notificationsList.innerHTML = '<li>لا توجد إشعارات حالياً.</li>';
        return;
    }
    elements.notificationsList.innerHTML = notifications.map((notif) => `
        <li class="${notif.is_read ? '' : 'unread'}">
            <strong>${notif.title}</strong>
            <div>${notif.message}</div>
            ${notif.note ? `<small>ملاحظة: ${notif.note}</small>` : ''}
            <small>${notif.created_at ? new Date(notif.created_at).toLocaleString('ar-SA') : ''}</small>
        </li>
    `).join('');
}

function toggleNotificationsPanel() {
    elements.notificationsPanel.classList.toggle('active');
    if (elements.notificationsPanel.classList.contains('active')) {
        elements.notificationsPanel.focus();
    }
}

async function markAllNotificationsRead() {
    try {
        const response = await fetch(`${API_BASE}/notifications/read-all`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        });
        if (response.ok) {
            await loadNotifications(true);
        }
    } catch (error) {
        console.warn('Failed to mark notifications read', error);
    }
}

function registerGlobalHandlers() {
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (elements.modal.classList.contains('active')) {
                closeModal();
            } else if (elements.notificationsPanel.classList.contains('active')) {
                elements.notificationsPanel.classList.remove('active');
            }
        }
    });
    document.addEventListener('click', (event) => {
        if (!elements.notificationsPanel.contains(event.target) && !elements.btnNotifications.contains(event.target)) {
            elements.notificationsPanel.classList.remove('active');
        }
    });
}

function init() {
    checkAuth();
    bindLayoutActions();
    bindTableEvents();
    bindModalActions();
    registerGlobalHandlers();
    setMenuActive(elements.menuPending);
    loadRequests();
    loadNotifications(true);
}

document.addEventListener('DOMContentLoaded', init);



