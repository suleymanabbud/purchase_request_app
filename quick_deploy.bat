@echo off
echo ========================================
echo   نشر نظام طلبات الشراء على VPS
echo ========================================

echo 1. تحديث النظام...
ssh root@72.60.32.88 "apt update && apt upgrade -y"

echo 2. تثبيت المتطلبات...
ssh root@72.60.32.88 "apt install python3.12 python3.12-venv python3.12-dev python3-pip nginx git curl wget unzip ufw -y"

echo 3. إنشاء مستخدم التطبيق...
ssh root@72.60.32.88 "adduser --system --group --shell /bin/bash purchase_app || true"
ssh root@72.60.32.88 "mkdir -p /opt/purchase_app"
ssh root@72.60.32.88 "chown purchase_app:purchase_app /opt/purchase_app"

echo 4. رفع الكود...
scp -r . root@72.60.32.88:/opt/purchase_app/

echo 5. إعداد البيئة...
ssh root@72.60.32.88 "cd /opt/purchase_app && python3.12 -m venv venv"
ssh root@72.60.32.88 "cd /opt/purchase_app && source venv/bin/activate && pip install -r requirements.txt"

echo 6. إعداد قاعدة البيانات...
ssh root@72.60.32.88 "mkdir -p /opt/purchase_app/database"
ssh root@72.60.32.88 "chown purchase_app:purchase_app /opt/purchase_app/database"

echo 7. إعداد Nginx...
ssh root@72.60.32.88 "cat > /etc/nginx/sites-available/purchase_app << 'EOF'
server {
    listen 80;
    server_name 72.60.32.88 srv1073351.hstgr.cloud;

    location /static/ {
        alias /opt/purchase_app/backend/static/;
    }

    location / {
        root /opt/purchase_app/frontend;
        try_files \$uri \$uri/ @flask;
    }

    location @flask {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"

ssh root@72.60.32.88 "ln -sf /etc/nginx/sites-available/purchase_app /etc/nginx/sites-enabled/"
ssh root@72.60.32.88 "rm -f /etc/nginx/sites-enabled/default"
ssh root@72.60.32.88 "nginx -t && systemctl restart nginx && systemctl enable nginx"

echo 8. إعداد Systemd Service...
ssh root@72.60.32.88 "cat > /etc/systemd/system/purchase_app.service << 'EOF'
[Unit]
Description=Purchase Request App
After=network.target

[Service]
Type=simple
User=purchase_app
Group=purchase_app
WorkingDirectory=/opt/purchase_app
Environment=PATH=/opt/purchase_app/venv/bin
Environment=FLASK_ENV=production
ExecStart=/opt/purchase_app/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

ssh root@72.60.32.88 "systemctl daemon-reload && systemctl enable purchase_app && systemctl start purchase_app"

echo 9. إعداد جدار الحماية...
ssh root@72.60.32.88 "ufw default deny incoming && ufw default allow outgoing"
ssh root@72.60.32.88 "ufw allow ssh && ufw allow 'Nginx Full' && ufw allow 5000"
ssh root@72.60.32.88 "ufw --force enable"

echo 10. اختبار التطبيق...
timeout 5
ssh root@72.60.32.88 "systemctl status purchase_app"

echo.
echo ========================================
echo   تم نشر التطبيق بنجاح!
echo ========================================
echo يمكنك الوصول للتطبيق على:
echo - HTTP: http://72.60.32.88
echo - HTTP: http://srv1073351.hstgr.cloud
echo.
echo الحسابات الجاهزة:
echo - admin/admin123 (مدير النظام)
echo - manager1/pass123 (المدير المباشر)
echo - finance1/pass123 (المدير المالي)
echo - disb1/pass123 (أمر الصرف)
echo - requester1/pass123 (مقدم الطلب)
echo ========================================
pause
