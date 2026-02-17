"""
إعدادات المشروع الموحّدة — تُقرأ من متغيرات البيئة أو .env
"""

import os

# تحميل .env إذا كان موجوداً (بدون اعتماد على python-dotenv)
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_file):
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ────────────────────────────────────────────
# إعدادات عامة
# ────────────────────────────────────────────

APP_NAME = "نظام إدارة طلبات الشراء"
COMPANY_NAME = "صرح القابضة"

# ────────────────────────────────────────────
# قاعدة البيانات
# ────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, 'database', 'purchase_requests.db')}"
)

# ────────────────────────────────────────────
# الأمان — JWT
# ────────────────────────────────────────────

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-2024")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

# ────────────────────────────────────────────
# الخادم
# ────────────────────────────────────────────

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

# ────────────────────────────────────────────
# CORS
# ────────────────────────────────────────────

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

# ────────────────────────────────────────────
# رفع الملفات
# ────────────────────────────────────────────

UPLOAD_FOLDER = os.path.join(BASE_DIR, "backend", "uploads")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
