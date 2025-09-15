from celery import shared_task
from datetime import datetime
from board_app import socketio, db
from board_app.models import Board, BoardSnapshot


@shared_task
def send_heartbeat():
    """
    Send heartbeat messages to all connected users on all boards
    """
    boards = Board.query.all()

    for board in boards:
        board_group_name = f'board_{board.id}'

        # Flask-SocketIO uses `emit` to broadcast
        socketio.emit(
            'heartbeat',
            {'timestamp': datetime.now().isoformat()},
            to=board_group_name  # room name == board group
        )

    return "Heartbeat messages sent"


@shared_task
def create_board_snapshot():
    """
    Create snapshots for all boards
    """
    boards = Board.query.all()

    for board in boards:
        try:
            state = board.get_current_state()  # You’ll need to implement this in Board model
            snapshot = BoardSnapshot(board_id=board.id, snapshot_data=state)
            db.session.add(snapshot)
            db.session.commit()
            print(f"Snapshot created for board {board.name}")
        except Exception as e:
            print(f"Failed to create snapshot for {board.id}: {e}")

    return "All board snapshots created"
