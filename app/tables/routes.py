from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db, csrf
from app.models import RestaurantTable
from app.utils import log_activity
from app.decorators import admin_required

tables_bp = Blueprint("tables_bp", __name__)


@tables_bp.route("/")
@login_required
def layout():
    tables = RestaurantTable.query.order_by(RestaurantTable.name).all()
    return render_template("tables/layout.html", tables=tables)


@tables_bp.route("/add", methods=["POST"])
@login_required
@admin_required
def add_table():
    name = request.form.get("name")
    capacity = request.form.get("capacity", 4)
    if name:
        db.session.add(RestaurantTable(name=name, capacity=capacity))
        db.session.commit()
        log_activity(f"Added table {name}")
        flash("Table added.", "success")
    return redirect(url_for("tables_bp.layout"))


@tables_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@csrf.exempt
def update_status(id):
    table = RestaurantTable.query.get_or_404(id)
    new_status = request.form.get("status") or (request.get_json(silent=True) or {}).get("status")
    if new_status in ("available", "occupied", "reserved", "cleaning"):
        table.status = new_status
        db.session.commit()
        log_activity(f"Table {table.name} set to {new_status}")
    if request.is_json:
        return jsonify({"ok": True, "status": table.status})
    return redirect(url_for("tables_bp.layout"))


@tables_bp.route("/<int:id>/transfer", methods=["POST"])
@login_required
def transfer(id):
    """Move an occupied table's open sale/status to another table."""
    source = RestaurantTable.query.get_or_404(id)
    dest_id = request.form.get("dest_table_id")
    dest = RestaurantTable.query.get_or_404(dest_id)
    if dest.status != "available":
        flash("Destination table is not available.", "danger")
        return redirect(url_for("tables_bp.layout"))

    from app.models import Sale

    open_sales = Sale.query.filter_by(table_id=source.id, status="completed").all()
    for s in open_sales:
        s.table_id = dest.id
    dest.status = "occupied"
    source.status = "cleaning"
    db.session.commit()
    log_activity(f"Transferred table {source.name} -> {dest.name}")
    flash(f"Transferred {source.name} to {dest.name}.", "success")
    return redirect(url_for("tables_bp.layout"))


@tables_bp.route("/merge", methods=["POST"])
@login_required
def merge():
    ids = request.form.getlist("table_ids")
    if len(ids) < 2:
        flash("Select at least two tables to merge.", "warning")
        return redirect(url_for("tables_bp.layout"))
    primary = RestaurantTable.query.get(ids[0])
    for tid in ids[1:]:
        t = RestaurantTable.query.get(tid)
        if t:
            t.merged_into_id = primary.id
            t.status = "occupied"
    primary.status = "occupied"
    db.session.commit()
    log_activity(f"Merged tables {ids} into {primary.name}")
    flash("Tables merged.", "success")
    return redirect(url_for("tables_bp.layout"))
