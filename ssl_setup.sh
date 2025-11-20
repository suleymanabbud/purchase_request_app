#!/bin/bash

# سكريبت إعداد SSL Certificate
# استخدم: bash ssl_setup.sh

echo "🔒 إعداد SSL Certificate للنظام..."

SERVER_IP="72.60.32.88"
DOMAIN="srv1073351.hstgr.cloud"

echo "📋 تأكد من أن النطاق يشير إلى IP الخادم: $SERVER_IP"
echo "📋 تأكد من أن Nginx يعمل بشكل صحيح"
echo ""

# تثبيت Certbot
echo "🔧 تثبيت Certbot..."
ssh root@$SERVER_IP "apt install certbot python3-certbot-nginx -y"

# الحصول على شهادة SSL
echo "🔐 الحصول على شهادة SSL..."
ssh root@$SERVER_IP "certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN"

# إعداد تجديد تلقائي
echo "🔄 إعداد التجديد التلقائي..."
ssh root@$SERVER_IP "systemctl enable certbot.timer"
ssh root@$SERVER_IP "systemctl start certbot.timer"

echo ""
echo "✅ تم إعداد SSL بنجاح!"
echo "🌐 يمكنك الوصول للتطبيق على:"
echo "   - HTTPS: https://$DOMAIN"
echo "   - HTTP: http://$DOMAIN (سيتم توجيهه إلى HTTPS)"
echo ""
echo "🔍 للتحقق من الشهادة:"
echo "   - https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
