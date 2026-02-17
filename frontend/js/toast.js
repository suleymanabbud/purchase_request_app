/**
 * Toast Notification System — نظام الإشعارات الاحترافي
 * يستبدل alert() بإشعارات أنيقة
 *
 * الاستخدام:
 *   showToast('تم الموافقة بنجاح', 'success');
 *   showToast('خطأ في الحفظ', 'error');
 *   showToast('تنبيه!', 'warning');
 *   showToast('معلومة', 'info');
 */

(function () {
    'use strict';

    // ── إعدادات ──
    const DEFAULTS = {
        duration: 4000,      // مدة العرض (مللي ثانية)
        maxToasts: 5,        // أقصى عدد توستات ظاهرة
    };

    const ICONS = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ',
    };

    const TITLES = {
        success: 'تم بنجاح',
        error: 'خطأ',
        warning: 'تنبيه',
        info: 'معلومة',
    };

    // ── إنشاء الحاوية ──
    function getContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    // ── إنشاء عنصر التوست ──
    function createToastElement(message, type, duration) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        toast.innerHTML = `
            <div class="toast-icon">${ICONS[type] || ICONS.info}</div>
            <div class="toast-body">
                <div class="toast-title">${TITLES[type] || TITLES.info}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" aria-label="إغلاق">&times;</button>
            <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
        `;

        // إغلاق يدوي
        toast.querySelector('.toast-close').addEventListener('click', () => {
            dismissToast(toast);
        });

        return toast;
    }

    // ── إخفاء التوست ──
    function dismissToast(toast) {
        if (toast.dataset.dismissed) return;
        toast.dataset.dismissed = 'true';
        toast.classList.add('toast-exit');
        clearTimeout(parseInt(toast.dataset.timerId));
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }

    // ── الدالة الرئيسية ──
    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || DEFAULTS.duration;

        const container = getContainer();

        // حد أقصى للتوستات
        while (container.children.length >= DEFAULTS.maxToasts) {
            dismissToast(container.firstElementChild);
        }

        const toast = createToastElement(message, type, duration);
        container.appendChild(toast);

        // إخفاء تلقائي
        const timerId = setTimeout(() => dismissToast(toast), duration);
        toast.dataset.timerId = timerId;

        // إيقاف المؤقت عند التمرير فوق التوست
        toast.addEventListener('mouseenter', () => {
            clearTimeout(parseInt(toast.dataset.timerId));
            const progress = toast.querySelector('.toast-progress');
            if (progress) progress.style.animationPlayState = 'paused';
        });

        toast.addEventListener('mouseleave', () => {
            const newTimerId = setTimeout(() => dismissToast(toast), 2000);
            toast.dataset.timerId = newTimerId;
            const progress = toast.querySelector('.toast-progress');
            if (progress) {
                progress.style.animationPlayState = 'running';
                progress.style.animationDuration = '2000ms';
            }
        });

        return toast;
    }

    // ── تصدير الدالة ──
    window.showToast = showToast;

    // ── استبدال alert الافتراضي ──
    window._originalAlert = window.alert;
    window.alert = function (message) {
        // تحديد النوع تلقائياً من النص
        let type = 'info';
        if (typeof message === 'string') {
            if (message.includes('خطأ') || message.includes('Error') || message.includes('✕')) {
                type = 'error';
            } else if (message.includes('تم') || message.includes('بنجاح') || message.includes('✓')) {
                type = 'success';
            } else if (message.includes('⚠') || message.includes('تنبيه') || message.includes('يجب') || message.includes('يرجى')) {
                type = 'warning';
            }
        }
        showToast(message, type);
    };
})();
