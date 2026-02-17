"""
مسارات المشرف — API فقط (بدون HTML مدمج)
"""

import logging
from flask import Blueprint, request, jsonify
from ..database import SessionLocal
from ..models import PurchaseRequest
from ..utils.auth import require_auth_and_roles

bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


@bp.get("/api/admin/requests")
@require_auth_and_roles("admin")
def admin_requests():
    """API لجلب بيانات الطلبات للوحة التحكم"""
    limit = int(request.args.get("limit", 50))
    db = SessionLocal()
    try:
        requests_list = (
            db.query(PurchaseRequest)
            .order_by(PurchaseRequest.id.desc())
            .limit(limit)
            .all()
        )
        data = [{
            "id": r.id,
            "order_number": r.order_number,
            "requester": r.requester,
            "department": r.department,
            "delivery_date": r.delivery_date,
            "currency": r.currency,
            "total_amount": float(r.total_amount or 0.0),
            "status": r.status,
        } for r in requests_list]
        return jsonify(data)
    finally:
        db.close()
