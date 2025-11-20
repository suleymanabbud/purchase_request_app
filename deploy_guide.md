# دليل نشر نظام طلبات الشراء على VPS

## معلومات الخادم
- **Hostname**: srv1073351.hstgr.cloud
- **IP**: 72.60.32.88
- **OS**: Ubuntu 25.04
- **User**: root

## الخطوات المطلوبة

### 1. الاتصال بالخادم
```bash
ssh root@72.60.32.88
```

### 2. تحديث النظام
```bash
apt update && apt upgrade -y
```

### 3. تثبيت المتطلبات الأساسية
```bash
# تثبيت Python 3.12
apt install python3.12 python3.12-venv python3.12-dev python3-pip -y

# تثبيت Nginx
apt install nginx -y

# تثبيت Git
apt install git -y

# تثبيت أدوات إضافية
apt install curl wget unzip -y
```

### 4. إنشاء مستخدم للتطبيق
```bash
# إنشاء مستخدم جديد
adduser --system --group --shell /bin/bash purchase_app

# إنشاء مجلد التطبيق
mkdir -p /opt/purchase_app
chown purchase_app:purchase_app /opt/purchase_app
```

### 5. رفع الكود إلى الخادم
```bash
# نسخ الملفات إلى الخادم (من جهازك المحلي)
scp -r . root@72.60.32.88:/opt/purchase_app/
```

### 6. إعداد البيئة الافتراضية
```bash
cd /opt/purchase_app
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7. إعداد قاعدة البيانات
```bash
# إنشاء مجلد قاعدة البيانات
mkdir -p /opt/purchase_app/database
chown purchase_app:purchase_app /opt/purchase_app/database

# تشغيل التطبيق لإنشاء قاعدة البيانات
python run.py
```

### 8. إعداد Nginx
```bash
# إنشاء ملف إعداد Nginx
cat > /etc/nginx/sites-available/purchase_app << 'EOF'
server {
    listen 80;
    server_name 72.60.32.88 srv1073351.hstgr.cloud;

    # ملفات الثابتة
    location /static/ {
        alias /opt/purchase_app/backend/static/;
    }

    # ملفات الواجهة الأمامية
    location / {
        root /opt/purchase_app/frontend;
        try_files $uri $uri/ @flask;
    }

    # تمرير الطلبات إلى Flask
    location @flask {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# تفعيل الموقع
ln -s /etc/nginx/sites-available/purchase_app /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# اختبار إعداد Nginx
nginx -t

# إعادة تشغيل Nginx
systemctl restart nginx
systemctl enable nginx
```

### 9. إعداد SSL Certificate (Let's Encrypt)
```bash
# تثبيت Certbot
apt install certbot python3-certbot-nginx -y

# الحصول على شهادة SSL
certbot --nginx -d srv1073351.hstgr.cloud
```

### 10. إنشاء Systemd Service
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
ExecStart=/opt/purchase_app/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# تفعيل وتشغيل الخدمة
systemctl daemon-reload
systemctl enable purchase_app
systemctl start purchase_app
```

### 11. إعداد جدار الحماية
```bash
# تثبيت UFW
apt install ufw -y

# إعداد القواعد
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw allow 5000

# تفعيل جدار الحماية
ufw enable
```

### 12. مراقبة النظام
```bash
# مراقبة حالة الخدمة
systemctl status purchase_app

# مراقبة السجلات
journalctl -u purchase_app -f

# مراقبة Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

## الوصول للتطبيق
- **HTTP**: http://72.60.32.88
- **HTTPS**: https://srv1073351.hstgr.cloud (بعد إعداد SSL)

## الحسابات الجاهزة
- admin/admin123 (مدير النظام)
- manager1/pass123 (المدير المباشر)
- finance1/pass123 (المدير المالي)
- disb1/pass123 (أمر الصرف)
- requester1/pass123 (مقدم الطلب)
