from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from board_app.config import Config
from flask_socketio import SocketIO
from flask_login import LoginManager

from celery_worker import celery_init_app


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

socketio = SocketIO()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.config.from_mapping(
        CELERY=dict(
            broker_url=app.config['CELERY_BROKER_URL'],
            result_backend=app.config['CELERY_RESULT_BACKEND'],
            task_ignore_result=False
        )
    )

    # Safety: only block if running pytest with production DB
    if app.config['TESTING'] and "sqlite" not in app.config['SQLALCHEMY_DATABASE_URI']:
        raise RuntimeError("⚠️ Tests are running against a non-test database!")
    
    celery_init_app(app)

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
