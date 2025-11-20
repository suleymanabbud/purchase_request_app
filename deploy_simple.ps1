Write-Host "Starting deployment..." -ForegroundColor Green

Write-Host "Step 1: Update system..." -ForegroundColor Yellow
ssh root@72.60.32.88 "apt update"

Write-Host "Step 2: Install requirements..." -ForegroundColor Yellow
ssh root@72.60.32.88 "apt install python3.12 python3.12-venv python3.12-dev python3-pip nginx git curl wget unzip ufw -y"

Write-Host "Step 3: Create app user..." -ForegroundColor Yellow
ssh root@72.60.32.88 "adduser --system --group --shell /bin/bash purchase_app"
ssh root@72.60.32.88 "mkdir -p /opt/purchase_app"
ssh root@72.60.32.88 "chown purchase_app:purchase_app /opt/purchase_app"

Write-Host "Step 4: Upload code..." -ForegroundColor Yellow
scp -r . root@72.60.32.88:/opt/purchase_app/

Write-Host "Step 5: Setup environment..." -ForegroundColor Yellow
ssh root@72.60.32.88 "cd /opt/purchase_app && python3.12 -m venv venv"
ssh root@72.60.32.88 "cd /opt/purchase_app && source venv/bin/activate && pip install -r requirements.txt"

Write-Host "Step 6: Setup database..." -ForegroundColor Yellow
ssh root@72.60.32.88 "mkdir -p /opt/purchase_app/database"
ssh root@72.60.32.88 "chown purchase_app:purchase_app /opt/purchase_app/database"

Write-Host "Step 7: Setup Nginx..." -ForegroundColor Yellow
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
ssh root@72.60.32.88 "nginx -t"
ssh root@72.60.32.88 "systemctl restart nginx"
ssh root@72.60.32.88 "systemctl enable nginx"

Write-Host "Step 8: Setup systemd service..." -ForegroundColor Yellow
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

ssh root@72.60.32.88 "systemctl daemon-reload"
ssh root@72.60.32.88 "systemctl enable purchase_app"
ssh root@72.60.32.88 "systemctl start purchase_app"

Write-Host "Step 9: Setup firewall..." -ForegroundColor Yellow
ssh root@72.60.32.88 "ufw default deny incoming"
ssh root@72.60.32.88 "ufw default allow outgoing"
ssh root@72.60.32.88 "ufw allow ssh"
ssh root@72.60.32.88 "ufw allow 'Nginx Full'"
ssh root@72.60.32.88 "ufw allow 5000"
ssh root@72.60.32.88 "ufw --force enable"

Write-Host "Step 10: Test application..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
ssh root@72.60.32.88 "systemctl status purchase_app"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Access the application at:" -ForegroundColor Cyan
Write-Host "- HTTP: http://72.60.32.88" -ForegroundColor White
Write-Host "- HTTP: http://srv1073351.hstgr.cloud" -ForegroundColor White
Write-Host ""
Write-Host "Default accounts:" -ForegroundColor Cyan
Write-Host "- admin/admin123 (System Admin)" -ForegroundColor White
Write-Host "- manager1/pass123 (Manager)" -ForegroundColor White
Write-Host "- finance1/pass123 (Finance Manager)" -ForegroundColor White
Write-Host "- disb1/pass123 (Disbursement Officer)" -ForegroundColor White
Write-Host "- requester1/pass123 (Requester)" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
