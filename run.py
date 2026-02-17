#!/usr/bin/env python3
"""
نقطة تشغيل التطبيق — Purchase Request System
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """تشغيل التطبيق"""
    from backend.config import HOST, PORT, DEBUG

    # ضمان وجود مجلد قاعدة البيانات
    os.makedirs("database", exist_ok=True)

    # إنشاء المستخدمين الافتراضيين
    from backend.seed_data import create_default_users
    create_default_users()

    # إنشاء وتشغيل التطبيق
    from backend.app import create_app
    app = create_app()

    mode = "الإنتاج" if not DEBUG else "التطوير"
    logger.info(f"تشغيل النظام في وضع {mode} على http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)


if __name__ == "__main__":
    main()
