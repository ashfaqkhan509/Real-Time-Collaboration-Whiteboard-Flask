from board_app.config import TestConfig
import pytest
from board_app import create_app, db
from board_app.models import User, Board, BoardMembership, PermissionEnum
import socketio as client_socketio


@pytest.fixture(scope='function')
def app():
    app = create_app(TestConfig)   # ✅ force TestConfig
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def socketio_client(app):
    """Create SocketIO test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.close()
        return user_id


@pytest.fixture(scope='function')
def test_user2(app):
    """Create a second test user."""
    with app.app_context():
        user = User(username='testuser2', email='test2@example.com')
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.close()
        return user_id


@pytest.fixture(scope='function')
def test_board(app, test_user):
    """Create a test board."""
    with app.app_context():
        board = Board(name='Test Board', created_by_id=test_user)
        db.session.add(board)
        db.session.commit()

        # Add user as admin member
        membership = BoardMembership(
            user_id=test_user,
            board_id=board.id,
            permission=PermissionEnum.ADMIN
        )
        db.session.add(membership)
        db.session.commit()

        board_id = board.id
        db.session.close()
        return board_id


@pytest.fixture(scope='function')
def test_board_with_members(app, test_user, test_user2):
    """Create a test board with multiple members."""
    with app.app_context():
        board = Board(name='Test Board with Members', created_by_id=test_user)
        db.session.add(board)
        db.session.commit()

        # Add users as members
        admin_membership = BoardMembership(
            user_id=test_user,
            board_id=board.id,
            permission=PermissionEnum.ADMIN
        )
        edit_membership = BoardMembership(
            user_id=test_user2,
            board_id=board.id,
            permission=PermissionEnum.EDIT
        )
        db.session.add(admin_membership)
        db.session.add(edit_membership)
        db.session.commit()

        board_id = board.id
        db.session.close()
        return board_id


@pytest.fixture(scope='function')
def authenticated_client(app, client, test_user):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
    return client


@pytest.fixture(scope='function')
def socketio_test_client():
    """Create a SocketIO client for testing."""
    return client_socketio.Client()


@pytest.fixture(scope='function')
def socketio_test_client2():
    """Create a second SocketIO client for testing."""
    return client_socketio.Client()
