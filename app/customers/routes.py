from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Customer, Sale, Reservation
from app.utils import log_activity

customers = Blueprint("customers", __name__)


@customers.route("/")
@login_required
def list_customers():
    items = Customer.query.order_by(Customer.name).all()
    return render_template("customers/list.html", items=items)


@customers.route("/add", methods=["POST"])
@login_required
def add_customer():
    name = request.form.get("name")
    if name:
        c = Customer(
            name=name,
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            preferred_events=request.form.get("preferred_events"),
            notes=request.form.get("notes"),
        )
        db.session.add(c)
        db.session.commit()
        log_activity(f"Added customer {name}")
        flash("Customer added.", "success")
    return redirect(url_for("customers.list_customers"))


@customers.route("/<int:id>")
@login_required
def detail(id):
    c = Customer.query.get_or_404(id)
    sales = Sale.query.filter_by(customer_id=id).order_by(Sale.created_at.desc()).all()
    reservation_history = Reservation.query.filter_by(customer_id=id).order_by(Reservation.date.desc()).all()
    return render_template("customers/detail.html", c=c, sales=sales, reservation_history=reservation_history)
