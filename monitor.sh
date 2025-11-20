#!/bin/bash

# سكريبت مراقبة النظام
# استخدم: bash monitor.sh

SERVER_IP="72.60.32.88"
DOMAIN="srv1073351.hstgr.cloud"

echo "📊 مراقبة نظام طلبات الشراء"
echo "================================"

# حالة الخدمة
echo "🔍 حالة الخدمة:"
ssh root@$SERVER_IP "systemctl status purchase_app --no-pager"

echo ""
echo "📋 آخر 20 سطر من السجلات:"
ssh root@$SERVER_IP "journalctl -u purchase_app --no-pager -n 20"

echo ""
echo "🌐 حالة Nginx:"
ssh root@$SERVER_IP "systemctl status nginx --no-pager"

echo ""
echo "📊 استخدام الذاكرة:"
ssh root@$SERVER_IP "free -h"

echo ""
echo "💾 مساحة القرص:"
ssh root@$SERVER_IP "df -h"

echo ""
echo "🌐 اختبار الاتصال:"
echo "   - HTTP: http://$SERVER_IP"
echo "   - HTTP: http://$DOMAIN"
echo "   - HTTPS: https://$DOMAIN"

echo ""
echo "🔧 أوامر مفيدة:"
echo "   - إعادة تشغيل التطبيق: ssh root@$SERVER_IP 'systemctl restart purchase_app'"
echo "   - مراقبة السجلات: ssh root@$SERVER_IP 'journalctl -u purchase_app -f'"
echo "   - إعادة تشغيل Nginx: ssh root@$SERVER_IP 'systemctl restart nginx'"
echo "   - مراقبة Nginx: ssh root@$SERVER_IP 'tail -f /var/log/nginx/access.log'"
