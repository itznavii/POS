from datetime import date, timedelta

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import (
    Sale,
    SaleItem,
    Reservation,
    InventoryItem,
    RestaurantTable,
)

main = Blueprint("main", __name__)


@main.route("/")
@login_required
def dashboard():
    today = date.today()

    today_sales = (
        db.session.query(func.sum(Sale.total))
        .filter(func.date(Sale.created_at) == today, Sale.status == "completed")
        .scalar()
        or 0
    )
    today_reservations = Reservation.query.filter_by(date=today).count()
    walkin_now = RestaurantTable.query.filter_by(status="occupied").count()
    upcoming = Reservation.query.filter(
        Reservation.date > today, Reservation.status.in_(["Reserved", "Confirmed"])
    ).count()
    monthly = (
        db.session.query(func.sum(Sale.total))
        .filter(
            func.extract("month", Sale.created_at) == today.month,
            func.extract("year", Sale.created_at) == today.year,
            Sale.status == "completed",
        )
        .scalar()
        or 0
    )
    low_stock = InventoryItem.query.filter(
        InventoryItem.quantity <= InventoryItem.low_stock_threshold
    ).count()
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(8).all()

    best_seller_row = (
        db.session.query(SaleItem.product_name, func.sum(SaleItem.quantity).label("qty"))
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .first()
    )
    best_seller = best_seller_row[0] if best_seller_row else "N/A"

    upcoming_list = (
        Reservation.query.filter(
            Reservation.date >= today, Reservation.status.in_(["Reserved", "Confirmed"])
        )
        .order_by(Reservation.date, Reservation.time)
        .limit(6)
        .all()
    )

    return render_template(
        "dashboard.html",
        today_sales=today_sales,
        today_reservations=today_reservations,
        walkin_now=walkin_now,
        upcoming=upcoming,
        monthly=monthly,
        low_stock=low_stock,
        recent_sales=recent_sales,
        best_seller=best_seller,
        upcoming_list=upcoming_list,
    )


@main.route("/api/sales-chart")
@login_required
def sales_chart():
    days = []
    totals = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        total = (
            db.session.query(func.sum(Sale.total))
            .filter(func.date(Sale.created_at) == d, Sale.status == "completed")
            .scalar()
            or 0
        )
        days.append(d.strftime("%a"))
        totals.append(round(total, 2))
    return jsonify({"labels": days, "data": totals})


@main.route("/api/reservation-chart")
@login_required
def reservation_chart():
    statuses = ["Reserved", "Confirmed", "Checked In", "Completed", "Cancelled", "No Show"]
    counts = [Reservation.query.filter_by(status=s).count() for s in statuses]
    return jsonify({"labels": statuses, "data": counts})
