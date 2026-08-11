"""Seed the database with an admin/staff account and sample restaurant data."""
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    User,
    Category,
    Product,
    BuffetTier,
    RestaurantTable,
    InventoryItem,
    Supplier,
    Setting,
)

app = create_app()

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        db.session.add(
            User(
                username="admin",
                name="Restaurant Administrator",
                role="admin",
                password_hash=generate_password_hash("admin123"),
            )
        )
    if not User.query.filter_by(username="staff").first():
        db.session.add(
            User(
                username="staff",
                name="Front Desk Cashier",
                role="staff",
                password_hash=generate_password_hash("staff123"),
            )
        )
    db.session.commit()

    if not Category.query.first():
        cat_beverages = Category(name="Beverages")
        cat_buffet = Category(name="Buffet")
        cat_desserts = Category(name="Desserts")
        db.session.add_all([cat_beverages, cat_buffet, cat_desserts])
        db.session.commit()

        supplier = Supplier(name="Green Valley Meat & Produce", contact="0917-000-0000")
        db.session.add(supplier)
        db.session.commit()

        rice = InventoryItem(name="Rice", quantity=100, unit="kg", low_stock_threshold=15, supplier_id=supplier.id)
        soda_syrup = InventoryItem(name="Soda Syrup", quantity=30, unit="L", low_stock_threshold=5, supplier_id=supplier.id)
        db.session.add_all([rice, soda_syrup])
        db.session.commit()

        soda = Product(
            name="Bottled Soda",
            category_id=cat_beverages.id,
            selling_price=60,
            cost_price=25,
            is_buffet=False,
            barcode="4800000000012",
            inventory_item_id=soda_syrup.id,
            deduct_qty=0.2,
        )
        iced_tea = Product(
            name="House Iced Tea",
            category_id=cat_beverages.id,
            selling_price=50,
            cost_price=15,
            barcode="4800000000029",
        )
        halo_halo = Product(name="Halo-Halo", category_id=cat_desserts.id, selling_price=95, cost_price=40, barcode="4800000000036")
        buffet = Product(name="Unlimited Lunch Buffet", category_id=cat_buffet.id, is_buffet=True, inventory_item_id=rice.id, deduct_qty=0.3)

        db.session.add_all([soda, iced_tea, halo_halo, buffet])
        db.session.commit()

        db.session.add_all(
            [
                BuffetTier(product_id=buffet.id, tier="adult", price=599),
                BuffetTier(product_id=buffet.id, tier="senior", price=479),
                BuffetTier(product_id=buffet.id, tier="pwd", price=479),
                BuffetTier(product_id=buffet.id, tier="kids", price=299),
                BuffetTier(product_id=buffet.id, tier="free", price=0),
            ]
        )

    if not RestaurantTable.query.first():
        for i in range(1, 9):
            db.session.add(RestaurantTable(name=f"T{i}", capacity=4 if i % 2 else 6))

    if not Setting.query.filter_by(key="restaurant_name").first():
        db.session.add(Setting(key="restaurant_name", value="Sitio Verde Buffet Restaurant"))
        db.session.add(Setting(key="vat_rate", value="12"))
        db.session.add(Setting(key="receipt_footer", value="Thank you for dining with us!"))

    db.session.commit()
    print("Seed complete. Login with admin/admin123 or staff/staff123")
