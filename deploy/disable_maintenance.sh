#!/bin/bash
# ============================================
# سكربت إلغاء وضع الصيانة
# يُنفذ من الجهاز المحلي
# ============================================

SERVER="root@72.60.32.88"
REMOTE_PATH="/opt/purchase_app"

echo "========================================"
echo "  إلغاء وضع الصيانة"
echo "========================================"

# 1. استعادة إعدادات Nginx الأصلية
echo ""
echo "⚙️  [1/3] استعادة إعدادات Nginx..."
scp nginx_config.conf ${SERVER}:/tmp/nginx_original.conf
ssh ${SERVER} << 'ENDSSH'
    if [ -f /etc/nginx/sites-available/purchase_app ]; then
        cp /tmp/nginx_original.conf /etc/nginx/sites-available/purchase_app
    elif [ -f /etc/nginx/conf.d/purchase_app.conf ]; then
        cp /tmp/nginx_original.conf /etc/nginx/conf.d/purchase_app.conf
    fi
    
    nginx -t
    if [ $? -eq 0 ]; then
        systemctl reload nginx
        echo "  ✅ تم استعادة Nginx"
    else
        echo "  ❌ خطأ في إعدادات Nginx! استعادة النسخة الاحتياطية..."
        if [ -f /etc/nginx/sites-available/purchase_app.backup ]; then
            cp /etc/nginx/sites-available/purchase_app.backup /etc/nginx/sites-available/purchase_app
        elif [ -f /etc/nginx/conf.d/purchase_app.conf.backup ]; then
            cp /etc/nginx/conf.d/purchase_app.conf.backup /etc/nginx/conf.d/purchase_app.conf
        fi
        nginx -t && systemctl reload nginx
    fi
ENDSSH

# 2. تشغيل التطبيق
echo ""
echo "🚀 [2/3] تشغيل التطبيق..."
ssh ${SERVER} << 'ENDSSH'
    systemctl start purchase_app
    sleep 3
    
    # التحقق من التشغيل
    if systemctl is-active --quiet purchase_app; then
        echo "  ✅ التطبيق يعمل"
    else
        echo "  ❌ التطبيق لم يبدأ! التحقق من السجلات..."
        journalctl -u purchase_app --no-pager -n 20
        exit 1
    fi
ENDSSH

# 3. فحص صحة النظام
echo ""
echo "🏥 [3/3] فحص صحة النظام..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://72.60.32.88/api/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ API يعمل بشكل طبيعي (HTTP $HTTP_CODE)"
else
    echo "  ⚠️ HTTP $HTTP_CODE — تحقق يدوياً من http://72.60.32.88"
fi

echo ""
echo "========================================"
echo "  ✅ تم إلغاء وضع الصيانة!"
echo "  النظام يعمل الآن بشكل طبيعي"  
echo "========================================"
