"""
ملف إعدادات المشروع
"""
import os

class Config:
    """الإعدادات الأساسية"""
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = "sqlite:///./database/purchase_requests.db"
    
    # إعدادات JWT
    JWT_SECRET_KEY = "your-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60  # 24 ساعة
    
    # إعدادات CORS
    CORS_ORIGINS = [
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5000",
        "http://localhost:5000"
    ]
    
    # إعدادات الخادم
    HOST = "0.0.0.0"
    PORT = 5000
    DEBUG = True
    
    # إعدادات الإدارة
    ADMIN_USER = "admin"
    ADMIN_PASS = "admin123"
    
    # إعدادات التطبيق
    APP_NAME = "نظام إدارة طلبات الشراء"
    COMPANY_NAME = "صرح القابضة"
    
    # إعدادات الملفات
    UPLOAD_FOLDER = "backend/static/uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    @staticmethod
    def init_app(app):
        """تهيئة التطبيق بالإعدادات"""
        app.config.from_object(Config)

class DevelopmentConfig(Config):
    """إعدادات التطوير"""
    DEBUG = True
    JWT_SECRET_KEY = "dev-secret-key"

class ProductionConfig(Config):
    """إعدادات الإنتاج"""
    DEBUG = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or "production-secret-key"
    DATABASE_URL = os.environ.get('DATABASE_URL') or Config.DATABASE_URL

# اختيار الإعدادات حسب البيئة
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
