from flask import Blueprint, request, jsonify, current_app
from ..utils.auth import create_token, require_auth
from ..database import SessionLocal
from ..models import User
import hashlib

bp = Blueprint("auth", __name__, url_prefix="/api")

def hash_password(password):
    """تشفير كلمة المرور"""
    return hashlib.sha256(password.encode()).hexdigest()

@bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    
    if not username or not password:
        return jsonify({"error": "اسم المستخدم وكلمة المرور مطلوبان"}), 400
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if not user or user.password_hash != hash_password(password):
            return jsonify({"error": "بيانات الدخول غير صحيحة"}), 401
        
        token = create_token(user.id, user.username, user.role, user.department)
        return jsonify({
            "token": token,
            "user": {
                "id": user.id, 
                "username": user.username, 
                "role": user.role,
                "full_name": user.full_name,
                "department": user.department
            }
        })
    finally:
        db.close()

@bp.get("/me")
@require_auth
def get_current_user():
    """الحصول على بيانات المستخدم الحالي"""
    # جلب بيانات المستخدم كاملة من قاعدة البيانات
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
            "department": user.department
        })
    finally:
        db.close()
