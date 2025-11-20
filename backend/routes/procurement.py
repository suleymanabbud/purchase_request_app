from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from ..database import SessionLocal
from ..models import PurchaseRequest, PurchaseItem, ApprovalHistory, User
from ..utils.auth import require_auth_and_roles
from ..utils.notifications import create_notification
from ..utils.watchers import get_request_watchers

bp = Blueprint("procurement", __name__, url_prefix="/api/procurement")


@bp.get("/requests")
@require_auth_and_roles("procurement", "admin")
def list_procurement_requests():
    status_filter = request.args.get("status")  # pending, purchased, adjusted, cancelled, completed
    db = SessionLocal()
    try:
        query = db.query(PurchaseRequest).options(joinedload(PurchaseRequest.items))
        query = query.filter(PurchaseRequest.status.in_(["pending_procurement", "completed"]))
        if status_filter:
            if status_filter == "completed":
                query = query.filter(PurchaseRequest.status == "completed")
            else:
                query = query.filter(PurchaseRequest.procurement_status == status_filter)
        requests = query.order_by(PurchaseRequest.updated_at.desc()).all()
        data = []
        for pr in requests:
            data.append(
                {
                    "id": pr.id,
                    "order_number": pr.order_number,
                    "requester": pr.requester,
                    "department": pr.department,
                    "status": pr.status,
                    "procurement_status": pr.procurement_status,
                    "procurement_note": pr.procurement_note,
                    "procurement_assigned_to": pr.procurement_assigned_to,
                    "total_amount": pr.total_amount,
                    "currency": pr.currency,
                    "delivery_date": pr.delivery_date,
                    "delivery_address": pr.delivery_address,
                    "project_code": pr.project_code,
                    "items": [
                        {
                            "id": item.id,
                            "item_name": item.item_name,
                            "specification": item.specification,
                            "unit": item.unit,
                            "quantity": item.quantity,
                            "price": item.price,
                            "total": item.total,
                        }
                        for item in pr.items
                    ],
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                }
            )
        return jsonify(data)
    finally:
        db.close()


@bp.patch("/requests/<int:req_id>")
@require_auth_and_roles("procurement", "admin")
def update_procurement_request(req_id):
    payload = request.get_json(force=True, silent=True) or {}
    new_status = payload.get("procurement_status")  # pending | purchased | adjusted | cancelled
    note = payload.get("note")
    assigned_to = payload.get("assigned_to")
    mark_completed = payload.get("mark_completed", False)
    items_payload = payload.get("items")

    if new_status and new_status not in {"pending", "purchased", "adjusted", "cancelled"}:
        return jsonify({"error": "حالة مشتريات غير صالحة"}), 400

    user = getattr(request, "user", {}) or {}
    actor_username = user.get("username")
    actor_role = user.get("role")

    db = SessionLocal()
    try:
        pr = (
            db.query(PurchaseRequest)
            .options(joinedload(PurchaseRequest.items))
            .get(req_id)
        )
        if not pr:
            return jsonify({"error": "الطلب غير موجود"}), 404
        if pr.status not in ("pending_procurement", "completed"):
            return jsonify({"error": "الطلب ليس في مرحلة المشتريات"}), 400

        changes = []

        # تحديث العناصر إن وجدت
        if isinstance(items_payload, list):
            existing_items = {item.id: item for item in pr.items}
            for item_data in items_payload:
                item_id = item_data.get("id")
                if item_id not in existing_items:
                    continue
                item = existing_items[item_id]
                updated = False
                for field in ["item_name", "specification", "unit"]:
                    if field in item_data and getattr(item, field) != item_data[field]:
                        setattr(item, field, item_data[field])
                        updated = True
                for field in ["quantity", "price"]:
                    if field in item_data:
                        value = float(item_data[field]) if item_data[field] is not None else 0.0
                        if getattr(item, field) != value:
                            setattr(item, field, value)
                            updated = True
                # تحديث المجموع إذا تغير
                new_total = (item.quantity or 0) * (item.price or 0)
                if item.total != new_total:
                    item.total = new_total
                    updated = True
                if updated:
                    changes.append(f"تعديل صنف #{item.id}")
            # تحديث المجموع الكلي
            pr.total_amount = sum(item.total or 0 for item in pr.items)

        if new_status and pr.procurement_status != new_status:
            pr.procurement_status = new_status
            changes.append(f"تغيير حالة المشتريات إلى {new_status}")

        if note:
            pr.procurement_note = note
            changes.append("تحديث ملاحظة المشتريات")

        if assigned_to:
            pr.procurement_assigned_to = assigned_to
            changes.append("تعيين المسؤول عن الطلب")

        now = datetime.utcnow()
        pr.procurement_updated_at = now

        if mark_completed or new_status == "purchased":
            pr.status = "completed"
            pr.current_stage = "done"
            pr.next_role = None
            pr.procurement_status = new_status or "purchased"
            pr.procurement_completed_at = now
            changes.append("إغلاق الطلب من قبل المشتريات")
        else:
            pr.status = "pending_procurement"
            pr.current_stage = "procurement"
            pr.next_role = "procurement"

        # سجل الحدث في سجل الموافقات
        db.add(
            ApprovalHistory(
                request_id=pr.id,
                actor_role=actor_role,
                actor_user=actor_username,
                action="procurement-update",
                note=note or "تحديث بواسطة قسم المشتريات",
            )
        )

        db.add(pr)
        db.commit()
        db.refresh(pr)

        # إرسال الإشعارات
        recipients = get_request_watchers(db, pr)
        action_type = "procurement"
        status_text = pr.procurement_status
        message = f"تم تحديث طلب الشراء #{pr.order_number} في قسم المشتريات (الحالة: {status_text})."
        if mark_completed or pr.status == "completed":
            message = f"تم إنهاء طلب الشراء #{pr.order_number} من قسم المشتريات."  # override message
        create_notification(
            db,
            request_id=pr.id,
            recipients=recipients,
            title="تحديث طلب الشراء",
            message=message,
            action_type=action_type,
            actor_username=actor_username,
            actor_role=actor_role,
            note=note,
        )
        db.commit()

        return jsonify(
            {
                "message": "تم تحديث الطلب",
                "id": pr.id,
                "status": pr.status,
                "procurement_status": pr.procurement_status,
                "total_amount": pr.total_amount,
                "changes": changes,
            }
        )
    except Exception as exc:
        db.rollback()
        return jsonify({"error": f"خطأ في تحديث الطلب: {exc}"}), 500
    finally:
        db.close()
