"""
إعدادات pytest المشتركة — قاعدة بيانات اختبار منفصلة + عميل Flask
"""

import os
import sys
import pytest

# ضمان أن مجلد المشروع في مسار البحث
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# استخدام قاعدة بيانات SQLite في الذاكرة للاختبارات
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"


@pytest.fixture(scope="session")
def app():
    """إنشاء تطبيق Flask للاختبار"""
    # إعادة تحميل database module ليستخدم URL الجديد
    from backend.database import Base, engine
    Base.metadata.create_all(bind=engine)

    from backend.app import create_app
    test_app = create_app()
    test_app.config["TESTING"] = True
    yield test_app


@pytest.fixture(scope="session")
def client(app):
    """عميل HTTP للاختبارات"""
    return app.test_client()


@pytest.fixture(scope="session")
def seeded_app(app):
    """تطبيق مع بيانات مستخدمين أولية"""
    from backend.database import SessionLocal
    from backend.models import User
    from werkzeug.security import generate_password_hash

    db = SessionLocal()
    try:
        # التحقق من عدم وجود مستخدمين سابقين
        if db.query(User).count() == 0:
            users = [
                {"username": "admin",             "password": "Admin@2024",   "full_name": "مدير النظام",         "role": "admin",       "department": "الإدارة العامة"},
                {"username": "manager_finance",   "password": "Finance@24",  "full_name": "خالد هنداوي",         "role": "manager",     "department": "مالية"},
                {"username": "requester_finance", "password": "Fin2024!",    "full_name": "موظف مالية",           "role": "requester",   "department": "مالية"},
                {"username": "manager_bizdev",    "password": "BizDev@24",   "full_name": "مدير تطوير الأعمال",  "role": "manager",     "department": "تطوير الأعمال"},
                {"username": "requester_bizdev",  "password": "Biz2024!",    "full_name": "موظف تطوير الأعمال",  "role": "requester",   "department": "تطوير الأعمال"},
                {"username": "manager_hr",        "password": "HumanR@24",   "full_name": "محمد السرحان",         "role": "manager",     "department": "موارد بشرية"},
                {"username": "requester_hr",      "password": "Hr2024!",     "full_name": "موظف موارد بشرية",    "role": "requester",   "department": "موارد بشرية"},
                {"username": "manager_exec",      "password": "Exec@2024",   "full_name": "خليل بالبي",          "role": "manager",     "department": "تنفيذية"},
                {"username": "procurement_user",  "password": "Procure@24",  "full_name": "مسؤول المشتريات",     "role": "procurement", "department": "المشتريات"},
            ]
            for u in users:
                db.add(User(
                    username=u["username"],
                    password_hash=generate_password_hash(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                    department=u["department"],
                ))
            db.commit()
    finally:
        db.close()

    return app


@pytest.fixture(scope="session")
def seeded_client(seeded_app):
    """عميل HTTP مع بيانات مستخدمين جاهزة"""
    return seeded_app.test_client()


# ==================== دوال مساعدة ====================

def login(client, username, password):
    """تسجيل الدخول وإرجاع التوكن"""
    res = client.post("/api/login", json={
        "username": username,
        "password": password,
    })
    assert res.status_code == 200, f"فشل تسجيل الدخول لـ {username}: {res.get_json()}"
    data = res.get_json()
    return data["token"]


def auth_header(token):
    """إنشاء header المصادقة"""
    return {"Authorization": f"Bearer {token}"}
