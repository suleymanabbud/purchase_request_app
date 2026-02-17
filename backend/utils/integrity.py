"""
فحص سلامة البيانات — يمنع رجوع الطلبات المعتمدة للحالة الأولية
يُستدعى عند تشغيل التطبيق وبعد كل migration
"""

import logging
from sqlalchemy import text
from ..database import SessionLocal

logger = logging.getLogger(__name__)

# الحالات التي تعني أن الطلب تجاوز المدير المباشر
ADVANCED_STATUSES = (
    "pending_finance", "pending_disbursement", "pending_procurement",
    "completed", "approved",
)


def verify_data_integrity():
    """
    فحص شامل لسلامة البيانات.
    يتحقق من:
    1. عدم وجود طلبات معتمدة تحولت لـ pending_manager
    2. تناسق status مع current_stage و next_role
    3. عدم وجود approved_history بدون تحديث الحالة
    
    Returns:
        dict مع نتائج الفحص
    """
    db = SessionLocal()
    results = {
        "checked": 0,
        "fixed": 0,
        "errors": [],
        "warnings": [],
    }

    try:
        # ============ فحص 1: طلبات لها سجل موافقة لكن حالتها pending_manager ============
        orphaned = db.execute(text("""
            SELECT pr.id, pr.order_number, pr.status, pr.current_stage, pr.next_role,
                   ah.action, ah.actor_role, ah.actor_user
            FROM purchase_requests pr
            INNER JOIN approval_history ah ON pr.id = ah.request_id
            WHERE pr.status = 'pending_manager'
              AND ah.action IN ('approve', 'auto-approve')
              AND ah.actor_role = 'manager'
        """)).fetchall()
        results["checked"] += 1

        for row in orphaned:
            req_id = row[0]
            order_num = row[1]
            logger.warning(
                f"⚠️ طلب #{order_num} (ID:{req_id}) حالته pending_manager "
                f"رغم وجود موافقة المدير! → يتم إصلاحه..."
            )

            # إصلاح: نقله للمرحلة الصحيحة (المالية)
            db.execute(text("""
                UPDATE purchase_requests 
                SET status = 'pending_finance', 
                    current_stage = 'finance', 
                    next_role = 'finance'
                WHERE id = :id AND status = 'pending_manager'
            """), {"id": req_id})
            results["fixed"] += 1
            results["warnings"].append(
                f"طلب #{order_num}: تم تصحيح الحالة من pending_manager → pending_finance"
            )

        # ============ فحص 2: تناسق status ↔ current_stage ↔ next_role ============
        inconsistent = db.execute(text("""
            SELECT id, order_number, status, current_stage, next_role
            FROM purchase_requests
            WHERE (status = 'pending_manager' AND current_stage != 'manager')
               OR (status = 'pending_finance' AND current_stage != 'finance')
               OR (status = 'pending_disbursement' AND current_stage != 'disbursement')
               OR (status = 'pending_procurement' AND current_stage != 'procurement')
               OR (status IN ('completed', 'approved') AND current_stage != 'done')
               OR (status = 'rejected' AND current_stage NOT IN ('done', 'rejected', 'manager', 'finance', 'disbursement'))
        """)).fetchall()
        results["checked"] += 1

        for row in inconsistent:
            req_id, order_num, status, stage, role = row
            # تصحيح current_stage و next_role بناءً على status
            corrections = {
                "pending_manager": ("manager", "manager"),
                "pending_finance": ("finance", "finance"),
                "pending_disbursement": ("disbursement", "disbursement"),
                "pending_procurement": ("procurement", "procurement"),
                "completed": ("done", None),
                "approved": ("done", None),
                "rejected": ("done", None),
            }
            if status in corrections:
                new_stage, new_role = corrections[status]
                db.execute(text("""
                    UPDATE purchase_requests 
                    SET current_stage = :stage, next_role = :role
                    WHERE id = :id
                """), {"stage": new_stage, "role": new_role, "id": req_id})
                results["fixed"] += 1
                results["warnings"].append(
                    f"طلب #{order_num}: تصحيح stage ({stage}→{new_stage}), role ({role}→{new_role})"
                )

        # ============ فحص 3: طلبات مرفوضة لكن بدون rejection_note ============
        rejected_no_note = db.execute(text("""
            SELECT pr.id, pr.order_number
            FROM purchase_requests pr
            WHERE pr.status = 'rejected' AND (pr.rejection_note IS NULL OR pr.rejection_note = '')
              AND NOT EXISTS (
                  SELECT 1 FROM approval_history ah 
                  WHERE ah.request_id = pr.id AND ah.action = 'reject' AND ah.note IS NOT NULL AND ah.note != ''
              )
        """)).fetchall()
        results["checked"] += 1

        for row in rejected_no_note:
            results["warnings"].append(f"طلب #{row[1]}: مرفوض بدون سبب!")

        if results["fixed"] > 0:
            db.commit()
            logger.info(f"✅ فحص السلامة: تم إصلاح {results['fixed']} مشكلة")
        else:
            logger.info("✅ فحص السلامة: البيانات سليمة")

        return results

    except Exception as e:
        db.rollback()
        logger.error(f"❌ خطأ في فحص السلامة: {e}", exc_info=True)
        results["errors"].append(str(e))
        return results
    finally:
        db.close()


def protect_approved_requests():
    """
    حماية الطلبات المعتمدة من التعديل العرضي.
    يُنشئ snapshot لحالات الطلبات المتقدمة لفحصها لاحقاً.
    
    Returns:
        dict مع request_id → status
    """
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, status FROM purchase_requests
            WHERE status NOT IN ('pending_manager', 'rejected')
        """)).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        logger.error(f"خطأ في حماية الطلبات: {e}")
        return {}
    finally:
        db.close()


def check_status_regression(snapshot):
    """
    التحقق من أن الطلبات المتقدمة لم ترجع لمراحل سابقة.
    Args:
        snapshot: dict من protect_approved_requests()
    Returns:
        list من الطلبات المتضررة
    """
    db = SessionLocal()
    regressions = []
    try:
        for req_id, old_status in snapshot.items():
            row = db.execute(text(
                "SELECT status FROM purchase_requests WHERE id = :id"
            ), {"id": req_id}).fetchone()

            if row and row[0] != old_status:
                # تحقق إذا الحالة الجديدة أقل من القديمة
                status_order = {
                    "pending_manager": 0,
                    "pending_finance": 1,
                    "pending_disbursement": 2,
                    "pending_procurement": 3,
                    "completed": 4,
                    "approved": 4,
                }
                old_level = status_order.get(old_status, -1)
                new_level = status_order.get(row[0], -1)

                if new_level < old_level:
                    regressions.append({
                        "id": req_id,
                        "old_status": old_status,
                        "new_status": row[0],
                    })
                    logger.error(
                        f"🚨 تراجع حالة الطلب #{req_id}: {old_status} → {row[0]}!"
                    )
                    # إصلاح تلقائي: إعادة الحالة القديمة
                    db.execute(text(
                        "UPDATE purchase_requests SET status = :status WHERE id = :id"
                    ), {"status": old_status, "id": req_id})

        if regressions:
            db.commit()
            logger.warning(f"🛡️ تم حماية {len(regressions)} طلب من تراجع الحالة")

        return regressions
    except Exception as e:
        db.rollback()
        logger.error(f"خطأ في فحص التراجع: {e}")
        return regressions
    finally:
        db.close()
