"""
مسارات المصادقة — تسجيل الدخول، بيانات المستخدم، التوقيع الإلكتروني
"""

import logging
import hashlib
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ..utils.auth import create_token, require_auth
from ..database import SessionLocal
from ..models import User

bp = Blueprint("auth", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


def _verify_password(stored_hash, password):
    """
    التحقق من كلمة المرور — يدعم الهاش القديم (SHA-256) والجديد (werkzeug).
    إذا نجح SHA-256 يُرقّي تلقائياً للهاش الجديد.
    """
    # محاولة werkzeug أولاً (الهاش الجديد)
    if stored_hash.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_hash, password), False

    # محاولة SHA-256 القديم
    old_hash = hashlib.sha256(password.encode()).hexdigest()
    if stored_hash == old_hash:
        return True, True  # نجح + يحتاج ترقية

    return False, False


@bp.post("/login")
def login():
    """تسجيل الدخول"""
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "اسم المستخدم وكلمة المرور مطلوبان"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()

        if not user:
            return jsonify({"error": "بيانات الدخول غير صحيحة"}), 401

        valid, needs_upgrade = _verify_password(user.password_hash, password)
        if not valid:
            return jsonify({"error": "بيانات الدخول غير صحيحة"}), 401

        # ترقية الهاش القديم تلقائياً
        if needs_upgrade:
            user.password_hash = generate_password_hash(password)
            db.commit()
            logger.info(f"تمت ترقية هاش كلمة المرور للمستخدم: {username}")

        token = create_token(user.id, user.username, user.role, user.department)
        return jsonify({
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "full_name": user.full_name,
                "department": user.department,
                "signature": user.signature,
            }
        })
    finally:
        db.close()


@bp.get("/me")
@require_auth
def get_current_user():
    """الحصول على بيانات المستخدم الحالي"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == request.user["user_id"]).first()
        if not user:
            return jsonify({"error": "المستخدم غير موجود"}), 404
        return jsonify({
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "department": user.department,
            "signature": user.signature,
        })
    finally:
        db.close()


@bp.get("/my-signature")
@require_auth
def get_my_signature():
    """جلب التوقيع الإلكتروني للمستخدم الحالي"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == request.user["user_id"]).first()
        if not user:
            return jsonify({"error": "المستخدم غير موجود"}), 404
        return jsonify({
            "signature": user.signature,
            "has_signature": bool(user.signature),
        })
    finally:
        db.close()


@bp.post("/my-signature")
@require_auth
def save_my_signature():
    """حفظ التوقيع الإلكتروني للمستخدم الحالي"""
    data = request.get_json(force=True, silent=True) or {}
    signature = data.get("signature")

    if not signature:
        return jsonify({"error": "التوقيع مطلوب"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == request.user["user_id"]).first()
        if not user:
            return jsonify({"error": "المستخدم غير موجود"}), 404

        user.signature = signature
        db.commit()
        return jsonify({
            "message": "تم حفظ التوقيع بنجاح",
            "signature": signature,
        })
    except Exception as e:
        db.rollback()
        logger.error(f"خطأ في حفظ التوقيع: {e}")
        return jsonify({"error": f"خطأ في حفظ التوقيع: {str(e)}"}), 500
    finally:
        db.close()


@bp.get("/approval-managers")
@require_auth
def get_approval_managers():
    """جلب أسماء المدراء المسؤولين عن الموافقات بناءً على قسم المستخدم"""
    db = SessionLocal()
    try:
        user_department = request.user.get("department", "")

        # المدير المباشر (حسب القسم)
        direct_manager = db.query(User).filter(
            User.role == "manager",
            User.department == user_department,
            User.is_active == True,
        ).first()

        # المدير المالي
        finance_manager = db.query(User).filter(
            User.username == "manager_finance",
            User.is_active == True,
        ).first()

        # آمر الصرف
        disbursement_manager = db.query(User).filter(
            User.username == "manager_exec",
            User.is_active == True,
        ).first()

        return jsonify({
            "direct_manager": direct_manager.full_name if direct_manager else "",
            "direct_manager_position": f"مدير {user_department}" if direct_manager else "",
            "finance_manager": finance_manager.full_name if finance_manager else "",
            "finance_manager_position": "مدير الإدارة المالية" if finance_manager else "",
            "disbursement_manager": disbursement_manager.full_name if disbursement_manager else "",
            "disbursement_manager_position": "آمر الصرف" if disbursement_manager else "",
        })
    finally:
        db.close()
