from flask import Blueprint, request, jsonify
from ..utils.auth import require_roles, require_auth, require_auth_and_roles
from ..database import SessionLocal
from ..models import PurchaseRequest, PurchaseItem, ApprovalHistory, User
from ..utils.notifications import create_notification
from ..utils.watchers import get_request_watchers

bp = Blueprint("workflow", __name__, url_prefix="/api")

# دالة إعادة تهيئة قاعدة البيانات
@bp.post("/admin/reset-db")
@require_auth_and_roles("admin")
def reset_db():
    """
    يحذف جميع الطلبات وسجلات الموافقات والعناصر (للاستخدام الإداري فقط)
    """
    db = SessionLocal()
    try:
        db.query(ApprovalHistory).delete()
        db.query(PurchaseItem).delete()
        db.query(PurchaseRequest).delete()
        db.commit()
        return jsonify({"message": "تم حذف جميع الطلبات بنجاح"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

# الحالات المعتمدة
# requester ينشئ الطلب بحالة "pending_manager"
# manager -> approve => pending_finance / reject => rejected
# finance -> approve => pending_disbursement / reject => rejected
# disbursement -> approve => approved / reject => rejected

@bp.get("/requests")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement")
def list_requests():
    # فلاتر خفيفة (اختيارية)
    status = request.args.get("status")
    dept = request.args.get("department")
    db = SessionLocal()
    q = db.query(PurchaseRequest)
    # إذا لم يكن المستخدم admin، فلتر حسب إدارته تلقائياً
    user = getattr(request, "user", {}) or {}
    user_role = user.get("role")
    user_dept = user.get("department")
    if status:
        q = q.filter(PurchaseRequest.status == status)
    # إذا لم يتم تمرير department في الاستعلام و المستخدم ليس admin، استخدم إدارة المستخدم
    if dept:
        q = q.filter(PurchaseRequest.department == dept)
    elif user_role != "admin" and user_dept:
        q = q.filter(PurchaseRequest.department == user_dept)
    
    # تحديث الطلبات القديمة لتتوافق مع النظام الجديد
    try:
        # تحديث الطلبات التي لا تحتوي على status
        updated_status = db.query(PurchaseRequest).filter(PurchaseRequest.status.is_(None)).update(
            {"status": "pending_manager"}, synchronize_session=False
        )
        print(f"🔄 تم تحديث {updated_status} طلب بدون status")
        
        # تحديث الطلبات التي لا تحتوي على current_stage
        updated_stage = db.query(PurchaseRequest).filter(PurchaseRequest.current_stage.is_(None)).update(
            {"current_stage": "manager"}, synchronize_session=False
        )
        print(f"🔄 تم تحديث {updated_stage} طلب بدون current_stage")
        
        # تحديث الطلبات التي لا تحتوي على next_role
        updated_role = db.query(PurchaseRequest).filter(PurchaseRequest.next_role.is_(None)).update(
            {"next_role": "manager"}, synchronize_session=False
        )
        print(f"🔄 تم تحديث {updated_role} طلب بدون next_role")
        
        # تحديث الطلبات التي لا تحتوي على created_by
        updated_created = db.query(PurchaseRequest).filter(PurchaseRequest.created_by.is_(None)).update(
            {"created_by": "system"}, synchronize_session=False
        )
        print(f"🔄 تم تحديث {updated_created} طلب بدون created_by")
        
        db.commit()
        print("✅ تم تحديث الطلبات القديمة")
        
        # فحص الطلبات بعد التحديث
        all_requests = db.query(PurchaseRequest).all()
        print(f"🔍 فحص {len(all_requests)} طلب بعد التحديث:")
        for req in all_requests:
            print(f"   طلب {req.id}: status={req.status}, stage={req.current_stage}, role={req.next_role}")
            
    except Exception as e:
        print(f"خطأ في تحديث الطلبات: {e}")
        db.rollback()
    
    data = []
    for r in q.order_by(PurchaseRequest.id.desc()).all():
        request_data = {
            "id": r.id,
            "order_number": r.order_number,
            "requester": r.requester,
            "department": r.department,
            "date": str(r.created_at.date()) if r.created_at else "",
            "delivery_date": str(r.delivery_date) if getattr(r,'delivery_date',None) else "",
            "delivery_address": r.delivery_address,
            "project_code": r.project_code,
            "currency": r.currency,
            "status": r.status or "pending_manager",
            "current_stage": r.current_stage,
            "next_role": r.next_role,
            "created_by": r.created_by,
            "total_amount": float(r.total_amount or 0.0)
        }
        data.append(request_data)
        print(f"📄 طلب {r.id}: الحالة={r.status}, المرحلة={r.current_stage}, الدور التالي={r.next_role}")
        
        # تفصيل أكثر للطلبات المعتمدة
        if r.status == "approved":
            print(f"✅ طلب {r.id} معتمد - يجب أن يظهر في لوحة الإدارة")
        elif r.status == "rejected":
            print(f"❌ طلب {r.id} مرفوض - يجب أن يظهر في لوحة الإدارة")
    db.close()
    print(f"📊 إجمالي الطلبات المرسلة: {len(data)}")
    
    # تفصيل الحالات
    approved_count = len([d for d in data if d['status'] == 'approved'])
    rejected_count = len([d for d in data if d['status'] == 'rejected'])
    pending_count = len([d for d in data if d['status'] in ['pending_manager', 'pending_finance', 'pending_disbursement', 'pending_procurement']])
    
    print(f"📈 تفصيل الحالات:")
    print(f"   - معتمد: {approved_count}")
    print(f"   - مرفوض: {rejected_count}")
    print(f"   - في الانتظار: {pending_count}")
    
    # تفصيل الطلبات المعتمدة والمرفوضة
    for d in data:
        if d['status'] == 'approved':
            print(f"   ✅ طلب {d['id']} ({d['order_number']}) معتمد")
        elif d['status'] == 'rejected':
            print(f"   ❌ طلب {d['id']} ({d['order_number']}) مرفوض")
        else:
            print(f"   🔄 طلب {d['id']} ({d['order_number']}) - الحالة: {d['status']}")
    
    return jsonify(data)

@bp.patch("/requests/<int:req_id>/status")
@require_auth_and_roles("admin","manager","finance","disbursement")
def update_status(req_id):
    """
    body: { "action": "approve" | "reject", "note": "اختياري" }
    """
    data = request.get_json(force=True, silent=True) or {}
    action = (data.get("action") or "").lower()
    note = data.get("note")
    if action not in ("approve","reject"):
        return jsonify({"error":"إجراء غير صحيح"}), 400

    if action == "reject" and not (note and note.strip()):
        return jsonify({"error": "يجب إضافة ملاحظة توضح سبب الرفض"}), 400

    user = getattr(request, "user", {}) or {}
    role = user.get("role")
    actor_user = user.get("username") or user.get("name") or user.get("email")

    db = SessionLocal()

    try:
        pr = db.query(PurchaseRequest).get(req_id)
        if not pr:
            return jsonify({"error":"الطلب غير موجود"}), 404

        # تعريف المتغيرات المطلوبة
        current = pr.status or "pending_manager"
        next_role = pr.next_role or "manager"

        if role == "manager":
            user_dept = user.get("department")
            # استثناء خاص للمدير المالي - يمكنه التصرف في جميع الطلبات
            if actor_user == "manager_finance":
                print(f"✅ استثناء: المدير المالي يمكنه التصرف في جميع الطلبات")
            else:
                # فلترة عادية للمديرين الآخرين
                if pr.department != user_dept:
                    print(f"❌ رفض: المدير {actor_user} ({user_dept}) حاول التصرف في طلب لإدارة أخرى: {pr.department}")
                    return jsonify({"error": "لا يمكنك التصرف إلا في طلبات إدارتك فقط"}), 403
        
        # استثناء خاص للمدير المالي - يمكنه التصرف في طلبات مرحلة المالية
        if actor_user == "manager_finance" and current == "pending_finance":
            print(f"✅ استثناء: المدير المالي يمكنه التصرف في طلبات مرحلة المالية")
        
        # استثناء خاص لمدير تطوير الأعمال - لا يمكنه الموافقة على طلباته الخاصة
        if actor_user == "manager_bizdev" and pr.requester == "مدير تطوير الأعمال" and current == "pending_manager":
            print(f"❌ رفض: مدير تطوير الأعمال لا يمكنه الموافقة على طلباته الخاصة")
            return jsonify({"error": "لا يمكنك الموافقة على طلبك الخاص"}), 403

        print(f"🔍 تحديث الطلب {pr.id}:")
        print(f"   المستخدم: {role}")
        print(f"   الحالة الحالية: {current}")
        print(f"   المرحلة الحالية: {pr.current_stage}")
        print(f"   الدور المطلوب: {next_role}")
        print(f"   الإجراء: {action}")

        # منع القرارات المتكررة والطلبات المنتهية
        if current in ("approved", "rejected"):
            print(f"❌ رفض: الطلب منتهي بالفعل بحالة {current}")
            return jsonify({"error": f"الطلب منتهي بالفعل. الحالة: {current}"}), 400

        # حماية: لا أحد يتصرف في طلب لا يطابق دوره الحالي
        # استثناء خاص للمدير المالي - يمكنه التصرف في طلبات مرحلة المالية
        if actor_user == "manager_finance" and current == "pending_finance":
            print(f"✅ استثناء: المدير المالي يمكنه التصرف في طلبات مرحلة المالية")
        elif role not in ("admin", next_role):
            print(f"❌ رفض: المستخدم {role} لا يطابق الدور المطلوب {next_role}")
            return jsonify({"error": f"ليس لديك صلاحية في هذه المرحلة. المرحلة الحالية تتطلب دور: {next_role}"}), 403
        
        # منع القرار إذا لم تكن في المرحلة الصحيحة
        # استثناء خاص للمدير المالي - يمكنه التصرف في طلبات مرحلة المالية
        if actor_user == "manager_finance" and current == "pending_finance":
            print(f"✅ استثناء: المدير المالي يمكنه التصرف في طلبات مرحلة المالية")
        elif role == "manager" and current != "pending_manager":
            print(f"❌ رفض: الطلب ليس في مرحلة المدير المباشر")
            return jsonify({"error": "الطلب ليس في مرحلة المدير المباشر"}), 400
        
        if role == "finance" and current != "pending_finance":
            print(f"❌ رفض: الطلب ليس في مرحلة المالية")
            return jsonify({"error": "الطلب ليس في مرحلة المالية"}), 400
        
        if role == "disbursement" and current != "pending_disbursement":
            print(f"❌ رفض: الطلب ليس في مرحلة أمر الصرف")
            return jsonify({"error": "الطلب ليس في مرحلة أمر الصرف"}), 400

        # سجّل الحدث أولًا
        db.add(ApprovalHistory(
            request_id=pr.id,
            actor_role=role,
            actor_user=actor_user,
            action=action,
            note=note
        ))

        # منطق التقدم/الإنهاء مع تخطي الموافقة المكررة لنفس المستخدم
        def get_next_role_and_user(pr, current):
            """
            يعيد (next_status, next_stage, next_role, next_user)
            """
            department = pr.department
            requester = pr.requester
            finance_user = "manager_finance"
            disb_user = "disbursement_exec"
            procurement_username = None
            procurement_user = db.query(User).filter(User.role == "procurement").first()
            if procurement_user:
                procurement_username = procurement_user.username

            if current == "pending_manager":
                return ("pending_finance", "finance", "finance", finance_user)
            elif current == "pending_finance":
                return ("pending_disbursement", "disbursement", "disbursement", disb_user)
            elif current == "pending_disbursement":
                return ("pending_procurement", "procurement", "procurement", procurement_username)
            else:
                return (pr.status, pr.current_stage, pr.next_role, None)

        def skip_duplicate_approvals(pr, current, actor_user):
            status, stage, role, user_target = get_next_role_and_user(pr, current)
            if status in ("approved", "rejected", "completed") or not role or not user_target:
                pr.status = status
                pr.current_stage = stage
                pr.next_role = role
                if status == "pending_procurement":
                    pr.procurement_status = pr.procurement_status or "pending"
                return
            if actor_user == user_target:
                db.add(ApprovalHistory(
                    request_id=pr.id,
                    actor_role=role,
                    actor_user=actor_user,
                    action="auto-approve",
                    note="تخطي الموافقة المكررة لنفس المستخدم"
                ))
                return skip_duplicate_approvals(pr, status, actor_user)
            else:
                pr.status = status
                pr.current_stage = stage
                pr.next_role = role
                if status == "pending_procurement":
                    pr.procurement_status = pr.procurement_status or "pending"
                return
        
        # موافقة تلقائية خاصة لطلبات الإدارة التنفيذية
        if pr.department == "تنفيذية" and actor_user == "disbursement_exec" and current == "pending_disbursement":
            db.add(ApprovalHistory(
                request_id=pr.id,
                actor_role="disbursement",
                actor_user=actor_user,
                action="auto-approve",
                note="موافقة تلقائية من أمر الصرف التنفيذي على طلبات إدارته"
            ))
            pr.status = "pending_procurement"
            pr.current_stage = "procurement"
            pr.next_role = "procurement"
            pr.procurement_status = pr.procurement_status or "pending"
            db.add(pr)
            db.commit()
            db.refresh(pr)
            recipients = get_request_watchers(db, pr)
            create_notification(
                db,
                request_id=pr.id,
                recipients=recipients,
                title="تحويل الطلب إلى قسم المشتريات",
                message=f"تم تحويل طلب الشراء #{pr.order_number} إلى قسم المشتريات",
                action_type="procurement",
                actor_username=actor_user,
                actor_role="disbursement",
                note="موافقة تلقائية",
            )
            db.commit()
            return jsonify({
                "id": pr.id,
                "status": pr.status,
                "current_stage": pr.current_stage,
                "next_role": pr.next_role,
                "message": "تم تحويل الطلب إلى قسم المشتريات",
                "auto_approved": True
            })

        if action == "reject":
            pr.status = "rejected"
            pr.current_stage = "done"
            pr.next_role = None
            pr.rejection_note = note
        else:  # approve
            skip_duplicate_approvals(pr, current, actor_user)
            if pr.status == "pending_procurement":
                pr.procurement_status = pr.procurement_status or "pending"

        db.add(pr)
        db.commit()
        db.refresh(pr)  # تحديث الكائن من قاعدة البيانات
        
        print(f"✅ تم تحديث الطلب {pr.id}:")
        print(f"   الحالة القديمة: {current} → الحالة الجديدة: {pr.status}")
        print(f"   المرحلة الجديدة: {pr.current_stage}")
        print(f"   الدور التالي: {pr.next_role}")
        print(f"   تم الحفظ في قاعدة البيانات بنجاح!")
        print(f"   الطلب الآن يجب أن يظهر في طابور: {pr.next_role or 'منتهي'}")
        
        # فحص الطلب بعد التحديث
        db.refresh(pr)
        print(f"🔍 فحص الطلب بعد التحديث:")
        print(f"   ID: {pr.id}")
        print(f"   Status: {pr.status}")
        print(f"   Current Stage: {pr.current_stage}")
        print(f"   Next Role: {pr.next_role}")
        
        # أعد أيضًا إحصائيات سريعة لواجهة المستخدم حتى يمكن تحديث الكاردات فورًا
        try:
            total_count = db.query(PurchaseRequest).count()
            approved_count = db.query(PurchaseRequest).filter(PurchaseRequest.status == 'approved').count()
            rejected_count = db.query(PurchaseRequest).filter(PurchaseRequest.status == 'rejected').count()
        except Exception:
            # إذا فشل الحساب، عد القيم الافتراضية
            total_count = None
            approved_count = None
            rejected_count = None

        recipients = get_request_watchers(db, pr)
        if role == "requester":
            recipients = [pr.created_by] if pr.created_by else []
        action_type = "reject" if pr.status == "rejected" else "approve"
        title = "تحديث حالة طلب الشراء"
        if pr.status == "rejected":
            message = f"تم رفض طلب الشراء #{pr.order_number} بواسطه {actor_user}. السبب: {note}" if note else f"تم رفض طلب الشراء #{pr.order_number}."
        elif pr.status == "pending_procurement":
            message = f"تم تحويل طلب الشراء #{pr.order_number} إلى قسم المشتريات." 
            action_type = "procurement"
        elif pr.status == "completed":
            message = f"تم إكمال طلب الشراء #{pr.order_number}."
        else:
            message = f"تمت الموافقة على طلب الشراء #{pr.order_number} من قبل {actor_user}."

        create_notification(
            db,
            request_id=pr.id,
            recipients=recipients,
            title=title,
            message=message,
            action_type=action_type,
            actor_username=actor_user,
            actor_role=role,
            note=note,
        )
        db.commit()

        return jsonify({
            "id": pr.id,
            "status": pr.status,
            "current_stage": pr.current_stage,
            "next_role": pr.next_role,
            "message": "تم تحديث الطلب بنجاح",
            "total": total_count,
            "approved": approved_count,
            "rejected": rejected_count
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"خطأ في تحديث الحالة: {str(e)}"}), 500
    finally:
        db.close()

@bp.get("/requests/<int:req_id>")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement")
def get_request_details(req_id):
    """الحصول على تفاصيل طلب معين"""
    db = SessionLocal()
    try:
        request = db.query(PurchaseRequest).get(req_id)
        if not request:
            return jsonify({"error": "الطلب غير موجود"}), 404
        
        # الحصول على العناصر
        items = []
        for item in request.items:
            items.append({
                "id": item.id,
                "item_name": item.item_name,
                "specification": item.specification,
                "unit": item.unit,
                "quantity": item.quantity,
                "price": item.price,
                "total": item.total
            })
        
        return jsonify({
            "id": request.id,
            "order_number": request.order_number,
            "requester": request.requester,
            "department": request.department,
            "delivery_address": request.delivery_address,
            "delivery_date": request.delivery_date,
            "project_code": request.project_code,
            "currency": request.currency,
            "total_amount": float(request.total_amount or 0.0),
            "status": request.status,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "updated_at": request.updated_at.isoformat() if request.updated_at else None,
            "items": items
        })
    finally:
        db.close()

# طلبات بانتظار دوري الحالي (قائمة العمل)
@bp.get("/my/approved")
@require_auth_and_roles("admin","manager","finance","disbursement")
def my_approved():
    """عرض الطلبات التي وافق عليها المستخدم الحالي"""
    user = getattr(request, "user", {}) or {}
    actor_user = user.get("username") or user.get("name") or user.get("email")
    
    db = SessionLocal()
    try:
        # البحث عن الطلبات التي وافق عليها المستخدم
        approved_requests = db.query(PurchaseRequest).join(ApprovalHistory).filter(
            ApprovalHistory.actor_user == actor_user,
            ApprovalHistory.action.in_(["approve", "auto-approve"])
        ).distinct().all()
        
        result = []
        for pr in approved_requests:
            # جلب تاريخ الموافقة
            approval_history = db.query(ApprovalHistory).filter(
                ApprovalHistory.request_id == pr.id,
                ApprovalHistory.actor_user == actor_user,
                ApprovalHistory.action.in_(["approve", "auto-approve"])
            ).order_by(ApprovalHistory.created_at.desc()).first()
            
            result.append({
                "id": pr.id,
                "requester": pr.requester,
                "department": pr.department,
                "order_number": pr.order_number,
                "total_amount": pr.total_amount,
                "currency": pr.currency,
                "status": pr.status,
                "current_stage": pr.current_stage,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "approved_at": approval_history.created_at.isoformat() if approval_history else None,
                "approval_note": approval_history.note if approval_history else None
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"خطأ في جلب الطلبات المعتمدة: {e}")
        return jsonify({"error": "خطأ في جلب الطلبات المعتمدة"}), 500
    finally:
        db.close()

@bp.get("/my/rejected")
@require_auth_and_roles("admin","manager","finance","disbursement")
def my_rejected():
    """عرض الطلبات التي رفضها المستخدم الحالي"""
    user = getattr(request, "user", {}) or {}
    actor_user = user.get("username") or user.get("name") or user.get("email")
    
    db = SessionLocal()
    try:
        # البحث عن الطلبات التي رفضها المستخدم
        rejected_requests = db.query(PurchaseRequest).join(ApprovalHistory).filter(
            ApprovalHistory.actor_user == actor_user,
            ApprovalHistory.action == "reject"
        ).distinct().all()
        
        result = []
        for pr in rejected_requests:
            # جلب تاريخ الرفض
            rejection_history = db.query(ApprovalHistory).filter(
                ApprovalHistory.request_id == pr.id,
                ApprovalHistory.actor_user == actor_user,
                ApprovalHistory.action == "reject"
            ).order_by(ApprovalHistory.created_at.desc()).first()
            
            result.append({
                "id": pr.id,
                "requester": pr.requester,
                "department": pr.department,
                "order_number": pr.order_number,
                "total_amount": pr.total_amount,
                "currency": pr.currency or "SYP",
                "status": pr.status,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "rejected_at": rejection_history.created_at.isoformat() if rejection_history else None,
                "rejection_note": rejection_history.note if rejection_history else None
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"خطأ في جلب الطلبات المرفوضة: {e}")
        return jsonify({"error": "خطأ في جلب الطلبات المرفوضة"}), 500
    finally:
        db.close()

@bp.get("/my/queue")
@require_auth_and_roles("admin","manager","finance","disbursement","procurement")
def my_queue():
    user = getattr(request, "user", {}) or {}
    role = user.get("role")
    username = user.get("username")
    print(f"🔍 طلبات {role} ({username}):")
    db = SessionLocal()
    q = db.query(PurchaseRequest)
    
    # الأدمن يرى كل ما هو غير منتهٍ
    if role == "admin":
        q = q.filter(PurchaseRequest.current_stage.in_(["manager","finance","disbursement"]))
        print(f"   📊 الأدمن يرى الطلبات غير المنتهية")
    else:
        # تحديد الطلبات حسب الدور والاسم
        if role == "manager":
            # المدير يرى طلبات إدارته فقط
            user_dept = user.get("department")
            print(f"   📊 المدير {username} من إدارة: '{user_dept}'")
            print(f"   🔍 بيانات المستخدم كاملة: {user}")
            
            # التأكد من وجود الإدارة
            if not user_dept:
                print(f"   ❌ لم يتم العثور على إدارة للمستخدم {username}!")
                return jsonify({"requests": [], "total": 0, "approved": 0, "rejected": 0, "pending": 0})
            
            # فحص جميع الطلبات أولاً
            all_requests = db.query(PurchaseRequest).all()
            print(f"   🔍 جميع الطلبات في النظام ({len(all_requests)}):")
            for req in all_requests:
                dept_match = req.department == user_dept
                status_match = req.status == "pending_manager"
                print(f"      - طلب {req.id}: '{req.department}' == '{user_dept}' = {dept_match}, حالة: {req.status} = pending_manager = {status_match}")
            
            # استثناء خاص للمدير المالي - يرى طلبات مرحلة pending_manager (قسم المالية) و pending_finance (جميع الأقسام)
            if username == "manager_finance":
                print(f"   🔄 استثناء: المدير المالي يرى طلبات مرحلة pending_manager (قسم المالية) و pending_finance (جميع الأقسام)")
                # إعادة تعيين الاستعلام ليشمل طلبات pending_manager (قسم المالية) و pending_finance (جميع الأقسام)
                q = db.query(PurchaseRequest)
                q = q.filter(
                    (PurchaseRequest.status == "pending_manager") & (PurchaseRequest.department == "مالية") |
                    (PurchaseRequest.status == "pending_finance")
                )
                print(f"   🔍 البحث عن طلبات: (قسم المالية + pending_manager) أو (جميع الأقسام + pending_finance)")
                
                # طباعة جميع الطلبات المتاحة
                all_pending = q.all()
                print(f"   📋 الطلبات المتاحة للمدير المالي ({len(all_pending)}):")
                for req in all_pending:
                    print(f"      - طلب {req.id}: {req.requester} من {req.department} - الحالة: {req.status}")
            else:
                # فلترة الطلبات حسب الإدارة والحالة (للمديرين الآخرين)
                q = q.filter(PurchaseRequest.department == user_dept, PurchaseRequest.status == "pending_manager")
                print(f"   🔍 البحث عن طلبات: إدارة='{user_dept}', حالة='pending_manager'")
        elif role == "finance":
            # المالي يرى جميع الطلبات في مرحلة المالية (من جميع الأقسام)
            print(f"   📊 المالي {username} يرى جميع الطلبات في مرحلة المالية")
            
            # فحص جميع الطلبات أولاً
            all_requests = db.query(PurchaseRequest).all()
            print(f"   🔍 جميع الطلبات في النظام ({len(all_requests)}):")
            for req in all_requests:
                status_match = req.status == "pending_finance"
                print(f"      - طلب {req.id}: {req.requester} من {req.department} - الحالة: {req.status} = pending_finance = {status_match}")
                if req.status == "pending_manager":
                    print(f"         ⚠️ طلب {req.id} لا يزال في مرحلة المدير المباشر - يحتاج موافقة!")
            
            q = q.filter(PurchaseRequest.status == "pending_finance")
            print(f"   🔍 البحث عن طلبات: حالة='pending_finance' (من جميع الأقسام)")
        elif role == "disbursement":
            # أمر الصرف يرى الطلبات في مرحلة أمر الصرف
            print(f"   📊 أمر الصرف {username} يرى الطلبات في مرحلة أمر الصرف")
            
            # فحص جميع الطلبات أولاً
            all_requests = db.query(PurchaseRequest).all()
            print(f"   🔍 جميع الطلبات في النظام ({len(all_requests)}):")
            for req in all_requests:
                status_match = req.status == "pending_disbursement"
                print(f"      - طلب {req.id}: {req.requester} من {req.department} - الحالة: {req.status} = pending_disbursement = {status_match}")
                if req.status == "pending_finance":
                    print(f"         ⚠️ طلب {req.id} لا يزال في مرحلة المالية - يحتاج موافقة مالية!")
            
            q = q.filter(PurchaseRequest.status == "pending_disbursement")
            print(f"   🔍 البحث عن طلبات: حالة='pending_disbursement'")
        elif role == "procurement":
            print(f"   📊 المشتريات {username} يرى الطلبات في مرحلة المشتريات")
            all_requests = db.query(PurchaseRequest).all()
            print(f"   🔍 جميع الطلبات في النظام ({len(all_requests)}):")
            for req in all_requests:
                status_match = req.status == "pending_procurement"
                print(f"      - طلب {req.id}: {req.requester} من {req.department} - الحالة: {req.status} = pending_procurement = {status_match}")
            q = q.filter(PurchaseRequest.status == "pending_procurement")
            print(f"   🔍 البحث عن طلبات: حالة='pending_procurement'")
        else:
            # للدور العام، استخدم next_role
            q = q.filter(PurchaseRequest.next_role == role)
            print(f"   📊 {role} يرى الطلبات في طابوره")
    
    requests = q.order_by(PurchaseRequest.id.desc()).all()
    print(f"   📋 عدد الطلبات: {len(requests)}")
    
    # طباعة تفاصيل الطلبات المطلوبة فقط
    print(f"   🔍 الطلبات المطلوبة:")
    for req in requests:
        print(f"      - طلب {req.id}: {req.requester} من {req.department} - الحالة: {req.status}")
    
    out = []
    for r in requests:
        out.append({
            "id": r.id, 
            "order_number": r.order_number, 
            "requester": r.requester,
            "department": r.department, 
            "status": r.status, 
            "total_amount": float(r.total_amount or 0.0),
            "currency": r.currency or "SYP",
            "date": str(r.created_at.date()) if r.created_at else "",
            "delivery_date": r.delivery_date,
            "delivery_address": r.delivery_address,
            "project_code": r.project_code,
            "items": [{
                "id": it.id,
                "item_name": it.item_name,
                "specification": it.specification,
                "unit": it.unit,
                "quantity": it.quantity,
                "price": it.price,
                "total": it.total,
            } for it in r.items]
        })
        print(f"   📄 طلب {r.id} ({r.order_number}): {r.status}")
    
    db.close()
    # احسب الإحصائيات العامة بسرعة لواجهة المستخدم
    try:
        db2 = SessionLocal()
        all_reqs = db2.query(PurchaseRequest).all()
        total_count = len(all_reqs)
        approved_count = len([x for x in all_reqs if x.status == 'approved'])
        rejected_count = len([x for x in all_reqs if x.status == 'rejected'])
        db2.close()
    except Exception:
        total_count = None
        approved_count = None
        rejected_count = None

    return jsonify({
        "requests": out,
        "total": total_count,
        "approved": approved_count,
        "rejected": rejected_count,
        "pending": len(out)
    })

# طلبات أنشأتها أنا (لـ requester)
@bp.get("/my/requests")
@require_auth_and_roles("requester","admin")
def my_requests():
    user = getattr(request, "user", {}) or {}
    me = user.get("username") or user.get("name") or user.get("email")
    db = SessionLocal()
    q = db.query(PurchaseRequest)
    if user.get("role") != "admin":
        if hasattr(PurchaseRequest, "created_by"):
            q = q.filter(PurchaseRequest.created_by == me)
        else:
            q = q.filter(PurchaseRequest.requester == (user.get("name") or me))
    out = [{
        "id": r.id, "order_number": r.order_number, "status": r.status,
        "total_amount": float(r.total_amount or 0.0)
    } for r in q.order_by(PurchaseRequest.id.desc()).all()]
    db.close()
    return jsonify(out)

# طلبات المستخدم الحالي (لجميع الأدوار)
@bp.get("/user/requests")
@require_auth_and_roles("requester","admin","manager","finance","disbursement")
def user_requests():
    user = getattr(request, "user", {}) or {}
    me = user.get("username") or user.get("name") or user.get("email")
    db = SessionLocal()
    q = db.query(PurchaseRequest)
    
    # إذا كان admin، يعرض جميع الطلبات
    if user.get("role") == "admin":
        pass  # لا نضيف فلتر
    else:
        # للمستخدمين الآخرين، نعرض الطلبات التي أنشأوها
        if hasattr(PurchaseRequest, "created_by"):
            q = q.filter(PurchaseRequest.created_by == me)
        else:
            q = q.filter(PurchaseRequest.requester == (user.get("name") or me))
    
    out = [{
        "id": r.id, 
        "order_number": r.order_number, 
        "status": r.status,
        "requester": r.requester,
        "department": r.department,
        "total_amount": float(r.total_amount or 0.0),
        "currency": r.currency or "SYP",
        "created_at": r.created_at.isoformat() if r.created_at else None
    } for r in q.order_by(PurchaseRequest.id.desc()).all()]
    db.close()
    return jsonify(out)
