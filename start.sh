#!/bin/bash

echo "========================================"
echo "   نظام إدارة طلبات الشراء - صرح القابضة"
echo "========================================"
echo

echo "تثبيت المتطلبات..."
pip install -r requirements.txt

echo
echo "تشغيل الخادم..."
echo "يمكنك الوصول للتطبيق على:"
echo "- الخادم الخلفي: http://localhost:5000"
echo "- صفحة تسجيل الدخول: http://localhost:5500/frontend/login.html"
echo

python run.py
