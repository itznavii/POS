from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user

from app import db
from app.decorators import admin_required
from app.models import (
    Reservation,
    ReservationAttachment,
    ReservationPayment,
    Customer,
    Sale,
    SaleItem,
    SalePayment,
)
from app.utils import (
    new_reservation_number,
    new_sale_number,
    save_upload,
    log_activity,
    generate_receipt_pdf,
)
from app.notifications.helpers import notify

reservations = Blueprint("reservations", __name__)

VAT_RATE = 0.12


@reservations.route("/")
@login_required
def list_reservations():
    status = request.args.get("status")
    query = Reservation.query
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Reservation.date.desc(), Reservation.time.desc()).all()
    return render_template("reservations/list.html", items=items, status=status)


@reservations.route("/calendar")
@login_required
def calendar_view():
    return render_template("reservations/calendar.html")


@reservations.route("/api/calendar-events")
@login_required
def calendar_events():
    color_map = {
        "Reserved": "#f0ad4e",
        "Confirmed": "#2f7a4f",
        "Checked In": "#0d6efd",
        "Completed": "#198754",
        "Cancelled": "#6c757d",
        "No Show": "#dc3545",
    }
    items = Reservation.query.all()
    events = []
    for r in items:
        events.append(
            {
                "id": r.id,
                "title": f"{r.customer_name} ({r.pax}pax) - {r.event_type or ''}",
                "start": f"{r.date.isoformat()}T{r.time.strftime('%H:%M:%S')}",
                "color": color_map.get(r.status, "#999"),
                "url": url_for("reservations.detail", id=r.id),
            }
        )
    return jsonify(events)


