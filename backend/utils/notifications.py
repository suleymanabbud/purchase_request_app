from typing import Iterable, Optional
from datetime import datetime, timezone
from ..models import Notification


def create_notification(
    db,
    *,
    request_id: Optional[int],
    recipients: Iterable[str],
    title: str,
    message: str,
    action_type: str,
    actor_username: Optional[str] = None,
    actor_role: Optional[str] = None,
    note: Optional[str] = None,
):
    """إنشاء إشعارات متعددة وتخزينها في قاعدة البيانات."""
    created = []
    now = datetime.now(timezone.utc)
    for recipient in recipients:
        if not recipient:
            continue
        notif = Notification(
            request_id=request_id,
            recipient_username=recipient,
            title=title,
            message=message,
            action_type=action_type,
            actor_username=actor_username,
            actor_role=actor_role,
            note=note,
            created_at=now,
        )
        db.add(notif)
        created.append(notif)
    return created



