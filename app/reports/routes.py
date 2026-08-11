import csv
import io
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.decorators import admin_required
from app.models import Sale, SaleItem, SalePayment, Reservation, Expense

reports = Blueprint("reports", __name__)


def _parse_range():
    period = request.args.get("period", "daily")
    today = date.today()
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == "monthly":
        start = today.replace(day=1)
        end = today
    elif period == "yearly":
        start = today.replace(month=1, day=1)
        end = today
    elif period == "custom":
        start = datetime.strptime(request.args.get("start", str(today)), "%Y-%m-%d").date()
        end = datetime.strptime(request.args.get("end", str(today)), "%Y-%m-%d").date()
    else:
        start = end = today
    return period, start, end


@reports.route("/")
@login_required
@admin_required
def index():
    period, start, end = _parse_range()

    sales = Sale.query.filter(
        func.date(Sale.created_at) >= start,
        func.date(Sale.created_at) <= end,
        Sale.status == "completed",
    ).all()

    total_sales = sum(s.total for s in sales)
    total_discount = sum(s.discount for s in sales)
    total_vat = sum(s.vat for s in sales)
    transaction_count = len(sales)

    top_products = (
        db.session.query(SaleItem.product_name, func.sum(SaleItem.quantity).label("qty"), func.sum(SaleItem.line_total).label("revenue"))
        .join(Sale)
        .filter(func.date(Sale.created_at) >= start, func.date(Sale.created_at) <= end, Sale.status == "completed")
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(10)
        .all()
    )

    payments_breakdown = (
        db.session.query(SalePayment.method, func.sum(SalePayment.amount))
        .join(Sale)
        .filter(func.date(Sale.created_at) >= start, func.date(Sale.created_at) <= end, Sale.status == "completed")
        .group_by(SalePayment.method)
        .all()
    )

    reservations_in_range = Reservation.query.filter(Reservation.date >= start, Reservation.date <= end).all()

    expenses_in_range = Expense.query.filter(Expense.date >= start, Expense.date <= end).all()
    total_expenses = sum(e.amount or 0 for e in expenses_in_range)

    return render_template(
        "reports/index.html",
        period=period,
        start=start,
        end=end,
        sales=sales,
        total_sales=total_sales,
        total_discount=total_discount,
        total_vat=total_vat,
        transaction_count=transaction_count,
        top_products=top_products,
        payments_breakdown=payments_breakdown,
        reservations_in_range=reservations_in_range,
        expenses_in_range=expenses_in_range,
        total_expenses=total_expenses,
        net=total_sales - total_expenses,
    )


@reports.route("/export/<fmt>")
@login_required
@admin_required
def export(fmt):
    period, start, end = _parse_range()
    sales = Sale.query.filter(
        func.date(Sale.created_at) >= start,
        func.date(Sale.created_at) <= end,
        Sale.status == "completed",
    ).all()

    rows = [
        ["Sale Number", "Date", "Customer", "Subtotal", "Discount", "VAT", "Total", "Cashier"]
    ]
    for s in sales:
        rows.append(
            [
                s.sale_number,
                s.created_at.strftime("%Y-%m-%d %H:%M"),
                s.customer_name,
                f"{s.subtotal:.2f}",
                f"{s.discount:.2f}",
                f"{s.vat:.2f}",
                f"{s.total:.2f}",
                s.cashier.username if s.cashier else "",
            ]
        )

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)
        mem = io.BytesIO(buf.getvalue().encode("utf-8"))
        return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=f"sales_report_{period}.csv")

    if fmt == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Sales Report"
        for row in rows:
            ws.append(row)
        mem = io.BytesIO()
        wb.save(mem)
        mem.seek(0)
        return send_file(
            mem,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"sales_report_{period}.xlsx",
        )

    if fmt == "pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        mem = io.BytesIO()
        doc = SimpleDocTemplate(mem, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph(f"Sitio Verde Buffet Restaurant - Sales Report ({period})", styles["Title"]),
            Paragraph(f"{start} to {end}", styles["Normal"]),
            Spacer(1, 12),
        ]
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e5631")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
        mem.seek(0)
        return send_file(mem, mimetype="application/pdf", as_attachment=True, download_name=f"sales_report_{period}.pdf")

    return "Unsupported format", 400
