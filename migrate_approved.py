#!/usr/bin/env python3
"""
استيراد الطلبات المعتمدة من النسخة الاحتياطية القديمة إلى القاعدة الجديدة.
يُشغّل على الـ VPS:
    cd /root/purchase_request_app
    python migrate_approved.py /opt/purchase_app_backup/database/purchase_requests.db
"""

import sys
import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# المسار الافتراضي للقاعدة الجديدة
NEW_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "purchase_requests.db")


def get_columns(cursor, table):
    """جلب أسماء أعمدة جدول"""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def migrate(old_db_path, new_db_path=NEW_DB):
    """استيراد الطلبات المعتمدة من القديمة للجديدة"""

    if not os.path.exists(old_db_path):
        logger.error(f"❌ ملف القاعدة القديمة غير موجود: {old_db_path}")
        return

    if not os.path.exists(new_db_path):
        logger.error(f"❌ ملف القاعدة الجديدة غير موجود: {new_db_path}")
        return

    logger.info(f"📂 القاعدة القديمة: {old_db_path}")
    logger.info(f"📂 القاعدة الجديدة: {new_db_path}")

    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row
    old_cur = old_conn.cursor()

    new_conn = sqlite3.connect(new_db_path)
    new_conn.row_factory = sqlite3.Row
    new_cur = new_conn.cursor()

    try:
        # === 1. جلب أعمدة الجداول في القاعدة الجديدة ===
        new_pr_cols = get_columns(new_cur, "purchase_requests")
        new_pi_cols = get_columns(new_cur, "purchase_items")

        # تحقق من وجود جدول approval_history
        new_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='approval_history'")
        has_ah = new_cur.fetchone() is not None
        new_ah_cols = get_columns(new_cur, "approval_history") if has_ah else []

        old_pr_cols = get_columns(old_cur, "purchase_requests")
        old_pi_cols = get_columns(old_cur, "purchase_items")
        old_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='approval_history'")
        old_has_ah = old_cur.fetchone() is not None

        logger.info(f"أعمدة purchase_requests الجديدة: {len(new_pr_cols)}")
        logger.info(f"أعمدة purchase_requests القديمة: {len(old_pr_cols)}")

        # === 2. جلب الطلبات المعتمدة من القديمة ===
        old_cur.execute("""
            SELECT * FROM purchase_requests 
            WHERE status IN ('approved', 'completed', 'pending_finance', 'pending_disbursement', 'pending_procurement')
            ORDER BY id
        """)
        old_requests = old_cur.fetchall()
        logger.info(f"📋 عدد الطلبات للاستيراد: {len(old_requests)}")

        if not old_requests:
            logger.info("لا توجد طلبات معتمدة في القاعدة القديمة")
            return

        # === 3. جلب order_numbers الموجودة لتجنب التكرار ===
        new_cur.execute("SELECT order_number FROM purchase_requests WHERE order_number IS NOT NULL")
        existing_orders = {row[0] for row in new_cur.fetchall()}
        logger.info(f"طلبات موجودة مسبقاً: {len(existing_orders)}")

        # === 4. الأعمدة المشتركة (بدون id) ===
        common_pr_cols = [c for c in old_pr_cols if c in new_pr_cols and c != 'id']
        common_pi_cols = [c for c in old_pi_cols if c in new_pi_cols and c != 'id']
        logger.info(f"أعمدة مشتركة (requests): {common_pr_cols}")
        logger.info(f"أعمدة مشتركة (items): {common_pi_cols}")

        imported = 0
        skipped = 0
        items_imported = 0
        history_imported = 0

        for old_req in old_requests:
            old_req_dict = dict(old_req)
            order_num = old_req_dict.get('order_number')

            # تجنب التكرار
            if order_num and order_num in existing_orders:
                skipped += 1
                continue

            old_id = old_req_dict['id']

            # إدراج الطلب
            values = {col: old_req_dict.get(col) for col in common_pr_cols}
            cols_str = ', '.join(values.keys())
            placeholders = ', '.join(['?'] * len(values))
            new_cur.execute(
                f"INSERT INTO purchase_requests ({cols_str}) VALUES ({placeholders})",
                list(values.values())
            )
            new_id = new_cur.lastrowid

            # إدراج البنود
            old_cur.execute("SELECT * FROM purchase_items WHERE request_id = ?", (old_id,))
            old_items = old_cur.fetchall()
            for item in old_items:
                item_dict = dict(item)
                item_values = {col: item_dict.get(col) for col in common_pi_cols if col != 'request_id'}
                item_values['request_id'] = new_id
                item_cols = ', '.join(item_values.keys())
                item_ph = ', '.join(['?'] * len(item_values))
                new_cur.execute(
                    f"INSERT INTO purchase_items ({item_cols}) VALUES ({item_ph})",
                    list(item_values.values())
                )
                items_imported += 1

            # إدراج سجل الموافقات
            if old_has_ah and has_ah:
                old_ah_cols_list = get_columns(old_cur, "approval_history")
                common_ah_cols = [c for c in old_ah_cols_list if c in new_ah_cols and c not in ('id', 'request_id')]
                
                old_cur.execute("SELECT * FROM approval_history WHERE request_id = ?", (old_id,))
                old_history = old_cur.fetchall()
                for hist in old_history:
                    hist_dict = dict(hist)
                    hist_values = {col: hist_dict.get(col) for col in common_ah_cols}
                    hist_values['request_id'] = new_id
                    hist_cols = ', '.join(hist_values.keys())
                    hist_ph = ', '.join(['?'] * len(hist_values))
                    new_cur.execute(
                        f"INSERT INTO approval_history ({hist_cols}) VALUES ({hist_ph})",
                        list(hist_values.values())
                    )
                    history_imported += 1

            imported += 1
            if order_num:
                existing_orders.add(order_num)

        new_conn.commit()

        logger.info("=" * 50)
        logger.info(f"✅ تم الاستيراد بنجاح!")
        logger.info(f"   الطلبات المستوردة: {imported}")
        logger.info(f"   البنود المستوردة: {items_imported}")
        logger.info(f"   سجلات الموافقة: {history_imported}")
        logger.info(f"   تم تخطيها (مكررة): {skipped}")
        logger.info("=" * 50)

    except Exception as e:
        new_conn.rollback()
        logger.error(f"❌ خطأ في الاستيراد: {e}")
        import traceback
        traceback.print_exc()
    finally:
        old_conn.close()
        new_conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  python migrate_approved.py <مسار_القاعدة_القديمة>")
        print()
        print("مثال:")
        print("  python migrate_approved.py /opt/purchase_app_backup/database/purchase_requests.db")
        sys.exit(1)

    migrate(sys.argv[1])
