"""
إعدادات الإنتاج للنشر على VPS
"""
import os

class ProductionConfig:
    """إعدادات الإنتاج"""
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = "sqlite:///./database/purchase_requests.db"
    
    # إعدادات JWT - يجب تغييرها في الإنتاج
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or "production-secret-key-change-me"
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24 ساعة
    
    # إعدادات CORS للإنتاج
    CORS_ORIGINS = [
        "http://72.60.32.88",
        "https://72.60.32.88",
        "http://srv1073351.hstgr.cloud",
        "https://srv1073351.hstgr.cloud"
    ]
    
    # إعدادات الخادم
    HOST = "127.0.0.1"  # للاستخدام مع Nginx
    PORT = 5000
    DEBUG = False  # مهم: تعطيل وضع التطوير في الإنتاج
    
    # إعدادات الإدارة
    ADMIN_USER = "admin"
    ADMIN_PASS = os.environ.get('ADMIN_PASS') or "admin123"
    
    # إعدادات التطبيق
    APP_NAME = "نظام إدارة طلبات الشراء"
    COMPANY_NAME = "صرح القابضة"
    
    # إعدادات الملفات
    UPLOAD_FOLDER = "backend/static/uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # إعدادات الأمان
    SECRET_KEY = os.environ.get('SECRET_KEY') or "production-secret-key-change-me"
    
    @staticmethod
    def init_app(app):
        """تهيئة التطبيق بالإعدادات"""
        app.config.from_object(ProductionConfig)
