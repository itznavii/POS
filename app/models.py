from datetime import datetime

from flask_login import UserMixin

from app import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="staff", nullable=False)  # admin | staff
    name = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_admin(self):
        return self.role == "admin"


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    preferred_events = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship("Sale", backref="customer", lazy=True)
    reservations = db.relationship("Reservation", backref="customer", lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    selling_price = db.Column(db.Float, nullable=False, default=0)
    cost_price = db.Column(db.Float, default=0)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    barcode = db.Column(db.String(64), unique=True, nullable=True, index=True)
    available = db.Column(db.Boolean, default=True)
    is_buffet = db.Column(db.Boolean, default=False)

    # Simple per-product inventory tracking (deduct N units of an inventory
    # item every time 1 unit of this product is sold). Optional.
    inventory_item_id = db.Column(db.Integer, db.ForeignKey("inventory_item.id"))
    deduct_qty = db.Column(db.Float, default=1.0)

    buffet_tiers = db.relationship(
        "BuffetTier", backref="product", lazy=True, cascade="all, delete-orphan"
    )

    def tier_price(self, tier):
        for t in self.buffet_tiers:
            if t.tier == tier:
                return t.price
        return 0.0


class BuffetTier(db.Model):
    """Per-product buffet pricing tiers: adult / senior / pwd / kids / free."""

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    tier = db.Column(db.String(20), nullable=False)  # adult, senior, pwd, kids, free
    price = db.Column(db.Float, default=0)


class RestaurantTable(db.Model):
    __tablename__ = "restaurant_table"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False)  # e.g. "T1"
    capacity = db.Column(db.Integer, default=4)
    status = db.Column(db.String(20), default="available")
    # available | occupied | reserved | cleaning
    merged_into_id = db.Column(db.Integer, db.ForeignKey("restaurant_table.id"))

    sales = db.relationship("Sale", backref="table", lazy=True)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    customer_name = db.Column(db.String(120))
    is_walkin = db.Column(db.Boolean, default=False)
    queue_number = db.Column(db.String(10))
    table_id = db.Column(db.Integer, db.ForeignKey("restaurant_table.id"))
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"))

    subtotal = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    discount_type = db.Column(db.String(30), default="none")
    vat = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    amount_tendered = db.Column(db.Float, default=0)
    change = db.Column(db.Float, default=0)

    status = db.Column(db.String(20), default="completed")
    # open (kitchen in-progress) | completed | voided
    void_reason = db.Column(db.String(255))
    voided_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    requires_approval = db.Column(db.Boolean, default=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    cashier_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship(
        "SaleItem", backref="sale", lazy=True, cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "SalePayment", backref="sale", lazy=True, cascade="all, delete-orphan"
    )
    cashier = db.relationship("User", foreign_keys=[cashier_id])
    reservation = db.relationship("Reservation", foreign_keys=[reservation_id])

    def total_paid(self):
        return sum(p.amount for p in self.payments)


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_name = db.Column(db.String(120))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float)
    line_total = db.Column(db.Float, default=0)

    is_senior_pwd = db.Column(db.Boolean, default=False)  # per-line discount flag

    is_buffet = db.Column(db.Boolean, default=False)
    buffet_adult = db.Column(db.Integer, default=0)
    buffet_senior = db.Column(db.Integer, default=0)
    buffet_pwd = db.Column(db.Integer, default=0)
    buffet_kids = db.Column(db.Integer, default=0)
    buffet_free = db.Column(db.Integer, default=0)

    kitchen_status = db.Column(db.String(20), default="preparing")
    # preparing | ready | served | completed


class SalePayment(db.Model):
    """Supports split / mixed payments per sale."""

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"))
    method = db.Column(db.String(30))  # Cash, GCash, Bank Transfer, Credit Card
    amount = db.Column(db.Float, default=0)
    reference_number = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_number = db.Column(db.String(20), unique=True, nullable=False)
    inquiry_number = db.Column(db.String(20))
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default="Reserved")
    # Reserved, Confirmed, Checked In, Completed, Cancelled, No Show

    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    pax = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(50))
    special_requests = db.Column(db.Text)
    assigned_staff = db.Column(db.String(120))
    confirmed_by = db.Column(db.String(120))
    date_confirmed = db.Column(db.DateTime)

    down_payment = db.Column(db.Float, default=0)

    arrival_time = db.Column(db.DateTime)
    actual_pax = db.Column(db.Integer)
    total_bill = db.Column(db.Float, default=0)
    remaining_balance = db.Column(db.Float, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attachments = db.relationship(
        "ReservationAttachment",
        backref="reservation",
        lazy=True,
        cascade="all, delete-orphan",
    )
    res_payments = db.relationship(
        "ReservationPayment",
        backref="reservation",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def total_verified_paid(self):
        return sum(
            p.amount for p in self.res_payments if p.status == "Verified"
        )


class ReservationAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"))
    filename = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReservationPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"))
    payment_type = db.Column(db.String(20))  # down_payment | final_payment
    method = db.Column(db.String(30))
    amount = db.Column(db.Float, default=0)
    reference_number = db.Column(db.String(60))
    status = db.Column(db.String(20), default="Pending")  # Pending, Verified, Rejected
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_by = db.Column(db.String(120))


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(120))

    items = db.relationship("InventoryItem", backref="supplier", lazy=True)


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(20), default="pcs")
    low_stock_threshold = db.Column(db.Float, default=5)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))

    products = db.relationship("Product", backref="inventory_item", lazy=True)
    transactions = db.relationship(
        "InventoryTransaction", backref="item", lazy=True, cascade="all, delete-orphan"
    )


class InventoryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("inventory_item.id"))
    type = db.Column(db.String(20))  # in | out | adjustment | sale_deduction
    quantity = db.Column(db.Float, default=0)
    reference = db.Column(db.String(120))
    note = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    amount = db.Column(db.Float)
    date = db.Column(db.Date, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"))


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(255))


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(255))
    ip_address = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(40))
    # reservation_reminder | low_inventory | cancelled_reservation | discount_approval | new_reservation
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    related_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
