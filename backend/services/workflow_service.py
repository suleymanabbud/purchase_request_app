"""
خدمة سير العمل — منطق الأعمال للدورة المستندية
يحتوي: الخرائط، التحقق من الصلاحيات، التخطي التلقائي، مزامنة الحقول
"""

import logging
from ..models import PurchaseRequest, ApprovalHistory, User

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# خرائط سير العمل (Workflow Maps)
# ──────────────────────────────────────────────────────────

# التقدم الخطي: كل حالة → الحالة التالية
WORKFLOW_TRANSITIONS = {
    "pending_manager":      {"next_status": "pending_finance",       "next_stage": "finance",       "next_role": "finance"},
    "pending_finance":      {"next_status": "pending_disbursement",  "next_stage": "disbursement",  "next_role": "disbursement"},
    "pending_disbursement": {"next_status": "pending_procurement",   "next_stage": "procurement",   "next_role": "procurement"},
}

# الحالة → ما هو الدور المطلوب للتصرف
STATUS_TO_REQUIRED_ROLE = {
    "pending_manager": "manager",
    "pending_finance": "finance",
    "pending_disbursement": "disbursement",
}

# الحالة → أي حقل توقيع يُملأ
STATUS_TO_SIGNATURE_FIELDS = {
    "pending_manager":      {"name": "manager_name",       "date": "manager_date",       "sig": "manager_signature"},
    "pending_finance":      {"name": "finance_name",       "date": "finance_date",       "sig": "finance_signature"},
    "pending_disbursement": {"name": "disbursement_name",  "date": "disbursement_date",  "sig": "disbursement_signature"},
}

# الحالة → اسم الدور في سجل الموافقات
STATUS_TO_HISTORY_ROLE = {
    "pending_manager": "manager",
    "pending_finance": "finance",
    "pending_disbursement": "disbursement",
}

# الحالة → (current_stage, next_role) — لضمان التناسق
STATUS_TO_STAGE_ROLE = {
    "pending_manager":      ("manager",      "manager"),
    "pending_finance":      ("finance",      "finance"),
    "pending_disbursement": ("disbursement", "disbursement"),
    "pending_procurement":  ("procurement",  "procurement"),
    "approved":             ("done",         None),
    "rejected":             ("done",         None),
    "completed":            ("done",         None),
}


# ──────────────────────────────────────────────────────────
# دوال مساعدة
# ──────────────────────────────────────────────────────────

def sync_status_fields(pr):
    """
    يضمن تناسق الحقول الثلاثة: status, current_stage, next_role
    يجب استدعاؤها بعد أي تعديل على pr.status
    """
    mapping = STATUS_TO_STAGE_ROLE.get(pr.status)
    if mapping:
        pr.current_stage, pr.next_role = mapping
    return pr


def get_effective_role(actor_user, actor_role, current_status, db):
    """
    تحديد الدور الفعلي للمستخدم بناءً على المرحلة الحالية.
    مثال: manager_finance يعمل كـ 'finance' في مرحلة pending_finance
           manager_exec يعمل كـ 'disbursement' في مرحلة pending_disbursement
    """
    if actor_role == "admin":
        return STATUS_TO_REQUIRED_ROLE.get(current_status, actor_role)

    user = db.query(User).filter(User.username == actor_user).first()
    if not user:
        return actor_role

    if actor_user == "manager_finance" and current_status == "pending_finance":
        return "finance"

    if actor_user == "manager_exec" and current_status == "pending_disbursement":
        return "disbursement"

    return actor_role


def can_act_on_request(actor_user, actor_role, pr, db):
    """
    التحقق من صلاحية المستخدم للتصرف في الطلب.
    يُرجع (True, effective_role) أو (False, error_message)
    """
    current_status = pr.status or "pending_manager"

    # الطلبات المنتهية لا يمكن التصرف فيها
    if current_status in ("approved", "rejected", "completed"):
        return False, f"الطلب منتهي بالفعل. الحالة: {current_status}"

    required_role = STATUS_TO_REQUIRED_ROLE.get(current_status)
    if not required_role:
        return False, f"حالة غير معروفة: {current_status}"

    effective_role = get_effective_role(actor_user, actor_role, current_status, db)

    # التحقق من الدور
    if effective_role != required_role and actor_role != "admin":
        return False, f"ليس لديك صلاحية في هذه المرحلة. المرحلة تتطلب: {required_role}"

    # التحقق من القسم (للمديرين فقط في مرحلة pending_manager)
    if current_status == "pending_manager" and actor_role == "manager":
        user = db.query(User).filter(User.username == actor_user).first()
        user_dept = user.department if user else None

        if actor_user not in ("manager_finance", "manager_exec"):
            if pr.department != user_dept:
                return False, "لا يمكنك التصرف إلا في طلبات إدارتك فقط"

        if actor_user == "manager_bizdev" and pr.created_by == actor_user:
            return False, "لا يمكنك الموافقة على طلبك الخاص"

    return True, effective_role


def auto_skip_if_same_approver(db, pr, actor_user, signature, today_str):
    """
    تخطي المرحلة التالية تلقائياً إذا كان المعتمد التالي هو نفسه.
    مثال: manager_finance يوافق كمدير مباشر → يتخطى مرحلة المالية تلقائياً.
    """
    current = pr.status

    # مدير المالية وافق كمدير مباشر → تخطي المالية
    if current == "pending_finance" and actor_user == "manager_finance":
        user = db.query(User).filter(User.username == actor_user).first()
        user_full_name = user.full_name if user else actor_user

        pr.finance_name = user_full_name
        pr.finance_date = today_str
        pr.finance_signature = signature

        db.add(ApprovalHistory(
            request_id=pr.id, actor_role="finance",
            actor_user=actor_user, action="auto-approve",
            note="موافقة تلقائية - نفس المعتمد", signature=signature
        ))

        transition = WORKFLOW_TRANSITIONS["pending_finance"]
        pr.status = transition["next_status"]
        sync_status_fields(pr)
        logger.info(f"  ⏩ Auto-skip finance for {pr.id}")

    # آمر الصرف وافق كمدير مباشر/مالي → تخطي أمر الصرف
    if pr.status == "pending_disbursement" and actor_user == "manager_exec":
        user = db.query(User).filter(User.username == actor_user).first()
        user_full_name = user.full_name if user else actor_user

        pr.disbursement_name = user_full_name
        pr.disbursement_date = today_str
        pr.disbursement_signature = signature

        db.add(ApprovalHistory(
            request_id=pr.id, actor_role="disbursement",
            actor_user=actor_user, action="auto-approve",
            note="موافقة تلقائية - نفس المعتمد", signature=signature
        ))

        transition = WORKFLOW_TRANSITIONS["pending_disbursement"]
        pr.status = transition["next_status"]
        sync_status_fields(pr)
        pr.procurement_status = pr.procurement_status or "pending"
        logger.info(f"  ⏩ Auto-skip disbursement for {pr.id}")

    return pr
