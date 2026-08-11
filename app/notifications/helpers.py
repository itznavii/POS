from datetime import datetime, timedelta

from app import db
from app.models import Notification


def notify(ntype, message, related_id=None, dedupe=False):
    """Create a notification. If dedupe=True, skip if an identical unread
    notification already exists within the last hour (avoids alert spam,
    e.g. repeated low-stock pings)."""
    if dedupe:
        cutoff = datetime.utcnow() - timedelta(hours=1)
        existing = Notification.query.filter_by(
            type=ntype, message=message, is_read=False
        ).filter(Notification.created_at >= cutoff).first()
        if existing:
            return existing
    n = Notification(type=ntype, message=message, related_id=related_id)
    db.session.add(n)
    db.session.commit()
    return n


def unread_notification_count():
    return Notification.query.filter_by(is_read=False).count()