@reservations.route("/new", methods=["GET", "POST"])
@login_required
def new_reservation():
    if request.method == "POST":
        customer_name = request.form.get("customer_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        date_str = request.form.get("date")
        time_str = request.form.get("time")
        pax = int(request.form.get("pax", 1) or 1)

        customer = Customer.query.filter_by(phone=phone).first() if phone else None
        if not customer and customer_name:
            customer = Customer(name=customer_name, phone=phone, email=email)
            db.session.add(customer)
            db.session.flush()

        r = Reservation(
            reservation_number=new_reservation_number(),
            inquiry_number=request.form.get("inquiry_number"),
            customer_id=customer.id if customer else None,
            date=datetime.strptime(date_str, "%Y-%m-%d").date(),
            time=datetime.strptime(time_str, "%H:%M").time(),
            customer_name=customer_name,
            phone=phone,
            email=email,
            pax=pax,
            event_type=request.form.get("event_type"),
            special_requests=request.form.get("special_requests"),
            assigned_staff=request.form.get("assigned_staff"),
            down_payment=float(request.form.get("down_payment", 0) or 0),
            status="Reserved",
        )
        db.session.add(r)
        db.session.flush()

        # Optional down payment record + proof upload
        dp_amount = float(request.form.get("down_payment", 0) or 0)
        if dp_amount > 0:
            db.session.add(
                ReservationPayment(
                    reservation_id=r.id,
                    payment_type="down_payment",
                    method=request.form.get("payment_method", "Cash"),
                    amount=dp_amount,
                    reference_number=request.form.get("reference_number"),
                    status="Pending",
                )
            )

        proof_file = request.files.get("proof_of_payment")
        if proof_file and proof_file.filename:
            try:
                filename = save_upload(proof_file, subfolder="reservations")
                if filename:
                    db.session.add(ReservationAttachment(reservation_id=r.id, filename=filename))
            except ValueError as e:
                flash(str(e), "danger")

        db.session.commit()
        notify("new_reservation", f"New reservation {r.reservation_number} by {r.customer_name}", related_id=r.id)
        log_activity(f"Created reservation {r.reservation_number}")
        flash(f"Reservation {r.reservation_number} created.", "success")
        return redirect(url_for("reservations.detail", id=r.id))

    return render_template("reservations/new.html")


@reservations.route("/<int:id>")
@login_required
def detail(id):
    r = Reservation.query.get_or_404(id)
    return render_template("reservations/detail.html", r=r)


@reservations.route("/<int:id>/confirm", methods=["POST"])
@login_required
def confirm(id):
    r = Reservation.query.get_or_404(id)
    r.status = "Confirmed"
    r.confirmed_by = current_user.name or current_user.username
    r.date_confirmed = datetime.utcnow()
    db.session.commit()
    log_activity(f"Confirmed reservation {r.reservation_number}")
    flash("Reservation confirmed.", "success")
    return redirect(url_for("reservations.detail", id=id))


@reservations.route("/<int:id>/cancel", methods=["POST"])
@login_required
def cancel(id):
    r = Reservation.query.get_or_404(id)
    r.status = "Cancelled"
    db.session.commit()
    notify("cancelled_reservation", f"Reservation {r.reservation_number} was cancelled", related_id=r.id)
    log_activity(f"Cancelled reservation {r.reservation_number}")
    flash("Reservation cancelled.", "warning")
    return redirect(url_for("reservations.detail", id=id))


@reservations.route("/<int:id>/no-show", methods=["POST"])
@login_required
def no_show(id):
    r = Reservation.query.get_or_404(id)
    r.status = "No Show"
    db.session.commit()
    log_activity(f"Marked reservation {r.reservation_number} as No Show")
    flash("Reservation marked as No Show.", "warning")
    return redirect(url_for("reservations.detail", id=id))


@reservations.route("/<int:id>/upload-proof", methods=["POST"])
@login_required
def upload_proof(id):
    r = Reservation.query.get_or_404(id)
    proof_file = request.files.get("proof_of_payment")
    if proof_file and proof_file.filename:
        try:
            filename = save_upload(proof_file, subfolder="reservations")
            if filename:
                db.session.add(ReservationAttachment(reservation_id=r.id, filename=filename))
                db.session.commit()
                flash("Proof of payment uploaded.", "success")
        except ValueError as e:
            flash(str(e), "danger")
    return redirect(url_for("reservations.detail", id=id))


@reservations.route("/payment/<int:payment_id>/verify", methods=["POST"])
@login_required
@admin_required
def verify_payment(payment_id):
    payment = ReservationPayment.query.get_or_404(payment_id)
    action = request.form.get("action", "Verified")
    payment.status = action
    payment.verified_by = current_user.name or current_user.username
    db.session.commit()
    log_activity(f"{action} payment #{payment.id} for reservation {payment.reservation.reservation_number}")
    flash(f"Payment {action.lower()}.", "success")
    return redirect(url_for("reservations.detail", id=payment.reservation_id))


# ---------------------------------------------------------------------------
# Check-in
# ---------------------------------------------------------------------------
@reservations.route("/<int:id>/checkin", methods=["POST"])
@login_required
def checkin(id):
    r = Reservation.query.get_or_404(id)
    r.status = "Checked In"
    r.arrival_time = datetime.utcnow()
    r.actual_pax = int(request.form.get("actual_pax", r.pax) or r.pax)
    db.session.commit()
    log_activity(f"Checked in reservation {r.reservation_number} ({r.actual_pax} guests)")
    flash("Guest checked in.", "success")
    return redirect(url_for("reservations.detail", id=id))


# ---------------------------------------------------------------------------
# Final billing: total bill entry -> auto-compute balance -> final payment ->
# generate official receipt -> mark Completed
# ---------------------------------------------------------------------------
@reservations.route("/<int:id>/final-billing", methods=["GET", "POST"])
@login_required
def final_billing(id):
    r = Reservation.query.get_or_404(id)

    if request.method == "POST":
        total_bill = float(request.form.get("total_bill", 0) or 0)
        verified_dp = r.total_verified_paid()
        remaining = max(0.0, total_bill - verified_dp)

        payment_method = request.form.get("payment_method", "Cash")
        amount_paid = float(request.form.get("amount_paid", 0) or 0)

        if amount_paid + 0.01 < remaining:
            flash(
                f"Amount paid (PHP {amount_paid:.2f}) is less than the remaining balance "
                f"(PHP {remaining:.2f}).",
                "danger",
            )
            return redirect(url_for("reservations.final_billing", id=id))

        r.total_bill = total_bill
        r.remaining_balance = max(0.0, remaining - amount_paid)

        db.session.add(
            ReservationPayment(
                reservation_id=r.id,
                payment_type="final_payment",
                method=payment_method,
                amount=amount_paid,
                reference_number=request.form.get("reference_number"),
                status="Verified",
                verified_by=current_user.name or current_user.username,
            )
        )

        # Build a Sale record so it flows into reports/receipt like any other transaction
        subtotal = round(total_bill / (1 + VAT_RATE), 2)
        vat = round(total_bill - subtotal, 2)
        sale = Sale(
            sale_number=new_sale_number(),
            customer_id=r.customer_id,
            customer_name=r.customer_name,
            is_walkin=False,
            reservation_id=r.id,
            subtotal=subtotal,
            discount=0,
            discount_type="none",
            vat=vat,
            total=total_bill,
            amount_tendered=verified_dp + amount_paid,
            change=max(0.0, (verified_dp + amount_paid) - total_bill),
            status="completed",
            cashier_id=current_user.id,
        )
        db.session.add(sale)
        db.session.flush()
        db.session.add(
            SaleItem(
                sale_id=sale.id,
                product_name=f"Reservation Buffet ({r.actual_pax or r.pax} guests)",
                quantity=r.actual_pax or r.pax,
                price=total_bill / max(1, (r.actual_pax or r.pax)),
                line_total=total_bill,
            )
        )
        db.session.add(
            SalePayment(sale_id=sale.id, method=payment_method, amount=amount_paid, reference_number=request.form.get("reference_number"))
        )
        if verified_dp:
            db.session.add(SalePayment(sale_id=sale.id, method="Down Payment", amount=verified_dp))

        r.status = "Completed"
        db.session.commit()
        log_activity(f"Final billing for reservation {r.reservation_number}: total PHP {total_bill:.2f}")
        flash("Final billing recorded. Reservation marked Completed.", "success")
        return redirect(url_for("pos.receipt", sale_id=sale.id))

    verified_dp = r.total_verified_paid()
    return render_template("reservations/final_billing.html", r=r, verified_dp=verified_dp)
