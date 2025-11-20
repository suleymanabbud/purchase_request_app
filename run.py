#!/usr/bin/env python3
"""
ملف تشغيل المشروع الرئيسي
"""
import sys
import os

# إضافة مسار المشروع إلى Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_database():
    """إصلاح قاعدة البيانات"""
    print("🔧 إصلاح قاعدة البيانات...")
    
    # إنشاء مجلد قاعدة البيانات إذا لم يكن موجوداً
    os.makedirs("database", exist_ok=True)
    
    # إعادة إنشاء قاعدة البيانات
    try:
        from backend.database import Base, engine
        from backend.models import User, PurchaseRequest, PurchaseItem, ApprovalHistory
        
        # إنشاء جميع الجداول (سيتم إعادة إنشاؤها تلقائياً)
        Base.metadata.create_all(bind=engine)
        print("✅ تم إنشاء/تحديث قاعدة البيانات")
        
        # تحديث الطلبات القديمة لتتوافق مع النظام الجديد
        try:
            from backend.database import SessionLocal
            db = SessionLocal()
            
            # تحديث الطلبات القديمة لتتوافق مع النظام الجديد
            print("🔧 تحديث الطلبات القديمة...")
            
            # تحديث الطلبات التي لا تحتوي على status
            updated_status = db.query(PurchaseRequest).filter(PurchaseRequest.status.is_(None)).update(
                {"status": "pending_manager"}, synchronize_session=False
            )
            if updated_status > 0:
                print(f"✅ تم تحديث {updated_status} طلب - status")
            
            # تحديث الطلبات التي لا تحتوي على current_stage
            updated_stage = db.query(PurchaseRequest).filter(PurchaseRequest.current_stage.is_(None)).update(
                {"current_stage": "manager"}, synchronize_session=False
            )
            if updated_stage > 0:
                print(f"✅ تم تحديث {updated_stage} طلب - current_stage")
            
            # تحديث الطلبات التي لا تحتوي على next_role
            updated_role = db.query(PurchaseRequest).filter(PurchaseRequest.next_role.is_(None)).update(
                {"next_role": "manager"}, synchronize_session=False
            )
            if updated_role > 0:
                print(f"✅ تم تحديث {updated_role} طلب - next_role")
            
            # تحديث الطلبات التي لا تحتوي على created_by
            updated_creator = db.query(PurchaseRequest).filter(PurchaseRequest.created_by.is_(None)).update(
                {"created_by": "system"}, synchronize_session=False
            )
            if updated_creator > 0:
                print(f"✅ تم تحديث {updated_creator} طلب - created_by")
            
            # تحديث إجباري لجميع الطلبات لتكون pending_manager
            print("🔧 تحديث جميع الطلبات لتكون pending_manager...")
            all_updated = db.query(PurchaseRequest).update({
                "status": "pending_manager",
                "current_stage": "manager", 
                "next_role": "manager"
            }, synchronize_session=False)
            print(f"✅ تم تحديث {all_updated} طلب - جميع الطلبات")
            
            db.commit()
            print("✅ تم تحديث الطلبات القديمة")
            db.close()
            
        except Exception as e:
            print(f"⚠️ تحذير: لم يتم تحديث الطلبات القديمة: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إصلاح قاعدة البيانات: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 نظام إدارة طلبات الشراء - صرح القابضة")
    print("=" * 50)
    
    # تثبيت المتطلبات
    print("🔧 التحقق من المتطلبات...")
    try:
        import jwt
        print("✅ PyJWT مثبت")
    except ImportError:
        print("⚠️ PyJWT غير مثبت. جاري التثبيت...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyJWT==2.8.0"])
            print("✅ تم تثبيت PyJWT بنجاح")
        except Exception as e:
            print(f"❌ فشل في تثبيت PyJWT: {e}")
            print("⚠️ سيتم استخدام Debug Mode فقط")
    
    # إصلاح قاعدة البيانات
    try:
        if not fix_database():
            print("❌ فشل في إصلاح قاعدة البيانات")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ تحذير: {e}")
        print("المحاولة مرة أخرى...")
        if not fix_database():
            print("❌ فشل في إصلاح قاعدة البيانات")
            sys.exit(1)
    
    # إنشاء المستخدمين الافتراضيين
    print("👥 إنشاء المستخدمين الافتراضيين...")
    from backend.seed_data import create_default_users
    create_default_users()
    
    # إنشاء التطبيق
    from backend.app import create_app
    app = create_app()
    app.config['ADMIN_USER'] = 'admin'
    app.config['ADMIN_PASS'] = 'admin123'
    
    # تحديد وضع التشغيل
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if is_production:
        print("\n🎯 تشغيل المشروع في وضع الإنتاج...")
        print("🌐 الخادم يعمل على: http://0.0.0.0:5000")
        print("🔒 وضع الإنتاج مفعل - DEBUG = False")
    else:
        print("\n🎯 تشغيل المشروع في وضع التطوير...")
        print("يمكنك الوصول للتطبيق على:")
        print("- الخادم الخلفي: http://localhost:5000")
        print("- صفحة تسجيل الدخول: http://localhost:5000/frontend/login.html")
    
    print("\nالحسابات الجاهزة:")
    print("- admin/admin123 (مدير النظام)")
    print("- manager_finance/pass123 (مدير المالية)")
    print("- finance_manager/pass123 (رئيس المالية)")
    print("- manager_bizdev/pass123 (مدير تطوير الأعمال)")
    print("- manager_hr/pass123 (مدير الموارد البشرية)")
    print("- tech_user/pass123 (المسؤول التقني)")
    print("- manager_exec/pass123 (مدير الإدارة التنفيذية)")
    print("- disbursement_exec/pass123 (أمر الصرف)")
    print("- requester_finance/pass123 (موظف مالية)")
    print("- requester_bizdev/pass123 (موظف تطوير الأعمال)")
    print("- requester_hr/pass123 (موظف موارد بشرية)")
    print("- requester_exec1/pass123 (موظف تنفيذية 1)")
    print("- requester_exec2/pass123 (موظف تنفيذية 2)")
    print("=" * 50)
    
    # تشغيل التطبيق حسب الوضع
    if is_production:
        app.run(host="0.0.0.0", port=5000, debug=False)
    else:
        app.run(host="0.0.0.0", port=5000, debug=True)
