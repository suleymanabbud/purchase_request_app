#!/bin/bash

# إصلاح مشاكل الخادم
echo "🔧 إصلاح مشاكل الخادم..."

# 1. التحقق من حالة nginx
echo "📋 التحقق من حالة nginx..."
systemctl status nginx

# 2. التحقق من حالة التطبيق
echo "📋 التحقق من حالة التطبيق..."
ps aux | grep python

# 3. إعادة تشغيل nginx
echo "🔄 إعادة تشغيل nginx..."
systemctl restart nginx

# 4. التحقق من المنافذ المفتوحة
echo "📋 المنافذ المفتوحة..."
netstat -tlnp | grep :80
netstat -tlnp | grep :5000

# 5. التحقق من ملفات nginx
echo "📋 إعدادات nginx..."
ls -la /etc/nginx/sites-available/
ls -la /etc/nginx/sites-enabled/

# 6. إعادة تشغيل التطبيق
echo "🔄 إعادة تشغيل التطبيق..."
cd /opt/purchase_app
pkill -f "python.*app.py"
nohup python3 app.py > app.log 2>&1 &

echo "✅ تم الانتهاء من الإصلاح"



