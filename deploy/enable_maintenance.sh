#!/bin/bash
# ============================================
# سكربت تفعيل وضع الصيانة
# يُنفذ من الجهاز المحلي
# ============================================

SERVER="root@72.60.32.88"
REMOTE_PATH="/opt/purchase_app"
NGINX_CONF="/etc/nginx/sites-available/purchase_app"

echo "========================================"
echo "  تفعيل وضع الصيانة"
echo "========================================"

# 1. رفع صفحة الصيانة
echo ""
echo "📄 [1/4] رفع صفحة الصيانة..."
scp frontend/maintenance.html ${SERVER}:${REMOTE_PATH}/frontend/maintenance.html
echo "  ✅ تم رفع صفحة الصيانة"

# 2. نسخ إعدادات nginx الأصلية احتياطياً + تفعيل وضع الصيانة
echo ""
echo "⚙️  [2/4] تفعيل وضع الصيانة في Nginx..."
scp nginx_maintenance.conf ${SERVER}:/tmp/nginx_maintenance.conf
ssh ${SERVER} << 'ENDSSH'
    # نسخة احتياطية من الإعدادات الحالية
    cp /etc/nginx/sites-available/purchase_app /etc/nginx/sites-available/purchase_app.backup 2>/dev/null || true
    cp /etc/nginx/conf.d/purchase_app.conf /etc/nginx/conf.d/purchase_app.conf.backup 2>/dev/null || true
    
    # تحديد الملف الصحيح
    if [ -f /etc/nginx/sites-available/purchase_app ]; then
        cp /tmp/nginx_maintenance.conf /etc/nginx/sites-available/purchase_app
        echo "  → تم تحديث sites-available"
    elif [ -f /etc/nginx/conf.d/purchase_app.conf ]; then
        cp /tmp/nginx_maintenance.conf /etc/nginx/conf.d/purchase_app.conf
        echo "  → تم تحديث conf.d"
    else
        # إنشاء ملف جديد
        cp /tmp/nginx_maintenance.conf /etc/nginx/sites-available/purchase_app
        ln -sf /etc/nginx/sites-available/purchase_app /etc/nginx/sites-enabled/purchase_app 2>/dev/null || true
        echo "  → تم إنشاء ملف جديد"
    fi
    
    # اختبار الإعدادات
    nginx -t
    if [ $? -eq 0 ]; then
        systemctl reload nginx
        echo "  ✅ Nginx تم إعادة تحميله"
    else
        echo "  ❌ خطأ في إعدادات Nginx!"
        exit 1
    fi
ENDSSH
echo "  ✅ وضع الصيانة مفعل في Nginx"

# 3. نسخ احتياطي لقاعدة البيانات
echo ""
echo "💾 [3/4] نسخ احتياطي لقاعدة البيانات..."
ssh ${SERVER} << 'ENDSSH'
    cd /opt/purchase_app
    BACKUP_DIR="backups"
    mkdir -p ${BACKUP_DIR}
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    
    # نسخ قاعدة البيانات
    if [ -f backend/purchase_requests.db ]; then
        cp backend/purchase_requests.db ${BACKUP_DIR}/purchase_requests_${TIMESTAMP}.db
        echo "  ✅ نسخة احتياطية: ${BACKUP_DIR}/purchase_requests_${TIMESTAMP}.db"
    elif [ -f purchase_requests.db ]; then
        cp purchase_requests.db ${BACKUP_DIR}/purchase_requests_${TIMESTAMP}.db
        echo "  ✅ نسخة احتياطية: ${BACKUP_DIR}/purchase_requests_${TIMESTAMP}.db"
    else
        echo "  ⚠️ لم يتم العثور على قاعدة البيانات!"
        find /opt/purchase_app -name "*.db" -type f 2>/dev/null
    fi
ENDSSH

# 4. إيقاف التطبيق
echo ""
echo "🛑 [4/4] إيقاف التطبيق..."
ssh ${SERVER} << 'ENDSSH'
    systemctl stop purchase_app 2>/dev/null || true
    echo "  ✅ تم إيقاف التطبيق"
ENDSSH

echo ""
echo "========================================"
echo "  ✅ وضع الصيانة مفعّل بنجاح!"
echo "========================================"
echo ""
echo "  الموقع يعرض صفحة الصيانة الآن"
echo "  يمكنك الآن إجراء التعديلات بأمان"
echo ""
echo "  لإلغاء وضع الصيانة، شغّل:"
echo "  bash disable_maintenance.sh"
echo "========================================"
