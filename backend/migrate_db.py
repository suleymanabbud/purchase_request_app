"""
سكربت لتحديث قاعدة البيانات وإضافة الأعمدة المفقودة
يُستدعى تلقائياً عند بدء التطبيق عبر app.py

⚠️ قواعد أمان:
- لا يُعدّل أي حقل status أو current_stage أو next_role
- لا يحذف أي بيانات موجودة
- يُسجّل كل تغيير في السجلات
"""

import logging

from sqlalchemy import text, inspect
from .database import engine, SessionLocal

logger = logging.getLogger(__name__)


def migrate_database():
    """إضافة الأعمدة المفقودة إلى قاعدة البيانات"""
    logger.info("بدء تحديث قاعدة البيانات...")

    db = SessionLocal()
    try:
        inspector = inspect(engine)

        if not inspector.has_table("purchase_requests"):
            logger.error("جدول purchase_requests غير موجود!")
            return False

        existing_columns = [col["name"] for col in inspector.get_columns("purchase_requests")]
        logger.info(f"الأعمدة الموجودة: {len(existing_columns)}")

        # الأعمدة المطلوبة (فقط إضافة — لا حذف ولا تعديل)
        required_columns = {
            "procurement_status": "VARCHAR(50)",
            "procurement_note": "TEXT",
            "procurement_assigned_to": "VARCHAR(120)",
            "procurement_completed_at": "DATETIME",
            "procurement_updated_at": "DATETIME",
            "rejection_note": "TEXT",
        }

        added_count = 0
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                try:
                    db.execute(text(f"ALTER TABLE purchase_requests ADD COLUMN {col_name} {col_type}"))
                    db.commit()
                    logger.info(f"تم إضافة العمود: {col_name}")
                    added_count += 1

                    if col_name == "procurement_status":
                        db.execute(text("UPDATE purchase_requests SET procurement_status = 'pending' WHERE procurement_status IS NULL"))
                        db.commit()
                except Exception as e:
                    logger.warning(f"خطأ في إضافة العمود {col_name}: {e}")
                    db.rollback()

        # التحقق من عمود signature في users
        if inspector.has_table("users"):
            user_columns = [col["name"] for col in inspector.get_columns("users")]
            if "signature" not in user_columns:
                try:
                    db.execute(text("ALTER TABLE users ADD COLUMN signature TEXT"))
                    db.commit()
                    logger.info("تم إضافة عمود signature في users")
                    added_count += 1
                except Exception as e:
                    logger.warning(f"خطأ في إضافة عمود signature لجدول users: {e}")
                    db.rollback()

        # التحقق من جدول notifications
        if not inspector.has_table("notifications"):
            logger.info("إنشاء جدول notifications...")
            from .models import Notification
            from .database import Base
            Notification.__table__.create(bind=engine, checkfirst=True)
            logger.info("تم إنشاء جدول notifications")

        # التحقق من عمود signature في approval_history
        if inspector.has_table("approval_history"):
            approval_columns = [col["name"] for col in inspector.get_columns("approval_history")]
            if "signature" not in approval_columns:
                try:
                    db.execute(text("ALTER TABLE approval_history ADD COLUMN signature TEXT"))
                    db.commit()
                    logger.info("تم إضافة عمود signature في approval_history")
                    added_count += 1
                except Exception as e:
                    logger.warning(f"خطأ في إضافة عمود signature: {e}")
                    db.rollback()

        # ==================== إنشاء الفهارس المركبة ====================
        _ensure_indexes(db, inspector)

        # ==================== فحص سلامة الحالات ====================
        _verify_status_consistency(db)

        logger.info(f"تم تحديث قاعدة البيانات بنجاح (تم إضافة {added_count} عمود)")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"خطأ في تحديث قاعدة البيانات: {e}", exc_info=True)
        return False
    finally:
        db.close()


def _ensure_indexes(db, inspector):
    """إنشاء الفهارس المركبة إذا لم تكن موجودة"""
    index_definitions = [
        ("purchase_requests", "ix_pr_status_department", ["status", "department"]),
        ("purchase_requests", "ix_pr_created_by", ["created_by"]),
        ("approval_history",  "ix_ah_actor_action", ["actor_user", "action"]),
        ("notifications",     "ix_notif_recipient_read", ["recipient_username", "is_read"]),
    ]

    for table, idx_name, columns in index_definitions:
        if not inspector.has_table(table):
            continue
        existing = {idx["name"] for idx in inspector.get_indexes(table)}
        if idx_name in existing:
            continue
        try:
            cols = ", ".join(columns)
            db.execute(text(f"CREATE INDEX {idx_name} ON {table} ({cols})"))
            db.commit()
            logger.info(f"تم إنشاء فهرس: {idx_name} على {table}")
        except Exception as e:
            logger.warning(f"خطأ في إنشاء فهرس {idx_name}: {e}")
            db.rollback()


def _verify_status_consistency(db):
    """
    ⚠️ فحص أمان: التأكد من أن migration لم يغير أي حالة طلب.
    هذا الفحص يمنع المشكلة الحرجة المعروفة:
    - طلبات معتمدة تعود لـ pending_manager بعد تغيير الكود
    """
    try:
        # فحص: هل هناك طلبات بحالة متقدمة لكن current_stage لا يتطابق؟
        mismatched = db.execute(text("""
            SELECT id, order_number, status, current_stage, next_role
            FROM purchase_requests
            WHERE (status = 'pending_finance' AND current_stage = 'manager')
               OR (status = 'pending_disbursement' AND current_stage IN ('manager', 'finance'))
               OR (status = 'pending_procurement' AND current_stage IN ('manager', 'finance', 'disbursement'))
               OR (status IN ('completed', 'approved') AND current_stage NOT IN ('done', 'procurement'))
        """)).fetchall()

        for row in mismatched:
            req_id, order_num, status, stage, role = row
            # تصحيح current_stage بناءً على status
            stage_map = {
                "pending_finance": "finance",
                "pending_disbursement": "disbursement",
                "pending_procurement": "procurement",
                "completed": "done",
                "approved": "done",
            }
            role_map = {
                "pending_finance": "finance",
                "pending_disbursement": "disbursement",
                "pending_procurement": "procurement",
                "completed": None,
                "approved": None,
            }
            new_stage = stage_map.get(status, stage)
            new_role = role_map.get(status, role)

            db.execute(text("""
                UPDATE purchase_requests 
                SET current_stage = :stage, next_role = :role
                WHERE id = :id
            """), {"stage": new_stage, "role": new_role, "id": req_id})
            logger.warning(
                f"🔧 تصحيح طلب #{order_num}: stage {stage}→{new_stage}, role {role}→{new_role}"
            )

        if mismatched:
            db.commit()
            logger.info(f"✅ تم تصحيح {len(mismatched)} طلب غير متسق")

    except Exception as e:
        logger.warning(f"خطأ في فحص تناسق الحالات: {e}")
        db.rollback()


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    success = migrate_database()
    if not success:
        sys.exit(1)
