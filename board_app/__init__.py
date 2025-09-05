from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from board_app.config import Config
from flask_socketio import SocketIO
from flask_login import LoginManager


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

socketio = SocketIO()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    login_manager.init_app(app)

    from board_app import routes
    app.register_blueprint(routes.auth_bp)
    app.register_blueprint(routes.board_bp)

    import board_app.sockerio_handlers  # noqa: F401

    return app


@login_manager.user_loader
def load_user(user_id):
    from board_app.models import User
    return User.query.get(int(user_id))
