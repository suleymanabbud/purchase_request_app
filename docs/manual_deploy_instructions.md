# دليل النشر اليدوي على VPS

## معلومات الخادم
- **IP**: 72.60.32.88
- **Domain**: srv1073351.hstgr.cloud
- **Username**: root
- **Password**: (من Hostinger)

## الخطوات اليدوية:

### 1. الاتصال بالخادم
```bash
# استخدم PuTTY أو أي عميل SSH
ssh root@72.60.32.88
```

### 2. تحديث النظام
```bash
apt update && apt upgrade -y
```

### 3. تثبيت المتطلبات
```bash
apt install python3.12 python3.12-venv python3.12-dev python3-pip nginx git curl wget unzip ufw -y
```

### 4. إنشاء مستخدم التطبيق
```bash
adduser --system --group --shell /bin/bash purchase_app
mkdir -p /opt/purchase_app
chown purchase_app:purchase_app /opt/purchase_app
```

### 5. رفع الملفات
```bash
# استخدم WinSCP أو FileZilla لرفع جميع ملفات المشروع إلى /opt/purchase_app/
```

### 6. إعداد البيئة
```bash
cd /opt/purchase_app
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7. إعداد قاعدة البيانات
```bash
mkdir -p /opt/purchase_app/database
chown purchase_app:purchase_app /opt/purchase_app/database
```

### 8. إعداد Nginx
```bash
cat > /etc/nginx/sites-available/purchase_app << 'EOF'
server {
    listen 80;
    server_name 72.60.32.88 srv1073351.hstgr.cloud;

    location /static/ {
        alias /opt/purchase_app/backend/static/;
    }

    location / {
        root /opt/purchase_app/frontend;
        try_files $uri $uri/ @flask;
    }

    location @flask {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/purchase_app /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
systemctl enable nginx
```

### 9. إعداد Systemd Service
```bash
cat > /etc/systemd/system/purchase_app.service << 'EOF'
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
EOF

systemctl daemon-reload
systemctl enable purchase_app
systemctl start purchase_app
```

### 10. إعداد جدار الحماية
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw allow 5000
ufw --force enable
```

### 11. اختبار التطبيق
```bash
systemctl status purchase_app
```

## الوصول للتطبيق:
- **HTTP**: http://72.60.32.88
- **HTTP**: http://srv1073351.hstgr.cloud

## الحسابات الجاهزة:
- admin/admin123 (مدير النظام)
- manager1/pass123 (المدير المباشر)
- finance1/pass123 (المدير المالي)
- disb1/pass123 (أمر الصرف)
- requester1/pass123 (مقدم الطلب)
