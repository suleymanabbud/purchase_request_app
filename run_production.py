#!/usr/bin/env python3
"""
ملف تشغيل المشروع للإنتاج
"""
import sys
import os

# إضافة مسار المشروع إلى Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_production():
    """إعداد البيئة للإنتاج"""
    print("🔧 إعداد البيئة للإنتاج...")
    
    # إنشاء مجلد قاعدة البيانات إذا لم يكن موجوداً
    os.makedirs("database", exist_ok=True)
    
    # إعادة إنشاء قاعدة البيانات
    try:
        from backend.database import Base, engine
        from backend.models import User, PurchaseRequest, PurchaseItem, ApprovalHistory
        
        # إنشاء جميع الجداول
        Base.metadata.create_all(bind=engine)
        print("✅ تم إنشاء/تحديث قاعدة البيانات")
        
        # إنشاء المستخدمين الافتراضيين
        from backend.seed_data import create_default_users
        create_default_users()
        print("✅ تم إنشاء المستخدمين الافتراضيين")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إعداد قاعدة البيانات: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 نظام إدارة طلبات الشراء - صرح القابضة")
    print("🌐 وضع الإنتاج")
    print("=" * 50)
    
    # إعداد البيئة للإنتاج
    if not setup_production():
        print("❌ فشل في إعداد البيئة للإنتاج")
        sys.exit(1)
    
    # إنشاء التطبيق مع إعدادات الإنتاج
    from backend.app import create_app
    from production_config import ProductionConfig
    
    app = create_app()
    ProductionConfig.init_app(app)
    
    print("\n🎯 تشغيل المشروع في وضع الإنتاج...")
    print("🌐 الخادم يعمل على: http://127.0.0.1:5000")
    print("🔒 وضع الإنتاج مفعل - DEBUG = False")
    print("=" * 50)
    
    # تشغيل التطبيق
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
