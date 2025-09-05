from board_app.models import (
    PermissionEnum,
    User,
    Board,
    BoardMembership,
    DrawingAction,
    BoardSnapshot,
    ActiveConnection
)
from board_app import db
from datetime import datetime
from flask_socketio import emit
from board_app import socketio


def get_user(username):
    return db.session.query(User).filter_by(username=username).first()


def get_board(board_id):
    return db.session.query(Board).filter_by(id=board_id).first()


def get_board_membership(board_id, user_id):
    return db.session.query(BoardMembership).filter_by(board_id=board_id, user_id=user_id).first()


def get_drawing_action(board_id, action_id):
    return db.session.query(DrawingAction).filter_by(board_id=board_id, action_id=action_id).first()


def get_board_snapshot(board_id):
    return db.session.query(BoardSnapshot).filter_by(board_id=board_id).first()


def get_active_connection(board_id, user_id):
    return db.session.query(ActiveConnection).filter_by(board_id=board_id, user_id=user_id).first()


def has_board_access(board_id, user_id):
    try:
        board = get_board(board_id)
        if not board:
            return False
        
        membership = get_board_membership(board_id, user_id)
        
        return membership is not None
    except Exception as e:
        print(f"Error while checking board access:{e}")
        return False


def has_edit_permission(board_id, user_id):
    try:
        membership = get_board_membership(board_id, user_id)

        if not membership:
            return False
        
        return membership.permission in [PermissionEnum.EDIT, PermissionEnum.ADMIN]
    except Exception as e:
        print(f"Error while checking edit permission:{e}")
        return False


def get_board_state(board_id):
    """Get current board state from all drawing actions"""
    try:
        board = get_board(board_id)
        if not board:
            return []

        # Get all drawing actions for this board ordered by creation time
        actions = db.session.query(DrawingAction)\
            .filter_by(board_id=board_id)\
            .order_by(DrawingAction.created_at)\
            .all()
        
        # Convert to dict format for JSON serialization
        board_state = []
        for action in actions:
            # Prefer the original client tool stored in action_data.action_type if present
            client_tool = None
            try:
                if isinstance(action.action_data, dict):
                    client_tool = action.action_data.get('action_type') or action.action_data.get('tool')
            except Exception:
                client_tool = None

            board_state.append({
                'id': action.id,
                'action_type': client_tool or (action.action_type.value if hasattr(action.action_type, 'value') else action.action_type),
                'action_data': action.action_data,
                'action_id': action.action_id,
                'user_id': action.user_id,
                'timestamp': action.created_at.isoformat() if action.created_at else None
            })
        
        return board_state
    except Exception as e:
        print(f"Error while getting board state: {e}")
        return []


def save_drawing_action(board_id, user_id, data):
    """Save drawing action to database"""
    try:
        board = get_board(board_id)
        if not board:
            return None

        # Handle clear board action
        if data.get('action_type') == 'clear':
            # Delete all previous actions for this board
            db.session.query(DrawingAction).filter_by(board_id=board_id).delete()
            db.session.commit()
            return {
                'id': None,
                'action_type': 'clear',
                'action_data': {},
                'action_id': data['action_id'],
                'timestamp': datetime.utcnow().isoformat()
            }

        # Normalize client tool into model enum categories while preserving original tool in action_data
        client_action_type = data.get('action_type')
        if not client_action_type:
            raise ValueError('Missing action_type in drawing action data')

        # Persist the original client tool inside action_data for accurate replay
        action_data_payload = data.get('action_data') or {}
        if isinstance(action_data_payload, dict):
            action_data_payload['action_type'] = client_action_type

        # Map client tool to server enum
        from board_app.models import ActionTypeEnum  # local import to avoid circulars
        mapping = {
            'pen': ActionTypeEnum.DRAW,
            'eraser': ActionTypeEnum.ERASE,
            'line': ActionTypeEnum.SHAPE,
            'rectangle': ActionTypeEnum.SHAPE,
            'circle': ActionTypeEnum.SHAPE,
            'text': ActionTypeEnum.TEXT,
            'clear': ActionTypeEnum.CLEAR,
        }
        enum_action_type = mapping.get(client_action_type)
        if not enum_action_type:
            # Default unknowns to DRAW to avoid failures
            enum_action_type = ActionTypeEnum.DRAW

        action = DrawingAction(
            board_id=board_id,
            user_id=user_id,
            action_type=enum_action_type,
            action_data=action_data_payload,
            action_id=data['action_id']
        )
        db.session.add(action)
        db.session.commit()

        return {
            'id': action.id,
            # Return the original tool for clients
            'action_type': client_action_type,
            'action_data': action_data_payload,
            'action_id': action.action_id,
            'user_id': action.user_id,
            'timestamp': action.created_at.isoformat() if action.created_at else None
        }
    except Exception as e:
        print(f"Error while saving drawing action: {e}")
        db.session.rollback()
        return None


def add_active_connection(board_id, user_id, channel_name):
    """Add active connection"""
    try:
        # Remove existing connection for this user and board
        existing = ActiveConnection.query.filter_by(
            board_id=board_id,
            user_id=user_id
        ).first()
        
        if existing:
            existing.channel_name = channel_name
            existing.connected_at = datetime.utcnow()
            existing.last_seen = datetime.utcnow()
        else:
            connection = ActiveConnection(
                board_id=board_id,
                user_id=user_id,
                channel_name=channel_name
            )
            db.session.add(connection)
        
        db.session.commit()
    except Exception as e:
        print(f"Error adding active connection: {e}")
        db.session.rollback()


def remove_active_connection(board_id, user_id):
    """Remove active connection"""
    try:
        connection = ActiveConnection.query.filter_by(
            board_id=board_id,
            user_id=user_id
        ).first()
        
        if connection:
            db.session.delete(connection)
            db.session.commit()
    except Exception as e:
        print(f"Error removing active connection: {e}")
        db.session.rollback()


def get_active_users(board_id):
    """Get active users for a board"""
    try:
        connections = ActiveConnection.query.filter_by(
            board_id=board_id,
        ).join(ActiveConnection.user).all()

        users = [connection.user.username for connection in connections]
        return users
    except Exception as e:
        print(f"Error getting active users: {e}")
        return []


def update_last_seen(board_id, user_id):
    """Update last seen timestamp for a user"""
    try:
        connection = ActiveConnection.query.filter_by(
            board_id=board_id,
            user_id=user_id
        ).first()
        
        if connection:
            connection.last_seen = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        print(f"Error updating last seen: {e}")
        db.session.rollback()


def broadcast_user_joined(board_id, username):
    """Broadcast user joined message"""
    try:
        users = get_active_users(board_id)
        room_name = f"board-{board_id}"
        socketio.emit('user_joined', {
            'type': 'user_joined',
            'users': users,
            'username': username
        }, room=room_name)
    except Exception as e:
        print(f"Error broadcasting user joined: {e}")


def broadcast_user_left(board_id, username):
    """Broadcast user left message"""
    try:
        users = get_active_users(board_id)
        room_name = f"board-{board_id}"
        socketio.emit('user_left', {
            'type': 'user_left',
            'users': users,
            'username': username
        }, room=room_name)
    except Exception as e:
        print(f"Error broadcasting user left: {e}")