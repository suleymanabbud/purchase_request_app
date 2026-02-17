"""
إنشاء المستخدمين الافتراضيين للنظام
يستخدم werkzeug.security لتشفير كلمات المرور (bcrypt-based)
"""

import logging
from werkzeug.security import generate_password_hash
from .database import SessionLocal, Base, engine
from .models import User

logger = logging.getLogger(__name__)


def hash_password(password):
    """تشفير كلمة المرور باستخدام werkzeug (pbkdf2:sha256)"""
    return generate_password_hash(password)


def create_default_users():
    """إنشاء المستخدمين الافتراضيين — آمن: لا يمس البيانات الموجودة"""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # التحقق من وجود المستخدمين — لا حاجة لإعادة الإنشاء
        if db.query(User).count() > 0:
            logger.info("المستخدمون موجودون بالفعل — تم تخطي الإنشاء")
            return

        # ─────────────────────────── الهيكل الإداري ───────────────────────────
        # المالية:      مدير (manager_finance) + موظف
        # تطوير الأعمال: مدير + موظف
        # الموارد البشرية: مدير + موظف
        # القسم التقني:  مستخدم واحد (مدير وموظف)
        # التنفيذية:     مدير (manager_exec: مدير + آمر صرف) + موظفان
        # المشتريات:    مسؤول مشتريات
        #
        # سير العمل:
        # 1. الطلب → المدير المباشر (حسب القسم)
        # 2. المدير المباشر → المدير المالي (manager_finance)
        # 3. المدير المالي → آمر الصرف (manager_exec)
        # 4. إذا كان نفس الشخص مدير مباشر ومالي أو آمر صرف → تخطي تلقائي
        # ─────────────────────────────────────────────────────────────────────

        users = [
            # مدير النظام
            {"username": "admin",             "password": "Admin@2024",   "full_name": "مدير النظام",           "role": "admin",       "department": "الإدارة العامة"},
            # المالية
            {"username": "manager_finance",   "password": "Finance@24",  "full_name": "خالد هنداوي",          "role": "manager",     "department": "مالية"},
            {"username": "requester_finance", "password": "Fin2024!",    "full_name": "موظف مالية",            "role": "requester",   "department": "مالية"},
            # تطوير الأعمال
            {"username": "manager_bizdev",    "password": "BizDev@24",   "full_name": "مدير تطوير الأعمال",   "role": "manager",     "department": "تطوير الأعمال"},
            {"username": "requester_bizdev",  "password": "Biz2024!",    "full_name": "موظف تطوير الأعمال",   "role": "requester",   "department": "تطوير الأعمال"},
            # الموارد البشرية
            {"username": "manager_hr",        "password": "HumanR@24",   "full_name": "محمد السرحان",          "role": "manager",     "department": "موارد بشرية"},
            {"username": "requester_hr",      "password": "Hr2024!",     "full_name": "موظف موارد بشرية",     "role": "requester",   "department": "موارد بشرية"},
            # التقنية
            {"username": "tech_user",         "password": "Tech@2024",   "full_name": "المسؤول التقني",        "role": "manager",     "department": "تقني"},
            # التنفيذية
            {"username": "manager_exec",      "password": "Exec@2024",   "full_name": "خليل بالبي",           "role": "manager",     "department": "تنفيذية"},
            {"username": "requester_exec1",   "password": "Exec2024!",   "full_name": "موظف تنفيذية 1",       "role": "requester",   "department": "تنفيذية"},
            {"username": "requester_exec2",   "password": "Exec2024!",   "full_name": "موظف تنفيذية 2",       "role": "requester",   "department": "تنفيذية"},
            # المشتريات
            {"username": "procurement_user",  "password": "Procure@24",  "full_name": "مسؤول المشتريات",      "role": "procurement", "department": "المشتريات"},
        ]

        for user_data in users:
            db.add(User(
                username=user_data["username"],
                password_hash=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                department=user_data["department"],
            ))

        db.commit()
        logger.info(f"تم إنشاء {len(users)} مستخدم افتراضي بنجاح")

    except Exception as e:
        db.rollback()
        logger.error(f"خطأ في إنشاء المستخدمين: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    create_default_users()
