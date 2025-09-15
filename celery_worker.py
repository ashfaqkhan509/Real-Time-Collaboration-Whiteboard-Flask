from celery import Celery, Task
from flask import Flask
from celery.schedules import crontab


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app

    # 🔹 Celery Beat Schedule
    celery_app.conf.beat_schedule = {
        "send-heartbeat-every-30-seconds": {
            "task": "board_app.tasks.send_heartbeat",
            "schedule": 30.0,
        },
        "snapshot-every-5-minutes": {
            "task": "board_app.tasks.create_board_snapshot",
            "schedule": crontab(minute="*/5"),
        },
    }

    return celery_app
