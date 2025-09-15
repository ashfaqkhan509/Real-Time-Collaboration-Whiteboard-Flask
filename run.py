from board_app import create_app, db, socketio
from board_app.models import (
    User,
    Board,
    BoardMembership,
    DrawingAction,
    BoardSnapshot,
    ActiveConnection
)
import os


app = create_app()


@app.shell_context_processor
def make_shell_context():
    return dict(
        db=db,
        User=User,
        Board=Board,
        BoardMembership=BoardMembership,
        DrawingAction=DrawingAction,
        BoardSnapshot=BoardSnapshot,
        ActiveConnection=ActiveConnection
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # Use Socket.IO server to enable websockets and proper event broadcasting
    print("Async mode in use:", socketio.async_mode)
    socketio.run(app, debug=True, host="0.0.0.0", port=port)
