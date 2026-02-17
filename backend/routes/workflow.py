import logging
from flask import Blueprint, request, jsonify
from ..utils.auth import require_roles, require_auth, require_auth_and_roles
from ..database import SessionLocal
from ..models import PurchaseRequest, PurchaseItem, ApprovalHistory, User
from ..utils.notifications import create_notification
from ..utils.watchers import get_request_watchers
from ..services.workflow_service import (
    WORKFLOW_TRANSITIONS, STATUS_TO_REQUIRED_ROLE, STATUS_TO_SIGNATURE_FIELDS,
    STATUS_TO_HISTORY_ROLE, STATUS_TO_STAGE_ROLE,
    sync_status_fields as _sync_status_fields,
    get_effective_role, can_act_on_request,
    auto_skip_if_same_approver as _auto_skip_if_same_approver,
)
from datetime import datetime, timezone

bp = Blueprint("workflow", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


# ==================== أدوات تحويل البيانات ====================

def _serialize_request_summary(r):
    """تحويل PurchaseRequest إلى dict مختصر (للقوائم)"""
    return {
        "id": r.id,
        "order_number": r.order_number,
        "requester": r.requester,
        "department": r.department,
        "status": r.status or "pending_manager",
        "current_stage": r.current_stage,
        "next_role": r.next_role,
        "total_amount": float(r.total_amount or 0.0),
        "currency": r.currency or "SYP",
        "created_by": r.created_by,
        "date": str(r.created_at.date()) if r.created_at else "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "delivery_date": r.delivery_date or "",
        "delivery_address": r.delivery_address,
        "project_code": r.project_code,
    }


def _serialize_item(it):
    """تحويل PurchaseItem إلى dict"""
    return {
        "id": it.id, "item_name": it.item_name,
        "specification": it.specification, "unit": it.unit,
        "quantity": it.quantity, "price": it.price, "total": it.total,
        "status": it.status or "pending",
        "rejection_reason": it.rejection_reason,
        "rejected_by": it.rejected_by,
    }


# ==================== دالة إعادة تهيئة القاعدة ====================

@bp.post("/admin/reset-db")
@require_auth_and_roles("admin")
def reset_db():
    """حذف جميع الطلبات (للاستخدام الإداري فقط)"""
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("confirm") or data.get("password") != "DELETE_ALL_DATA":
        return jsonify({"error": "يتطلب تأكيد الحذف", "message": 'أرسل {"confirm": true, "password": "DELETE_ALL_DATA"}'}), 400
    
    db = SessionLocal()
    try:
        db.query(ApprovalHistory).delete()
        db.query(PurchaseItem).delete()
        db.query(PurchaseRequest).delete()
        db.commit()
        return jsonify({"message": "تم حذف جميع الطلبات بنجاح"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ==================== قائمة الطلبات ====================

@bp.get("/requests")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement")
def list_requests():
    status = request.args.get("status")
    dept = request.args.get("department")
    db = SessionLocal()
    try:
        user = getattr(request, "user", {}) or {}
        user_role = user.get("role")
        user_dept = user.get("department")
        
        q = db.query(PurchaseRequest)
        if status:
            q = q.filter(PurchaseRequest.status == status)
        if dept:
            q = q.filter(PurchaseRequest.department == dept)
        elif user_role != "admin" and user_dept:
            q = q.filter(PurchaseRequest.department == user_dept)
        
        results = q.order_by(PurchaseRequest.id.desc()).all()
        return jsonify([_serialize_request_summary(r) for r in results])
    finally:
        db.close()


# ==================== تحديث حالة الطلب ====================

@bp.patch("/requests/<int:req_id>/status")
@require_auth_and_roles("admin","manager","finance","disbursement")
def update_status(req_id):
    """تحديث حالة طلب: موافقة أو رفض"""
    data = request.get_json(force=True, silent=True) or {}
    action = (data.get("action") or "").lower()
    note = data.get("note")
    signature = data.get("signature")

    if action not in ("approve", "reject"):
        return jsonify({"error": "إجراء غير صحيح"}), 400

    if action == "reject" and not (note and note.strip()):
        return jsonify({"error": "يجب إضافة ملاحظة توضح سبب الرفض"}), 400

    user = getattr(request, "user", {}) or {}
    actor_role = user.get("role")
    actor_user = user.get("username") or user.get("name") or user.get("email")

    db = SessionLocal()
    try:
        pr = db.get(PurchaseRequest, req_id)
        if not pr:
            return jsonify({"error": "الطلب غير موجود"}), 404

        current = pr.status or "pending_manager"

        # فحص الصلاحيات
        allowed, result = can_act_on_request(actor_user, actor_role, pr, db)
        if not allowed:
            return jsonify({"error": result}), 403
        effective_role = result

        logger.info(f"تحديث الطلب {pr.id}: {actor_user} ({effective_role}) → {action}")

        # جلب اسم المستخدم الكامل
        approver_user = db.query(User).filter(User.username == actor_user).first()
        user_full_name = (approver_user.full_name if approver_user else None) or actor_user
        today_str = datetime.now().strftime('%Y-%m-%d')

        # حفظ بيانات الموافقة
        if action == "approve":
            fields = STATUS_TO_SIGNATURE_FIELDS.get(current)
            if fields:
                setattr(pr, fields["name"], user_full_name)
                setattr(pr, fields["date"], today_str)
                setattr(pr, fields["sig"], signature)

        # تسجيل في سجل الموافقات
        history_role = STATUS_TO_HISTORY_ROLE.get(current, effective_role)
        db.add(ApprovalHistory(
            request_id=pr.id,
            actor_role=history_role,
            actor_user=actor_user,
            action=action,
            note=note,
            signature=signature
        ))

        if action == "reject":
            pr.status = "rejected"
            pr.rejection_note = note
            _sync_status_fields(pr)
        else:  # approve
            transition = WORKFLOW_TRANSITIONS.get(current)
            if transition:
                pr.status = transition["next_status"]
                _sync_status_fields(pr)
                
                if pr.status == "pending_procurement":
                    pr.procurement_status = pr.procurement_status or "pending"
                
                # === Auto-Skip: تخطي المرحلة إذا المعتمد التالي هو نفس الشخص ===
                pr = _auto_skip_if_same_approver(db, pr, actor_user, signature, today_str)


        db.add(pr)
        db.commit()
        db.refresh(pr)

        # إرسال الإشعارات
        _send_status_notification(db, pr, actor_user, actor_role, note)
        db.commit()

        return jsonify({
            "id": pr.id,
            "status": pr.status,
            "current_stage": pr.current_stage,
            "next_role": pr.next_role,
            "message": "تم تحديث الطلب بنجاح",
            "total": None,
            "approved": None,
            "rejected": None
        })
    except Exception as e:
        db.rollback()
        logger.error(f"خطأ في تحديث الطلب {req_id}: {e}")
        return jsonify({"error": f"خطأ في تحديث الحالة: {str(e)}"}), 500
    finally:
        db.close()





def _send_status_notification(db, pr, actor_user, actor_role, note):
    """إرسال إشعار بتحديث حالة الطلب"""
    try:
        recipients = get_request_watchers(db, pr)
        if actor_role == "requester":
            recipients = [pr.created_by] if pr.created_by else []
        
        if pr.status == "rejected":
            action_type = "reject"
            message = f"تم رفض طلب الشراء #{pr.order_number} بواسطة {actor_user}."
            if note:
                message += f" السبب: {note}"
        elif pr.status == "pending_procurement":
            action_type = "procurement"
            message = f"تم تحويل طلب الشراء #{pr.order_number} إلى قسم المشتريات."
        elif pr.status == "completed":
            action_type = "approve"
            message = f"تم إكمال طلب الشراء #{pr.order_number}."
        else:
            action_type = "approve"
            message = f"تمت الموافقة على طلب الشراء #{pr.order_number} من قبل {actor_user}."

        create_notification(
            db, request_id=pr.id, recipients=recipients,
            title="تحديث حالة طلب الشراء", message=message,
            action_type=action_type, actor_username=actor_user,
            actor_role=actor_role, note=note,
        )
    except Exception as e:
        logger.warning(f"فشل إرسال الإشعار: {e}")


# ==================== تفاصيل الطلب ====================

@bp.get("/requests/<int:req_id>")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement","requester")
def get_request_details(req_id):
    db = SessionLocal()
    try:
        pr = db.get(PurchaseRequest, req_id)
        if not pr:
            return jsonify({"error": "الطلب غير موجود"}), 404
        
        items = [{
            "id": item.id, "item_name": item.item_name,
            "specification": item.specification, "unit": item.unit,
            "quantity": item.quantity, "price": item.price,
            "total": item.total, "status": item.status or "pending",
            "rejection_reason": item.rejection_reason,
            "rejected_by": item.rejected_by
        } for item in pr.items]
        
        approval_dates = {}
        histories = db.query(ApprovalHistory).filter(
            ApprovalHistory.request_id == req_id,
            ApprovalHistory.action.in_(["approve", "auto-approve"])
        ).order_by(ApprovalHistory.created_at.desc()).all()
        for h in histories:
            role_key = (h.actor_role or "").lower()
            if role_key and role_key not in approval_dates:
                approval_dates[role_key] = h.created_at.isoformat() if h.created_at else None
        
        return jsonify({
            "id": pr.id,
            "order_number": pr.order_number,
            "requester": pr.requester,
            "department": pr.department,
            "delivery_address": pr.delivery_address,
            "delivery_date": pr.delivery_date,
            "project_code": pr.project_code,
            "currency": pr.currency,
            "total_amount": float(pr.total_amount or 0.0),
            "status": pr.status,
            "current_stage": pr.current_stage,
            "next_role": pr.next_role,
            "created_by": pr.created_by,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
            "date": str(pr.created_at.date()) if pr.created_at else "",
            "items": items,
            "approval_data": {
                "requester_name": pr.requester_name,
                "requester_position": pr.requester_position,
                "manager_name": pr.manager_name,
                "manager_position": pr.manager_position,
                "finance_name": pr.finance_name,
                "finance_position": pr.finance_position,
                "disbursement_name": pr.disbursement_name,
                "disbursement_position": pr.disbursement_position,
                "requester_date": pr.requester_date,
                "manager_date": pr.manager_date,
                "finance_date": pr.finance_date,
                "disbursement_date": pr.disbursement_date
            },
            "signatures": {
                "manager": pr.manager_signature,
                "finance": pr.finance_signature,
                "disbursement": pr.disbursement_signature
            },
            "approval_dates": approval_dates
        })
    finally:
        db.close()


# ==================== طلبات المعتمدة / المرفوضة ====================

@bp.get("/my/approved")
@require_auth_and_roles("admin","manager","finance","disbursement")
def my_approved():
    return _my_actioned_requests(["approve", "auto-approve"])


@bp.get("/my/rejected")
@require_auth_and_roles("admin","manager","finance","disbursement")
def my_rejected():
    return _my_actioned_requests(["reject"])


def _my_actioned_requests(actions):
    """
    جلب الطلبات التي تصرف فيها المستخدم الحالي (موافقة أو رفض).
    يُستخدم من my_approved و my_rejected — بلا N+1 query.
    """
    user = getattr(request, "user", {}) or {}
    actor_user = user.get("username") or user.get("name") or user.get("email")
    is_reject = "reject" in actions

    db = SessionLocal()
    try:
        # استعلام واحد مع subquery بدلاً من N+1
        from sqlalchemy import func
        latest_action = (
            db.query(
                ApprovalHistory.request_id,
                func.max(ApprovalHistory.created_at).label("action_at"),
                ApprovalHistory.note,
            )
            .filter(
                ApprovalHistory.actor_user == actor_user,
                ApprovalHistory.action.in_(actions),
            )
            .group_by(ApprovalHistory.request_id)
            .subquery()
        )

        rows = (
            db.query(PurchaseRequest, latest_action.c.action_at, latest_action.c.note)
            .join(latest_action, PurchaseRequest.id == latest_action.c.request_id)
            .order_by(latest_action.c.action_at.desc())
            .all()
        )

        result = []
        for pr, action_at, note in rows:
            d = _serialize_request_summary(pr)
            if is_reject:
                d["rejected_at"] = action_at.isoformat() if action_at else None
                d["rejection_note"] = note
            else:
                d["approved_at"] = action_at.isoformat() if action_at else None
                d["approval_note"] = note
            result.append(d)

        return jsonify(result)
    except Exception as e:
        label = "المرفوضة" if is_reject else "المعتمدة"
        logger.error(f"خطأ في جلب {label}: {e}")
        return jsonify({"error": f"خطأ في جلب الطلبات {label}"}), 500
    finally:
        db.close()


# ==================== طابور العمل ====================

@bp.get("/my/queue")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement")
def my_queue():
    user = getattr(request, "user", {}) or {}
    role = user.get("role")
    username = user.get("username")
    user_dept = user.get("department")
    
    db = SessionLocal()
    try:
        q = db.query(PurchaseRequest)
        
        if role == "admin":
            q = q.filter(PurchaseRequest.current_stage.in_(["manager", "finance", "disbursement"]))
        elif role == "manager":
            if not user_dept:
                return jsonify({"requests": [], "total": 0, "approved": 0, "rejected": 0, "pending": 0})
            
            if username == "manager_finance":
                # المدير المالي: طلبات إدارته (pending_manager) + جميع طلبات المالية (pending_finance)
                q = q.filter(
                    (PurchaseRequest.status == "pending_manager") & (PurchaseRequest.department == "مالية") |
                    (PurchaseRequest.status == "pending_finance")
                )
            elif username == "manager_exec":
                # آمر الصرف: طلبات إدارته (pending_manager) + جميع طلبات أمر الصرف
                q = q.filter(
                    ((PurchaseRequest.status == "pending_manager") & (PurchaseRequest.department == user_dept)) |
                    (PurchaseRequest.status == "pending_disbursement")
                )
            else:
                # مدير عادي: طلبات إدارته فقط
                q = q.filter(PurchaseRequest.department == user_dept, PurchaseRequest.status == "pending_manager")
        elif role == "finance":
            q = q.filter(PurchaseRequest.status == "pending_finance")
        elif role == "disbursement" or username == "manager_exec":
            q = q.filter(PurchaseRequest.status == "pending_disbursement")
        elif role == "procurement":
            q = q.filter(PurchaseRequest.status == "pending_procurement")
        else:
            q = q.filter(PurchaseRequest.next_role == role)
        
        requests_list = q.order_by(PurchaseRequest.id.desc()).all()
        out = []
        for r in requests_list:
            d = _serialize_request_summary(r)
            d["items"] = [_serialize_item(it) for it in r.items]
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


# ==================== طلباتي ====================

@bp.get("/my/requests")
@require_auth_and_roles("requester","admin","manager","finance","disbursement")
def my_requests():
    """طلباتي — الطلبات التي أنشأها المستخدم الحالي"""
    return _get_user_own_requests()


@bp.get("/user/requests")
@require_auth_and_roles("requester","admin","manager","finance","disbursement")
def user_requests():
    """طلبات المستخدم (alias لـ my/requests)"""
    return _get_user_own_requests()


def _get_user_own_requests():
    """جلب الطلبات التي أنشأها المستخدم الحالي"""
    user = getattr(request, "user", {}) or {}
    me = user.get("username") or user.get("name") or user.get("email")
    db = SessionLocal()
    try:
        q = db.query(PurchaseRequest)
        if user.get("role") != "admin":
            q = q.filter(PurchaseRequest.created_by == me)
        results = q.order_by(PurchaseRequest.id.desc()).all()
        return jsonify([_serialize_request_summary(r) for r in results])
    finally:
        db.close()


# ==================== الموافقة/رفض البنود ====================

@bp.post("/requests/<int:request_id>/items/<int:item_id>/action")
@require_auth
def item_action(request_id, item_id):
    """الموافقة أو رفض بند فردي"""
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    reason = data.get("reason", "").strip()
    
    if action not in ["approve", "reject"]:
        return jsonify({"error": "الإجراء يجب أن يكون 'approve' أو 'reject'"}), 400
    if action == "reject" and not reason:
        return jsonify({"error": "يجب إدخال سبب الرفض"}), 400
    
    db = SessionLocal()
    try:
        item = db.query(PurchaseItem).filter(
            PurchaseItem.id == item_id, PurchaseItem.request_id == request_id
        ).first()
        if not item:
            return jsonify({"error": "البند غير موجود"}), 404
        
        pr = item.request
        actor_user = request.user.get("username")
        actor_role = request.user.get("role")
        actor_name = request.user.get("full_name") or actor_user
        
        if actor_role not in ["manager", "finance", "disbursement", "admin"]:
            return jsonify({"error": "لا تملك صلاحية لتنفيذ هذا الإجراء"}), 403
        
        if action == "approve":
            item.status = "approved"
            item.rejection_reason = None
            item.rejected_by = None
            item.rejection_date = None
        else:
            item.status = "rejected"
            item.rejection_reason = reason
            item.rejected_by = actor_name
            item.rejection_date = datetime.now(timezone.utc)
        
        # إعادة حساب المبلغ الإجمالي
        approved_total = sum(i.total for i in pr.items if i.status in ["approved", "pending"])
        pr.total_amount = approved_total
        
        db.commit()
        return jsonify({
            "message": f"تم {'الموافقة على' if action == 'approve' else 'رفض'} البند بنجاح",
            "item": {"id": item.id, "item_name": item.item_name, "status": item.status,
                     "rejection_reason": item.rejection_reason, "rejected_by": item.rejected_by},
            "request": {"id": pr.id, "total_amount": float(pr.total_amount or 0)}
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.get("/requests/<int:request_id>/items")
@require_auth
def get_request_items(request_id):
    db = SessionLocal()
    try:
        items = db.query(PurchaseItem).filter(PurchaseItem.request_id == request_id).all()
        return jsonify({
            "items": [{
                "id": item.id, "item_name": item.item_name,
                "specification": item.specification, "unit": item.unit,
                "quantity": item.quantity, "price": item.price,
                "total": item.total, "status": item.status or "pending",
                "rejection_reason": item.rejection_reason,
                "rejected_by": item.rejected_by,
                "rejection_date": item.rejection_date.isoformat() if item.rejection_date else None
            } for item in items]
        })
    finally:
        db.close()


@bp.post("/requests/<int:request_id>/items/bulk-action")
@require_auth
def bulk_item_action(request_id):
    """الموافقة أو رفض عدة بنود دفعة واحدة"""
    data = request.get_json(force=True, silent=True) or {}
    items_actions = data.get("items", [])
    if not items_actions:
        return jsonify({"error": "يجب تحديد البنود والإجراءات"}), 400
    
    db = SessionLocal()
    try:
        pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
        if not pr:
            return jsonify({"error": "الطلب غير موجود"}), 404
        
        actor_user = request.user.get("username")
        actor_name = request.user.get("full_name") or actor_user
        results = []
        
        for ia in items_actions:
            item = db.query(PurchaseItem).filter(
                PurchaseItem.id == ia.get("id"), PurchaseItem.request_id == request_id
            ).first()
            if not item:
                continue
            
            if ia.get("action") == "approve":
                item.status = "approved"
                item.rejection_reason = None
                item.rejected_by = None
                item.rejection_date = None
            elif ia.get("action") == "reject":
                item.status = "rejected"
                item.rejection_reason = ia.get("reason", "").strip()
                item.rejected_by = actor_name
                item.rejection_date = datetime.now(timezone.utc)
            
            results.append({"id": item.id, "item_name": item.item_name, "status": item.status})
        
        # إعادة حساب المبلغ
        pr.total_amount = sum(i.total for i in pr.items if i.status in ["approved", "pending"])
        db.commit()
        
        return jsonify({"message": "تم تنفيذ الإجراءات بنجاح", "results": results,
                        "new_total": float(pr.total_amount or 0)})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
