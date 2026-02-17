"""
نقطة تجميع التطبيق — Flask Application Factory
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from .config import CORS_ORIGINS
from .database import Base, engine
from .routes.requests import bp as requests_bp
from .routes.admin import bp as admin_bp
from .routes.auth import bp as auth_bp
from .routes.workflow import bp as workflow_bp
from .routes.upload import bp as upload_bp
from .routes.procurement import bp as procurement_bp
from .routes.notifications import bp as notifications_bp

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def create_app():
    """إنشاء وتهيئة تطبيق Flask"""
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

    # CORS
    origins = CORS_ORIGINS if CORS_ORIGINS != "*" else "*"
    CORS(app, resources={r"/api/*": {"origins": origins}})

    # ضمان وجود مجلد قاعدة البيانات
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)

    # ─── نسخ احتياطي تلقائي قبل أي تغيير هيكلي ───
    try:
        from .utils.backup import backup_database
        backup_database("startup")
    except Exception as e:
        logger.warning(f"فشل النسخ الاحتياطي: {e}")

    # ─── حفظ snapshot للحالات قبل التعديل ───
    status_snapshot = {}
    try:
        from .utils.integrity import protect_approved_requests
        status_snapshot = protect_approved_requests()
    except Exception as e:
        logger.warning(f"فشل حفظ snapshot الحالات: {e}")

    # إنشاء/تحديث جداول قاعدة البيانات
    Base.metadata.create_all(bind=engine)

    # تحديث قاعدة البيانات لإضافة الأعمدة المفقودة
    try:
        from .migrate_db import migrate_database
        migrate_database()
    except Exception as e:
        logger.warning(f"فشل تحديث قاعدة البيانات: {e}")

    # ─── فحص سلامة البيانات بعد التحديث ───
    try:
        from .utils.integrity import verify_data_integrity, check_status_regression
        # التحقق من عدم تراجع الحالات
        if status_snapshot:
            check_status_regression(status_snapshot)
        # فحص شامل للتناسق
        verify_data_integrity()
    except Exception as e:
        logger.warning(f"فشل فحص السلامة: {e}")

    # الصفحة الرئيسية → login.html
    @app.get("/")
    def index():
        return app.send_static_file("login.html")

    # Health check
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # تسجيل الـ blueprints
    for bp in (requests_bp, admin_bp, auth_bp, workflow_bp,
               upload_bp, procurement_bp, notifications_bp):
        app.register_blueprint(bp)

    logger.info("تم تشغيل التطبيق بنجاح")
    return app
