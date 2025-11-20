from ..models import PurchaseRequest, User


def get_request_watchers(db, pr: PurchaseRequest):
    """إرجاع قائمة المستخدمين الذين يجب إعلامهم بالتغييرات على الطلب."""
    recipients = set()
    if pr.created_by:
        recipients.add(pr.created_by)

    # المدير المباشر لنفس الإدارة
    manager = (
        db.query(User)
        .filter(User.role == "manager", User.department == pr.department)
        .first()
    )
    if manager:
        recipients.add(manager.username)

    # جميع مستخدمي المالية
    for finance_user in db.query(User).filter(User.role == "finance"):
        recipients.add(finance_user.username)

    # أمر الصرف
    for disbursement_user in db.query(User).filter(User.role == "disbursement"):
        recipients.add(disbursement_user.username)

    return list(recipients)



