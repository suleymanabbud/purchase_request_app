from flask import Blueprint, request, jsonify
from ..database import SessionLocal
from ..models import PurchaseRequest, PurchaseItem, ApprovalHistory
from ..utils.auth import require_auth_and_roles

bp = Blueprint("requests", __name__, url_prefix="/api")

@bp.route("/requests", methods=["POST"])
@require_auth_and_roles("requester","admin","manager")
def create_request():
    payload = request.get_json(force=True, silent=True) or {}
    required = ["requester","department","delivery_address","delivery_date","project_code","order_number","currency","total_amount","items"]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"حقول ناقصة: {', '.join(missing)}"}), 400

    user = getattr(request, "user", {}) or {}
    creator = user.get("username") or user.get("name") or user.get("email") or payload.get("requester")
    user_role = user.get("role")
    user_department = user.get("department")

    db = SessionLocal()
    try:
        # تحديد الـ workflow حسب دور المستخدم
        if user_role == "manager" and user_department == "تطوير الأعمال":
            # مدير تطوير الأعمال - يتجاوز المدير المباشر
            status = "pending_finance"
            current_stage = "finance"
            next_role = "finance"
            print(f"🔄 مدير تطوير الأعمال - يتجاوز المدير المباشر")
        else:
            # موظف عادي - يحتاج موافقة المدير المباشر
            status = "pending_manager"
            current_stage = "manager"
            next_role = "manager"
            print(f"🔄 موظف عادي - يحتاج موافقة المدير المباشر")

        # جمع بيانات الموافقات
        approval_data = payload.get("approval_data", {})
        print(f"🔍 Debug - approval_data: {approval_data}")
        
        # إنشاء طلب رئيسي مع التوجيه التلقائي
        pr = PurchaseRequest(
            requester=payload["requester"],
            department=payload["department"],
            delivery_address=payload["delivery_address"],
            delivery_date=payload["delivery_date"],
            project_code=payload["project_code"],
            order_number=payload["order_number"],
            currency=payload["currency"],
            total_amount=float(payload.get("total_amount") or 0.0),
            
            # 👇 التوجيه التلقائي حسب دور المستخدم
            status=status,
            current_stage=current_stage,
            next_role=next_role,
            created_by=creator,
            
            # بيانات جدول الموافقات
            requester_name=approval_data.get("requester_name", ""),
            requester_position=approval_data.get("requester_position", ""),
            manager_name=approval_data.get("manager_name", ""),
            manager_position=approval_data.get("manager_position", ""),
            finance_name=approval_data.get("finance_name", ""),
            finance_position=approval_data.get("finance_position", ""),
            disbursement_name=approval_data.get("disbursement_name", ""),
            disbursement_position=approval_data.get("disbursement_position", ""),
            requester_date=approval_data.get("requester_date", ""),
            manager_date=approval_data.get("manager_date", ""),
            finance_date=approval_data.get("finance_date", ""),
            disbursement_date=approval_data.get("disbursement_date", "")
        )
        
        print(f"🆕 إنشاء طلب جديد:")
        print(f"   - مقدم الطلب: {payload['requester']}")
        print(f"   - الإدارة: '{payload['department']}'")
        print(f"   - الحالة: {status}")
        print(f"   - المرحلة: {current_stage}")
        print(f"   - الدور التالي: {next_role}")
        print(f"   - بيانات الموافقات: {approval_data}")
        print(f"   - عدد الأصناف: {len(payload.get('items', []))}")
        db.add(pr)
        db.flush()  # للحصول على pr.id قبل الكوميت

        items = payload.get("items") or []
        for it in items:
            qty = float(it.get("quantity") or 0.0)
            price = float(it.get("price") or 0.0)
            total = qty * price
            db.add(PurchaseItem(
                request_id=pr.id,
                item_name=it.get("item_name",""),
                specification=it.get("specification",""),
                unit=it.get("unit",""),
                quantity=qty,
                price=price,
                total=total
            ))

        # اختياري: سجّل حدث "إنشاء"
        if status == "pending_finance":
            note = "تم إنشاء الطلب وتحويله إلى المدير المالي"
        else:
            note = "تم إنشاء الطلب وتحويله إلى المدير المباشر"
            
        db.add(ApprovalHistory(
            request_id=pr.id,
            actor_role="requester",
            actor_user=creator,
            action="create",
            note=note
        ))

        db.commit()
        return jsonify({"message": "تم إنشاء طلب الشراء بنجاح", "id": pr.id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/requests", methods=["GET"])
def list_requests():
    db = SessionLocal()
    try:
        out = []
        for pr in db.query(PurchaseRequest).order_by(PurchaseRequest.id.desc()).all():
            out.append({
                "id": pr.id,
                "requester": pr.requester,
                "department": pr.department,
                "delivery_address": pr.delivery_address,
                "delivery_date": pr.delivery_date,
                "project_code": pr.project_code,
                "order_number": pr.order_number,
                "currency": pr.currency or "SYP",
                "total_amount": pr.total_amount,
                "status": pr.status,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "items": [{
                    "id": it.id,
                    "item_name": it.item_name,
                    "specification": it.specification,
                    "unit": it.unit,
                    "quantity": it.quantity,
                    "price": it.price,
                    "total": it.total,
                } for it in pr.items]
            })
        return jsonify(out)
    finally:
        db.close()

@bp.route("/user/requests", methods=["GET"])
@require_auth_and_roles("requester","admin","manager","finance","disbursement")
def get_user_requests():
    user = getattr(request, "user", {}) or {}
    user_id = user.get("id")
    user_role = user.get("role")
    
    db = SessionLocal()
    try:
        out = []
        
        # جلب الطلبات حسب دور المستخدم
        if user_role == "requester":
            # الموظف يرى طلباته فقط
            requests = db.query(PurchaseRequest).filter(PurchaseRequest.created_by == user.get("username")).order_by(PurchaseRequest.id.desc()).all()
        elif user_role in ["manager", "finance", "disbursement"]:
            # المديرين يرون جميع الطلبات
            requests = db.query(PurchaseRequest).order_by(PurchaseRequest.id.desc()).all()
        else:
            # الأدوار الأخرى ترى طلباتها فقط
            requests = db.query(PurchaseRequest).filter(PurchaseRequest.created_by == user.get("username")).order_by(PurchaseRequest.id.desc()).all()
        
        for pr in requests:
            out.append({
                "id": pr.id,
                "requester": pr.requester,
                "department": pr.department,
                "delivery_address": pr.delivery_address,
                "delivery_date": pr.delivery_date,
                "project_code": pr.project_code,
                "order_number": pr.order_number,
                "currency": pr.currency or "SYP",
                "total_amount": pr.total_amount,
                "status": pr.status,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "items": [{
                    "id": it.id,
                    "item_name": it.item_name,
                    "specification": it.specification,
                    "unit": it.unit,
                    "quantity": it.quantity,
                    "price": it.price,
                    "total": it.total,
                } for it in pr.items]
            })
        return jsonify(out)
    finally:
        db.close()

@bp.route("/requests/<int:request_id>", methods=["GET"])
@require_auth_and_roles("requester","admin","manager","finance","disbursement")
def get_request_details(request_id):
    db = SessionLocal()
    try:
        pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
        if not pr:
            return jsonify({"error": "الطلب غير موجود"}), 404
        
        # Debug logging
        print(f"🔍 API Debug - الطلب {request_id}:")
        print(f"   delivery_address: {pr.delivery_address}")
        print(f"   delivery_date: {pr.delivery_date}")
        print(f"   project_code: {pr.project_code}")
        print(f"   items count: {len(pr.items)}")
        print(f"   approval_data: requester_name={pr.requester_name}, manager_name={pr.manager_name}")
        for item in pr.items:
            print(f"   item: {item.item_name} - {item.quantity} x {item.price} = {item.total}")
        
        return jsonify({
            "id": pr.id,
            "requester": pr.requester,
            "department": pr.department,
            "delivery_address": pr.delivery_address,
            "delivery_date": pr.delivery_date,
            "project_code": pr.project_code,
            "order_number": pr.order_number,
            "currency": pr.currency or "SYP",
            "total_amount": pr.total_amount,
            "status": pr.status,
            "current_stage": pr.current_stage,
            "next_role": pr.next_role,
            "created_by": pr.created_by,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "date": str(pr.created_at.date()) if pr.created_at else "",
            "items": [{
                "id": it.id,
                "item_name": it.item_name,
                "specification": it.specification,
                "unit": it.unit,
                "quantity": it.quantity,
                "price": it.price,
                "total": it.total,
            } for it in pr.items],
            "approval_data": {
                "requester_name": pr.requester_name or "",
                "requester_position": pr.requester_position or "",
                "manager_name": pr.manager_name or "",
                "manager_position": pr.manager_position or "",
                "finance_name": pr.finance_name or "",
                "finance_position": pr.finance_position or "",
                "disbursement_name": pr.disbursement_name or "",
                "disbursement_position": pr.disbursement_position or "",
                "requester_date": pr.requester_date or "",
                "manager_date": pr.manager_date or "",
                "finance_date": pr.finance_date or "",
                "disbursement_date": pr.disbursement_date or ""
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
