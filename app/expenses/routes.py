from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.decorators import admin_required
from app.models import Expense
from app.utils import log_activity

expenses = Blueprint("expenses", __name__)

CATEGORIES = ["Utilities", "Salary", "Rent", "Marketing", "Supplies", "Others"]


@expenses.route("/")
@login_required
@admin_required
def list_expenses():
    items = Expense.query.order_by(Expense.date.desc()).all()
    total = sum(e.amount or 0 for e in items)
    return render_template("expenses/list.html", items=items, total=total, categories=CATEGORIES)


@expenses.route("/add", methods=["POST"])
@login_required
@admin_required
def add_expense():
    e = Expense(
        category=request.form.get("category"),
        description=request.form.get("description"),
        amount=float(request.form.get("amount", 0) or 0),
        date=datetime.strptime(request.form.get("date"), "%Y-%m-%d").date(),
        recorded_by=current_user.id,
    )
    db.session.add(e)
    db.session.commit()
    log_activity(f"Added expense: {e.category} PHP {e.amount:.2f}")
    flash("Expense recorded.", "success")
    return redirect(url_for("expenses.list_expenses"))


@expenses.route("/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_expense(id):
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    log_activity(f"Deleted expense #{id}")
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses"))
