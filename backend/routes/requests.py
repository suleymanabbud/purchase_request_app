"""
مسار إنشاء طلبات الشراء
جميع مسارات GET تُعالج حصرياً من workflow.py
"""

import logging
from flask import Blueprint, request, jsonify
from ..database import SessionLocal
from ..models import PurchaseRequest, PurchaseItem, ApprovalHistory
from ..utils.auth import require_auth_and_roles

bp = Blueprint("requests", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.route("/requests", methods=["POST"])
@require_auth_and_roles("requester", "admin", "manager")
def create_request():
    """إنشاء طلب شراء جديد"""
    payload = request.get_json(force=True, silent=True) or {}

    required = [
        "requester", "department", "delivery_address", "delivery_date",
        "project_code", "order_number", "currency", "total_amount", "items",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"حقول ناقصة: {', '.join(missing)}"}), 400

    user = getattr(request, "user", {}) or {}
    creator = (
        user.get("username")
        or user.get("name")
        or user.get("email")
        or payload.get("requester")
    )
    user_role = user.get("role")
    user_department = user.get("department")

    db = SessionLocal()
    try:
        # تحديد الـ workflow حسب دور المستخدم
        if user_role == "manager" and user_department == "تطوير الأعمال":
            # مدير تطوير الأعمال يتجاوز المدير المباشر
            status = "pending_finance"
            current_stage = "finance"
            next_role = "finance"
        else:
            # موظف عادي يحتاج موافقة المدير المباشر
            status = "pending_manager"
            current_stage = "manager"
            next_role = "manager"

        logger.info(f"طلب جديد من {creator} ({user_department}) → {status}")

        # جمع بيانات الموافقات
        approval_data = payload.get("approval_data", {})

        # إنشاء الطلب الرئيسي
        pr = PurchaseRequest(
            requester=payload["requester"],
            department=payload["department"],
            delivery_address=payload["delivery_address"],
            delivery_date=payload["delivery_date"],
            project_code=payload["project_code"],
            order_number=payload["order_number"],
            currency=payload["currency"],
            total_amount=float(payload.get("total_amount") or 0.0),
            status=status,
            current_stage=current_stage,
            next_role=next_role,
            created_by=creator,
            # بيانات جدول الموافقات
            requester_name=approval_data.get("requester_name", ""),
            requester_position=approval_data.get("requester_position", ""),
            manager_name=approval_data.get("manager_name", ""),
            manager_position=approval_data.get("manager_position", ""),
            finance_name=approval_data.get("finance_name", ""),
            finance_position=approval_data.get("finance_position", ""),
            disbursement_name=approval_data.get("disbursement_name", ""),
            disbursement_position=approval_data.get("disbursement_position", ""),
            requester_date=approval_data.get("requester_date", ""),
            manager_date=approval_data.get("manager_date", ""),
            finance_date=approval_data.get("finance_date", ""),
            disbursement_date=approval_data.get("disbursement_date", ""),
        )

        db.add(pr)
        db.flush()  # للحصول على pr.id

        # إضافة الأصناف
        items = payload.get("items") or []
        for it in items:
            qty = float(it.get("quantity") or 0.0)
            price = float(it.get("price") or 0.0)
            db.add(PurchaseItem(
                request_id=pr.id,
                item_name=it.get("item_name", ""),
                specification=it.get("specification", ""),
                unit=it.get("unit", ""),
                quantity=qty,
                price=price,
                total=qty * price,
            ))

        # تسجيل حدث الإنشاء في سجل الموافقات
        if status == "pending_finance":
            note = "تم إنشاء الطلب وتحويله إلى المدير المالي"
        else:
            note = "تم إنشاء الطلب وتحويله إلى المدير المباشر"

        db.add(ApprovalHistory(
            request_id=pr.id,
            actor_role="requester",
            actor_user=creator,
            action="create",
            note=note,
        ))

        db.commit()
        return jsonify({"message": "تم إنشاء طلب الشراء بنجاح", "id": pr.id}), 201

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        # تحسين رسائل الخطأ
        if "UNIQUE constraint failed" in error_msg or "unique constraint" in error_msg.lower():
            if "order_number" in error_msg:
                return jsonify({
                    "error": f"رقم الطلب '{payload.get('order_number', '')}' موجود مسبقاً. يرجى استخدام رقم آخر."
                }), 400
        logger.error(f"خطأ في إنشاء الطلب: {error_msg}", exc_info=True)
        return jsonify({"error": f"حدث خطأ أثناء حفظ الطلب: {error_msg}"}), 500
    finally:
        db.close()
