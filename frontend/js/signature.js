/**
 * signature.js — نظام التوقيع الإلكتروني المشترك
 * يُستدعى من: manager-dashboard, finance-dashboard, disbursement-dashboard
 *
 * يعتمد على: shared.js (apiFetch, showToast)
 */

// ==================== حالة التوقيع ====================
let signatureCanvas = null;
let signatureCtx = null;
let isDrawing = false;
let hasSignature = false;
let userSignature = null;  // base64 المحفوظ

// ==================== تحميل / حفظ ====================

/**
 * تحميل التوقيع المحفوظ من السيرفر
 */
async function loadUserSignature() {
    try {
        const res = await apiFetch('/my-signature');
        if (!res.ok) return;
        const data = await res.json();
        if (data.signature) {
            userSignature = data.signature;
            renderSignaturePreview();
        }
    } catch (e) {
        console.warn('خطأ في تحميل التوقيع:', e);
    }
}

/**
 * حفظ التوقيع في السيرفر
 */
async function saveUserSignature(signatureData) {
    try {
        const res = await apiFetch('/my-signature', {
            method: 'POST',
            body: JSON.stringify({ signature: signatureData }),
        });
        if (res.ok) {
            userSignature = signatureData;
            return true;
        }
    } catch (e) {
        console.error('خطأ في حفظ التوقيع:', e);
    }
    return false;
}

// ==================== عرض التوقيع ====================

/**
 * عرض معاينة التوقيع في الشريط الجانبي
 */
function renderSignaturePreview(containerId = 'signaturePreview') {
    const preview = document.getElementById(containerId);
    if (!preview) return;

    if (userSignature) {
        preview.innerHTML = `<img src="${userSignature}" alt="التوقيع" style="max-width:100%; max-height:100%; object-fit:contain;">`;
    } else {
        preview.innerHTML = '<span style="color:rgba(255,255,255,0.5); font-size:12px;">لا يوجد توقيع محفوظ</span>';
    }
}

// ==================== مودال التوقيع ====================

/**
 * فتح مودال التوقيع عند الموافقة
 * إذا كان التوقيع محفوظاً → يُستخدم مباشرة بدون فتح المودال
 * @param {Function} onApproveCallback — دالة تُستدعى بعد الحصول على التوقيع
 */
function showSignatureModal(onApproveCallback) {
    if (userSignature) {
        // التوقيع محفوظ → نستخدمه مباشرة
        if (typeof onApproveCallback === 'function') {
            onApproveCallback(userSignature);
        }
        return;
    }

    // فتح المودال
    const modal = document.getElementById('signatureModal');
    if (!modal) return;
    modal.style.display = 'block';
    modal.dataset.callback = onApproveCallback ? 'true' : '';
    window._signatureCallback = onApproveCallback || null;
    initSignatureCanvas();
}

/**
 * فتح المودال لتحديث التوقيع (حتى لو محفوظ)
 */
function openSignatureForUpdate() {
    const modal = document.getElementById('signatureModal');
    if (!modal) return;
    modal.style.display = 'block';
    window._signatureCallback = null;  // لا callback — مجرد تحديث
    initSignatureCanvas();
}

/**
 * إغلاق مودال التوقيع
 */
function closeSignatureModal() {
    const modal = document.getElementById('signatureModal');
    if (modal) modal.style.display = 'none';
}

// ==================== رسم التوقيع ====================

/**
 * تهيئة لوحة الرسم
 */
function initSignatureCanvas() {
    signatureCanvas = document.getElementById('signatureCanvas');
    if (!signatureCanvas) return;
    signatureCtx = signatureCanvas.getContext('2d');
    clearSignature();

    // إزالة المستمعين القدام
    signatureCanvas.replaceWith(signatureCanvas.cloneNode(true));
    signatureCanvas = document.getElementById('signatureCanvas');
    signatureCtx = signatureCanvas.getContext('2d');

    // أحداث الماوس
    signatureCanvas.addEventListener('mousedown', handleStart, { passive: false });
    signatureCanvas.addEventListener('mousemove', handleMove, { passive: false });
    signatureCanvas.addEventListener('mouseup', handleEnd, { passive: false });
    signatureCanvas.addEventListener('mouseleave', handleEnd, { passive: false });

    // أحداث اللمس
    signatureCanvas.addEventListener('touchstart', handleStart, { passive: false });
    signatureCanvas.addEventListener('touchmove', handleMove, { passive: false });
    signatureCanvas.addEventListener('touchend', handleEnd, { passive: false });
    signatureCanvas.addEventListener('touchcancel', handleEnd, { passive: false });
}

function handleStart(e) {
    e.preventDefault();
    const coords = getCoords(e);
    signatureCtx.beginPath();
    signatureCtx.moveTo(coords.x, coords.y);
    isDrawing = true;
}

function handleMove(e) {
    if (!isDrawing) return;
    e.preventDefault();
    const coords = getCoords(e);
    signatureCtx.lineTo(coords.x, coords.y);
    signatureCtx.strokeStyle = '#2c3e50';
    signatureCtx.lineWidth = 2;
    signatureCtx.lineCap = 'round';
    signatureCtx.lineJoin = 'round';
    signatureCtx.stroke();
    hasSignature = true;
}

function handleEnd(e) {
    if (e) e.preventDefault();
    if (isDrawing) signatureCtx.closePath();
    isDrawing = false;
}

/**
 * حساب إحداثيات من حدث ماوس أو لمس
 */
function getCoords(e) {
    const rect = signatureCanvas.getBoundingClientRect();
    const scaleX = signatureCanvas.width / rect.width;
    const scaleY = signatureCanvas.height / rect.height;

    let clientX, clientY;
    if (e.touches && e.touches.length > 0) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else if (e.changedTouches && e.changedTouches.length > 0) {
        clientX = e.changedTouches[0].clientX;
        clientY = e.changedTouches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }

    return {
        x: (clientX - rect.left) * scaleX,
        y: (clientY - rect.top) * scaleY,
    };
}

/**
 * مسح التوقيع
 */
function clearSignature() {
    if (!signatureCanvas || !signatureCtx) return;
    signatureCtx.clearRect(0, 0, signatureCanvas.width, signatureCanvas.height);
    hasSignature = false;
}

/**
 * تأكيد التوقيع وحفظه
 */
async function confirmApprovalWithSignature() {
    if (!signatureCanvas) {
        alert('لم يتم تهيئة لوحة التوقيع.');
        return;
    }
    if (!hasSignature) {
        alert('يرجى رسم التوقيع أولاً.');
        return;
    }

    const dataUrl = signatureCanvas.toDataURL('image/png');

    // حفظ في قاعدة البيانات
    const saved = await saveUserSignature(dataUrl);
    if (!saved) {
        alert('حدث خطأ في حفظ التوقيع. يرجى المحاولة مرة أخرى.');
        return;
    }

    renderSignaturePreview();
    closeSignatureModal();

    // استدعاء الـ callback إذا كان موجوداً
    if (typeof window._signatureCallback === 'function') {
        window._signatureCallback(dataUrl);
        window._signatureCallback = null;
    }
}

// ==================== توافقية الكود القديم ====================
function startDraw(evt) { handleStart(evt); }
function drawLine(evt) { handleMove(evt); }
function endDraw() { handleEnd(); }
function getOffset(evt) {
    const coords = getCoords(evt);
    return { offsetX: coords.x, offsetY: coords.y };
}
