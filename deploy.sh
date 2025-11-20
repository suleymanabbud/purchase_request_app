#!/bin/bash

# سكريبت نشر نظام طلبات الشراء على VPS
# استخدم: bash deploy.sh

echo "========================================"
echo "   نشر نظام طلبات الشراء على VPS"
echo "========================================"

# متغيرات
SERVER_IP="72.60.32.88"
SERVER_USER="root"
APP_DIR="/opt/purchase_app"
DOMAIN="srv1073351.hstgr.cloud"

echo "🚀 بدء عملية النشر..."

# 1. تحديث النظام
echo "📦 تحديث النظام..."
ssh $SERVER_USER@$SERVER_IP "apt update && apt upgrade -y"

# 2. تثبيت المتطلبات الأساسية
echo "🔧 تثبيت المتطلبات الأساسية..."
ssh $SERVER_USER@$SERVER_IP "apt install python3.12 python3.12-venv python3.12-dev python3-pip nginx git curl wget unzip ufw -y"

# 3. إنشاء مستخدم التطبيق
echo "👤 إنشاء مستخدم التطبيق..."
ssh $SERVER_USER@$SERVER_IP "adduser --system --group --shell /bin/bash purchase_app || true"
ssh $SERVER_USER@$SERVER_IP "mkdir -p $APP_DIR"
ssh $SERVER_USER@$SERVER_IP "chown purchase_app:purchase_app $APP_DIR"

# 4. رفع الكود
echo "📤 رفع الكود إلى الخادم..."
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' ./ $SERVER_USER@$SERVER_IP:$APP_DIR/

# 5. إعداد البيئة الافتراضية
echo "🐍 إعداد البيئة الافتراضية..."
ssh $SERVER_USER@$SERVER_IP "cd $APP_DIR && python3.12 -m venv venv"
ssh $SERVER_USER@$SERVER_IP "cd $APP_DIR && source venv/bin/activate && pip install -r requirements.txt"

# 6. إعداد قاعدة البيانات
echo "🗄️ إعداد قاعدة البيانات..."
ssh $SERVER_USER@$SERVER_IP "mkdir -p $APP_DIR/database"
ssh $SERVER_USER@$SERVER_IP "chown purchase_app:purchase_app $APP_DIR/database"

# 7. إعداد Nginx
echo "🌐 إعداد Nginx..."
ssh $SERVER_USER@$SERVER_IP "cat > /etc/nginx/sites-available/purchase_app << 'EOF'
server {
    listen 80;
    server_name $SERVER_IP $DOMAIN;

    # ملفات الثابتة
    location /static/ {
        alias $APP_DIR/backend/static/;
    }

    # ملفات الواجهة الأمامية
    location / {
        root $APP_DIR/frontend;
        try_files \$uri \$uri/ @flask;
    }

    # تمرير الطلبات إلى Flask
    location @flask {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"

# تفعيل الموقع
ssh $SERVER_USER@$SERVER_IP "ln -sf /etc/nginx/sites-available/purchase_app /etc/nginx/sites-enabled/"
ssh $SERVER_USER@$SERVER_IP "rm -f /etc/nginx/sites-enabled/default"
ssh $SERVER_USER@$SERVER_IP "nginx -t && systemctl restart nginx && systemctl enable nginx"

# 8. إعداد Systemd Service
echo "⚙️ إعداد Systemd Service..."
ssh $SERVER_USER@$SERVER_IP "cat > /etc/systemd/system/purchase_app.service << 'EOF'
[Unit]
Description=Purchase Request App
After=network.target

[Service]
Type=simple
User=purchase_app
Group=purchase_app
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
Environment=FLASK_ENV=production
ExecStart=$APP_DIR/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

# تفعيل وتشغيل الخدمة
ssh $SERVER_USER@$SERVER_IP "systemctl daemon-reload && systemctl enable purchase_app && systemctl start purchase_app"

# 9. إعداد جدار الحماية
echo "🔥 إعداد جدار الحماية..."
ssh $SERVER_USER@$SERVER_IP "ufw default deny incoming && ufw default allow outgoing"
ssh $SERVER_USER@$SERVER_IP "ufw allow ssh && ufw allow 'Nginx Full' && ufw allow 5000"
ssh $SERVER_USER@$SERVER_IP "ufw --force enable"

# 10. اختبار التطبيق
echo "🧪 اختبار التطبيق..."
sleep 5
ssh $SERVER_USER@$SERVER_IP "systemctl status purchase_app"

echo ""
echo "✅ تم نشر التطبيق بنجاح!"
echo "🌐 يمكنك الوصول للتطبيق على:"
echo "   - HTTP: http://$SERVER_IP"
echo "   - HTTP: http://$DOMAIN"
echo ""
echo "🔐 الحسابات الجاهزة:"
echo "   - admin/admin123 (مدير النظام)"
echo "   - manager1/pass123 (المدير المباشر)"
echo "   - finance1/pass123 (المدير المالي)"
echo "   - disb1/pass123 (أمر الصرف)"
echo "   - requester1/pass123 (مقدم الطلب)"
echo ""
echo "📋 أوامر مفيدة:"
echo "   - مراقبة الخدمة: ssh $SERVER_USER@$SERVER_IP 'systemctl status purchase_app'"
echo "   - مراقبة السجلات: ssh $SERVER_USER@$SERVER_IP 'journalctl -u purchase_app -f'"
echo "   - إعادة تشغيل: ssh $SERVER_USER@$SERVER_IP 'systemctl restart purchase_app'"
