# دليل نشر ميزة الموافقة على مستوى البنود

## الملفات المعدلة:
1. `backend/models.py` - إضافة حقول للبنود
2. `backend/routes/workflow.py` - إضافة APIs جديدة
3. `backend/migrate_item_approval.py` - سكربت الترحيل (جديد)

---

## خطوات النشر:

### 1. رفع الملفات للخادم:

```bash
# من جهازك المحلي
scp backend/models.py backend/routes/workflow.py backend/migrate_item_approval.py root@72.60.32.88:/opt/purchase_app/backend/
scp backend/routes/workflow.py root@72.60.32.88:/opt/purchase_app/backend/routes/
```

### 2. على الخادم - تشغيل الترحيل:

```bash
ssh root@72.60.32.88
cd /opt/purchase_app
source venv/bin/activate

# تشغيل سكربت الترحيل
python3 backend/migrate_item_approval.py
```

### 3. إعادة تشغيل التطبيق:

```bash
systemctl restart purchase_app
```

### 4. التحقق من APIs الجديدة:

```bash
# اختبار جلب بنود طلب
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://72.60.32.88:5000/api/requests/1/items

# اختبار رفض بند
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action":"reject","reason":"السعر مرتفع"}' \
  http://72.60.32.88:5000/api/requests/1/items/1/action
```

---

## APIs الجديدة:

### 1. جلب بنود الطلب:
```
GET /api/requests/{request_id}/items
```

### 2. الموافقة/رفض بند واحد:
```
POST /api/requests/{request_id}/items/{item_id}/action
Body: {
  "action": "approve" | "reject",
  "reason": "سبب الرفض (مطلوب عند الرفض)"
}
```

### 3. الموافقة/رفض عدة بنود:
```
POST /api/requests/{request_id}/items/bulk-action
Body: {
  "items": [
    { "id": 1, "action": "approve" },
    { "id": 2, "action": "reject", "reason": "السبب" }
  ]
}
```

---

## الخطوات التالية (Frontend):

بعد نشر Backend، يجب تحديث الواجهات:

1. **manager-dashboard.html** - إضافة أزرار موافقة/رفض لكل بند
2. **finance-dashboard.html** - نفس التحديث
3. **index.html** - عرض حالة البنود لطالب الشراء

هل تريد أن أبدأ بتحديث الواجهات الآن؟
