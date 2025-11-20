# backend/app.py
import os
from flask import Flask, jsonify
from flask_cors import CORS
from .database import Base, engine
from .routes.requests import bp as requests_bp
from .routes.admin import bp as admin_bp
from .routes.auth import bp as auth_bp
from .routes.workflow import bp as workflow_bp
from .routes.upload import bp as upload_bp
from .routes.procurement import bp as procurement_bp
from .routes.notifications import bp as notifications_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

def create_app():
    # نخدّم الواجهة من نفس التطبيق (ينهي CORS)
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

    # بإمكانك ترك CORS مفتوح للتطوير لمسارات /api/* أو إزالته لأن الواجهة على نفس الأصل
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # إنشاء/تحديث جداول قاعدة البيانات
    Base.metadata.create_all(bind=engine)

    # صفحة البداية -> login.html
    @app.get("/")
    def index():
        return app.send_static_file("login.html")

    # Health check
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # تسجيل الـ blueprints
    app.register_blueprint(requests_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(notifications_bp)

    return app

# تشغيل مباشر (اختياري عند تشغيل الملف نفسه)
if __name__ == "__main__":
    _app = create_app()
    _app.config['ADMIN_USER'] = 'admin'
    _app.config['ADMIN_PASS'] = 'admin123'
    _app.run(host="0.0.0.0", port=5000, debug=True)
