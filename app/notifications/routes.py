from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

from app import db
from app.models import Notification

notifications = Blueprint("notifications", __name__)


@notifications.route("/")
@login_required
def list_notifications():
    items = Notification.query.order_by(Notification.created_at.desc()).limit(100).all()
    return render_template("notifications/list.html", items=items)


@notifications.route("/<int:id>/read")
@login_required
def mark_read(id):
    n = Notification.query.get_or_404(id)
    n.is_read = True
    db.session.commit()
    return redirect(url_for("notifications.list_notifications"))


@notifications.route("/read-all")
@login_required
def mark_all_read():
    Notification.query.update({Notification.is_read: True})
    db.session.commit()
    return redirect(url_for("notifications.list_notifications"))
