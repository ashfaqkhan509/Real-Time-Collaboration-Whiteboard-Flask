from board_app import socketio
from flask_login import current_user
import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room, disconnect
from board_app.utils import (
    has_board_access,
    has_edit_permission,
    get_active_users,
    update_last_seen,
    broadcast_user_joined,
    broadcast_user_left,
    get_board_state,
    save_drawing_action,
    add_active_connection,
    remove_active_connection
)


@socketio.on('connect')
def handle_connect():
    board_id = request.args.get('board_id')

    if not board_id:
        disconnect()
        return

    if not current_user.is_authenticated:
        disconnect()
        return

    if not has_board_access(board_id, current_user.id):
        disconnect()
        return

    room_name = f"board-{board_id}"
    join_room(room_name)

    # Create a new active connection
    add_active_connection(board_id, current_user.id, request.sid)

    # Send current board state to the newly connected user
    board_state = get_board_state(board_id)
    emit('board_state', {
        'type': 'board_state',
        'state': board_state
    })

    # Broadcast user joined to all users in the room
    broadcast_user_joined(board_id, current_user.username)


@socketio.on('disconnect')
def handle_disconnect():
    board_id = request.args.get('board_id')

    if board_id and current_user.is_authenticated:
        room_name = f"board-{board_id}"
        leave_room(room_name)
        remove_active_connection(board_id, current_user.id)
        broadcast_user_left(board_id, current_user.username)


@socketio.on('drawing_action')
def handle_drawing_action(data):
    board_id = request.args.get('board_id')

    if not board_id:
        emit('error', {
            'type': 'error',
            'message': 'Board ID is required'
        })
        return

    if not has_edit_permission(board_id, current_user.id):
        emit('error', {
            'type': 'error',
            'message': 'You do not have permission to edit this board'
        })
        return

    # Save the drawing action
    action = save_drawing_action(board_id, current_user.id, data)

    if action:
        # Broadcast drawing action to all users in the room
        room_name = f"board-{board_id}"

        socketio.emit('drawing_action', {
            'type': 'drawing_action',
            'action': action,
            'current_user': current_user.username
        }, room=room_name)
    else:
        emit('error', {
            'type': 'error',
            'message': 'Failed to save drawing action'
        })


@socketio.on('cursor_position')
def handle_cursor_position(data):
    board_id = request.args.get('board_id')

    if not board_id:
        emit('error', {
            'type': 'error',
            'message': 'Board ID is required'
        })
        return

    room_name = f"board-{board_id}"
    socketio.emit('cursor_position', {
        'type': 'cursor_position',
        'x': data['x'],
        'y': data['y'],
        'user': current_user.username,
        'sender_sid': request.sid
    }, room=room_name, include_self=False)


@socketio.on('request_users')
def handle_request_users():
    board_id = request.args.get('board_id')

    if not board_id:
        emit('error', {
            'type': 'error',
            'message': 'Board ID is required'
        })
        return

    users = get_active_users(board_id)

    emit('active_users', {
        'type': 'active_users',
        'users': users
    })


@socketio.on('heartbeat')
def handle_heartbeat():
    board_id = request.args.get('board_id')

    if board_id and current_user.is_authenticated:
        update_last_seen(board_id, current_user.id)

        emit('heartbeat_response', {
            'type': 'heartbeat_response',
            'timestamp': datetime.datetime.utcnow().isoformat()
        })
