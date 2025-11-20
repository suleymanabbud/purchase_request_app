# backend/routes/admin.py
from flask import Blueprint, request, Response, render_template_string, jsonify, current_app
from base64 import b64decode
from ..database import SessionLocal
from ..models import PurchaseRequest  # غيّر الاسم إذا كان موديلك باسم مختلف

bp = Blueprint("admin", __name__)  # بدون url_prefix حتى يكون /admin بالضبط

# -------- Basic Auth بسيط للأدمن --------
def _unauthorized():
    return Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Dashboard"'})

def _require_admin():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        userpass = b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        username, password = userpass.split(":", 1)
    except Exception:
        return False
    return (
        username == current_app.config.get("ADMIN_USER", "admin")
        and password == current_app.config.get("ADMIN_PASS", "admin123")
    )

def admin_only(fn):
    def wrapper(*args, **kwargs):
        if not _require_admin():
            return _unauthorized()
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

# -------- صفحة الداشبورد نفسها --------
@bp.route("/admin")
@admin_only
def admin_page():
    html = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>لوحة التحكم - المشتريات</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{font-family:Tahoma,Arial; background:#f5f7f8; padding:20px;}
  h1{margin:0 0 10px; color:#2d3e2e}
  .card{background:#fff; border:1px solid #e3e6e8; border-radius:10px; padding:16px; margin:16px 0;}
  table{width:100%; border-collapse:collapse; margin-top:10px;}
  th,td{border:1px solid #d8dcdf; padding:8px 10px; text-align:center; font-size:13px;}
  th{background:#698163; color:#fff;}
  .pill{display:inline-block; padding:2px 8px; border-radius:999px; background:#e9f5ea; color:#256029; font-size:12px;}
  .muted{color:#59656a; font-size:12px;}
  .topbar{display:flex; gap:12px; align-items:center; justify-content:space-between;}
  .btn{background:#698163; color:#fff; border:none; padding:8px 12px; border-radius:8px; cursor:pointer;}
  .btn:hover{background:#2d3e2e;}
</style>
</head>
<body>
  <div class="topbar">
    <h1>لوحة التحكم</h1>
    <button class="btn" onclick="location.reload()">تحديث</button>
  </div>

  <div class="card">
    <h3>طلبات الشراء <span class="pill" id="count-requests">0</span></h3>
    <div class="muted">آخر 50 طلبًا</div>
    <table id="tbl-requests">
      <thead>
        <tr>
          <th>#</th>
          <th>رقم الطلب</th>
          <th>الطالب</th>
          <th>القسم</th>
          <th>الإجمالي</th>
          <th>العملة</th>
          <th>تاريخ التسليم</th>
        </tr>
      </thead>
      <tbody><tr><td colspan="7">جارٍ التحميل...</td></tr></tbody>
    </table>
  </div>

<script>
function fmt(n){ return (n||0).toLocaleString('ar-SY',{minimumFractionDigits:2,maximumFractionDigits:2}); }
fetch('/api/admin/requests', {headers: {}})
  .then(r => r.json())
  .then(rows => {
    const tb = document.querySelector('#tbl-requests tbody');
    tb.innerHTML = '';
    (rows||[]).forEach((row, i) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i+1}</td>
        <td>${row.order_number || '-'}</td>
        <td>${row.requester || '-'}</td>
        <td>${row.department || '-'}</td>
        <td>${fmt(row.total_amount)}</td>
        <td>${row.currency || '-'}</td>
        <td>${row.delivery_date || '-'}</td>
      `;
      tb.appendChild(tr);
    });
    document.getElementById('count-requests').textContent = (rows||[]).length;
  })
  .catch(() => {
    document.querySelector('#tbl-requests tbody').innerHTML =
      '<tr><td colspan="7">تعذر تحميل البيانات</td></tr>';
  });
</script>
</body>
</html>
"""
    return render_template_string(html)

# -------- API يعيد بيانات الطلبات للداشبورد --------
@bp.get("/api/admin/requests")
@admin_only
def admin_requests():
    limit = int(request.args.get("limit", 50))
    with SessionLocal() as db:
        q = db.query(PurchaseRequest).order_by(PurchaseRequest.id.desc()).limit(limit).all()
        data = []
        for r in q:
            data.append({
                "id": r.id,
                "order_number": getattr(r, "order_number", None),
                "requester": getattr(r, "requester", None),
                "department": getattr(r, "department", None),
                "delivery_date": getattr(r, "delivery_date", None),
                "currency": getattr(r, "currency", None),
                "total_amount": float(getattr(r, "total_amount", 0) or 0.0),
            })
        return jsonify(data)
