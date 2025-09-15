from board_app import create_app
import board_app.tasks  # noqa: F401, noqa: E402

flask_app = create_app()
celery_app = flask_app.extensions['celery']
