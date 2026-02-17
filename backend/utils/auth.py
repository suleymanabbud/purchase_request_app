"""
وحدة المصادقة والصلاحيات — JWT Authentication & RBAC
"""

import logging
import datetime
from functools import wraps
from flask import request, jsonify
from ..config import JWT_SECRET_KEY, JWT_EXPIRY_HOURS

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# المفتاح السري — من ملف الإعدادات الموحّد
# ────────────────────────────────────────────
SECRET_KEY = JWT_SECRET_KEY

# استيراد JWT
try:
    import jwt
except ImportError:
    jwt = None
    logger.warning("مكتبة PyJWT غير مثبتة — لن تعمل المصادقة.")


# ────────────────────────────────────────────
# إنشاء والتحقق من التوكن
# ────────────────────────────────────────────

def create_token(user_id, username, role, department=None):
    """إنشاء JWT token للمستخدم"""
    if jwt is None:
        return None
    try:
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "department": department,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    except Exception as e:
        logger.error(f"خطأ في إنشاء Token: {e}")
        return None


def verify_token(token):
    """التحقق من صحة الـ token — يُرجع payload أو None"""
    if jwt is None:
        return None
    if not token or token in ("null", "undefined"):
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.debug("Token منتهي الصلاحية")
        return None
    except jwt.InvalidTokenError:
        logger.debug("Token غير صالح")
        return None


# ────────────────────────────────────────────
# استخراج التوكن من الطلب
# ────────────────────────────────────────────

def _extract_token():
    """استخراج JWT من header Authorization: Bearer ..."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# ────────────────────────────────────────────
# Decorators
# ────────────────────────────────────────────

def require_auth(f):
    """ديكوريتر للتحقق من المصادقة فقط (أي دور)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Token مطلوب"}), 401

        user_data = verify_token(token)
        if not user_data:
            return jsonify({"error": "Token غير صالح أو منتهي الصلاحية"}), 401

        request.user = user_data
        return f(*args, **kwargs)

    return decorated


def require_roles(*allowed_roles):
    """ديكوريتر للتحقق من الصلاحيات (يتطلب require_auth قبله)"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, "user"):
                return jsonify({"error": "يجب تسجيل الدخول أولاً"}), 401

            user_role = request.user.get("role")
            if user_role not in allowed_roles:
                return jsonify({"error": "ليس لديك صلاحية للوصول لهذا المورد"}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_auth_and_roles(*allowed_roles):
    """ديكوريتر مشترك للمصادقة والصلاحيات"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "Token مطلوب"}), 401

            user_data = verify_token(token)
            if not user_data:
                return jsonify({"error": "Token غير صالح أو منتهي الصلاحية"}), 401

            user_role = user_data.get("role")
            if user_role not in allowed_roles:
                return jsonify({
                    "error": f"ليس لديك صلاحية للوصول لهذا المورد. دورك: {user_role}"
                }), 403

            request.user = user_data
            return f(*args, **kwargs)
        return decorated
    return decorator
