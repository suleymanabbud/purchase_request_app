"""
نظام النسخ الاحتياطي التلقائي لقاعدة البيانات
يُنشئ نسخة احتياطية قبل أي migration أو تغيير هيكلي
"""

import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# مجلد النسخ الاحتياطية
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, "database", "backups")
DB_FILE = os.path.join(BASE_DIR, "database", "purchase_requests.db")

# أقصى عدد نسخ احتياطية للحفاظ على المساحة
MAX_BACKUPS = 20


def backup_database(reason="auto"):
    """
    إنشاء نسخة احتياطية من قاعدة البيانات.
    Args:
        reason: سبب النسخ (مثل: migration, manual, startup)
    Returns:
        مسار الملف الاحتياطي أو None في حالة الفشل
    """
    if not os.path.exists(DB_FILE):
        logger.warning("ملف قاعدة البيانات غير موجود — لا حاجة لنسخ احتياطي")
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"purchase_requests_{reason}_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    try:
        shutil.copy2(DB_FILE, backup_path)
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        logger.info(f"✅ نسخة احتياطية: {backup_name} ({size_mb:.2f} MB)")

        # تنظيف النسخ القديمة
        _cleanup_old_backups()

        return backup_path
    except Exception as e:
        logger.error(f"❌ فشل النسخ الاحتياطي: {e}")
        return None


def restore_database(backup_path):
    """
    استعادة قاعدة البيانات من نسخة احتياطية.
    Args:
        backup_path: مسار ملف النسخة الاحتياطية
    Returns:
        True إذا نجحت الاستعادة
    """
    if not os.path.exists(backup_path):
        logger.error(f"ملف النسخة الاحتياطية غير موجود: {backup_path}")
        return False

    try:
        # نسخة احتياطية من الحالة الحالية قبل الاستعادة
        backup_database("pre_restore")

        shutil.copy2(backup_path, DB_FILE)
        logger.info(f"✅ تم استعادة قاعدة البيانات من: {os.path.basename(backup_path)}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل الاستعادة: {e}")
        return False


def list_backups():
    """إرجاع قائمة النسخ الاحتياطية المتوفرة"""
    if not os.path.exists(BACKUP_DIR):
        return []

    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            path = os.path.join(BACKUP_DIR, f)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            backups.append({
                "name": f,
                "path": path,
                "size_mb": round(size_mb, 2),
                "created": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            })
    return backups


def _cleanup_old_backups():
    """حذف النسخ الاحتياطية القديمة (الاحتفاظ بآخر MAX_BACKUPS)"""
    if not os.path.exists(BACKUP_DIR):
        return

    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
        key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)),
        reverse=True,
    )

    for old_file in backups[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old_file))
            logger.info(f"🗑️ حذف نسخة قديمة: {old_file}")
        except Exception:
            pass
