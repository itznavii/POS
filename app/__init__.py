from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from app.config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.auth.routes import auth
    from app.main.routes import main
    from app.pos.routes import pos
    from app.tables.routes import tables_bp
    from app.kitchen.routes import kitchen
    from app.reservations.routes import reservations
    from app.inventory.routes import inventory
    from app.reports.routes import reports
    from app.admin.routes import admin
    from app.expenses.routes import expenses
    from app.customers.routes import customers
    from app.notifications.routes import notifications

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(main)
    app.register_blueprint(pos, url_prefix="/pos")
    app.register_blueprint(tables_bp, url_prefix="/tables")
    app.register_blueprint(kitchen, url_prefix="/kitchen")
    app.register_blueprint(reservations, url_prefix="/reservations")
    app.register_blueprint(inventory, url_prefix="/inventory")
    app.register_blueprint(reports, url_prefix="/reports")
    app.register_blueprint(admin, url_prefix="/admin")
    app.register_blueprint(expenses, url_prefix="/expenses")
    app.register_blueprint(customers, url_prefix="/customers")
    app.register_blueprint(notifications, url_prefix="/notifications")

    from app.notifications.helpers import unread_notification_count

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        count = 0
        if current_user.is_authenticated:
            count = unread_notification_count()
        return {"unread_notifications": count}

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
