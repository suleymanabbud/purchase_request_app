from flask import Blueprint, jsonify, request
from ..database import SessionLocal
from ..models import Notification
from ..utils.auth import require_auth_and_roles

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@require_auth_and_roles("admin", "manager", "finance", "disbursement", "procurement", "requester")
def list_notifications():
    user = getattr(request, "user", {}) or {}
    username = user.get("username")
    db = SessionLocal()
    try:
        notifications = (
            db.query(Notification)
            .filter(Notification.recipient_username == username)
            .order_by(Notification.created_at.desc())
            .limit(100)
            .all()
        )
        data = [
            {
                "id": n.id,
                "request_id": n.request_id,
                "title": n.title,
                "message": n.message,
                "action_type": n.action_type,
                "actor_username": n.actor_username,
                "actor_role": n.actor_role,
                "note": n.note,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ]
        return jsonify(data)
    finally:
        db.close()


@bp.post("/<int:notification_id>/read")
@require_auth_and_roles("admin", "manager", "finance", "disbursement", "procurement", "requester")
def mark_notification_read(notification_id):
    user = getattr(request, "user", {}) or {}
    username = user.get("username")
    db = SessionLocal()
    try:
        notification = db.get(Notification, notification_id)
        if not notification or notification.recipient_username != username:
            return jsonify({"error": "الإشعار غير موجود"}), 404
        notification.is_read = True
        db.add(notification)
        db.commit()
        return jsonify({"message": "تم تحديث حالة الإشعار"})
    finally:
        db.close()


@bp.post("/read-all")
@require_auth_and_roles("admin", "manager", "finance", "disbursement", "procurement", "requester")
def mark_all_read():
    user = getattr(request, "user", {}) or {}
    username = user.get("username")
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.recipient_username == username,
            Notification.is_read.is_(False),
        ).update({"is_read": True})
        db.commit()
        return jsonify({"message": "تم تعليم جميع الإشعارات كمقروءة"})
    finally:
        db.close()



