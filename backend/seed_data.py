from .database import SessionLocal, Base, engine
from .models import User, AccountType
import hashlib

def hash_password(password):
    """تشفير كلمة المرور"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_default_users():
    """إنشاء المستخدمين الافتراضيين"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    # --- منطق الهيكل الإداري والموافقات ---
    # المالية: موظف ومدير (manager_finance هو المدير المباشر والمالي)
    # تطوير الأعمال: موظف ومدير
    # الموارد البشرية: موظف ومدير
    # القسم التقني: مستخدم واحد فقط (مدير وموظف بنفس الوقت)
    # الإدارة التنفيذية: موظفان ومدير واحد (manager_exec) وهو نفسه أمر الصرف
    # منطق الموافقات:
    # - الطلب يذهب أولاً للمدير المباشر (حسب القسم)
    # - إذا وافق المدير المباشر، يذهب للمدير المالي (manager_finance)
    # - إذا وافق المدير المالي، يذهب لأمر الصرف (manager_exec)
    # - إذا كان نفس المستخدم هو المدير المباشر والمالي أو أمر الصرف، يتخطى النظام الموافقة المكررة تلقائيًا
    # - إذا وافق أمر الصرف على طلب هو نفسه مديره المباشر، يعتبر الطلب معتمدًا مباشرة بعد موافقة المالية
    # - إذا وافق المدير المالي على طلب هو نفسه مدير مباشر للموظف، يتخطى النظام الموافقة المكررة
    try:
        # التحقق من وجود المستخدمين
        if db.query(User).count() > 0:
            print("Users already exist")
            return
        users = [
            # حساب مدير النظام
            {
                "username": "admin",
                "password": "admin123",
                "full_name": "مدير النظام",
                "role": "admin",
                "department": "الإدارة العامة"
            },
            # الإدارة المالية: موظف ومدير ومدير مالي
            {"username": "manager_finance", "password": "pass123", "full_name": "مدير المالية", "role": "manager", "department": "مالية"},
            {"username": "finance_manager", "password": "pass123", "full_name": "رئيس المالية", "role": "finance", "department": "مالية"},
            {"username": "requester_finance", "password": "pass123", "full_name": "موظف مالية", "role": "requester", "department": "مالية"},
            # إدارة تطوير الأعمال: موظف ومدير
            {"username": "manager_bizdev", "password": "pass123", "full_name": "مدير تطوير الأعمال", "role": "manager", "department": "تطوير الأعمال"},
            {"username": "requester_bizdev", "password": "pass123", "full_name": "موظف تطوير الأعمال", "role": "requester", "department": "تطوير الأعمال"},
            # إدارة الموارد البشرية: موظف ومدير
            {"username": "manager_hr", "password": "pass123", "full_name": "مدير الموارد البشرية", "role": "manager", "department": "موارد بشرية"},
            {"username": "requester_hr", "password": "pass123", "full_name": "موظف موارد بشرية", "role": "requester", "department": "موارد بشرية"},
            # القسم التقني: مستخدم واحد فقط (موظف ومدير بنفس الوقت)
            {"username": "tech_user", "password": "pass123", "full_name": "المسؤول التقني", "role": "manager", "department": "تقني"},
            # الإدارة التنفيذية: موظفان ومدير/أمر صرف
            {"username": "manager_exec", "password": "pass123", "full_name": "مدير الإدارة التنفيذية", "role": "manager", "department": "تنفيذية"},
            {"username": "disbursement_exec", "password": "pass123", "full_name": "أمر الصرف التنفيذي", "role": "disbursement", "department": "تنفيذية"},
            {"username": "requester_exec1", "password": "pass123", "full_name": "موظف تنفيذية 1", "role": "requester", "department": "تنفيذية"},
            {"username": "requester_exec2", "password": "pass123", "full_name": "موظف تنفيذية 2", "role": "requester", "department": "تنفيذية"},
            # قسم المشتريات
            {"username": "procurement_user", "password": "pass123", "full_name": "مسؤول المشتريات", "role": "procurement", "department": "المشتريات"},
        ]
        
        for user_data in users:
            user = User(
                username=user_data["username"],
                password_hash=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                department=user_data["department"]
            )
            db.add(user)
        
        db.commit()
        print("Default users created successfully")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_default_users()
