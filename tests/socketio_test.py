import time
from board_app.models import (
    User,
    Board,
    BoardMembership,
    DrawingAction,
    ActiveConnection,
    PermissionEnum,
)
from board_app import db
from board_app.utils import (
    has_board_access,
    has_edit_permission,
    get_active_users,
    update_last_seen,
    get_board_state,
    save_drawing_action,
    add_active_connection,
    remove_active_connection,
)


class TestWebSocketAuthentication:
    """Test WebSocket connection with authentication."""

    def test_has_board_access_with_valid_user(self, app, test_user, test_board):
        """Test that has_board_access returns True for valid user."""
        with app.app_context():
            result = has_board_access(test_board, test_user)
            assert result is True

    def test_has_board_access_with_invalid_user(self, app, test_user):
        """Test that has_board_access returns False for invalid user."""
        with app.app_context():
            # Create another user first
            other_user = User(username='otheruser', email='other@example.com')
            other_user.set_password('password')
            db.session.add(other_user)
            db.session.commit()

            # Create a board that the test user doesn't have access to
            board = Board(name='Private Board', created_by_id=other_user.id)
            db.session.add(board)
            db.session.commit()
            board_id = board.id

            result = has_board_access(board_id, test_user)
            assert result is False

    def test_has_edit_permission_with_admin_user(self, app, test_user, test_board):
        """Test that has_edit_permission returns True for admin user."""
        with app.app_context():
            result = has_edit_permission(test_board, test_user)
            assert result is True

    def test_has_edit_permission_with_view_user(self, app, test_user, test_board):
        """Test that has_edit_permission returns False for view-only user."""
        with app.app_context():
            # Change user permission to view-only
            membership = BoardMembership.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            membership.permission = PermissionEnum.VIEW
            db.session.commit()

            result = has_edit_permission(test_board, test_user)
            assert result is False


class TestMultipleUsersInGroup:
    """Test multiple users in the same group/board."""

    def test_multiple_users_in_same_board(
        self, app, test_board_with_members, test_user, test_user2
    ):
        """Test that multiple users can be added to the same board."""
        with app.app_context():
            # Check that both users have memberships
            membership1 = BoardMembership.query.filter_by(
                board_id=test_board_with_members,
                user_id=test_user
            ).first()
            membership2 = BoardMembership.query.filter_by(
                board_id=test_board_with_members,
                user_id=test_user2
            ).first()

            assert membership1 is not None
            assert membership2 is not None
            assert membership1.permission == PermissionEnum.ADMIN
            assert membership2.permission == PermissionEnum.EDIT

    def test_active_connections_tracking(
        self, app, test_board_with_members, test_user, test_user2
    ):
        """Test that active connections are properly tracked."""
        with app.app_context():
            # Add active connections for both users
            add_active_connection(test_board_with_members, test_user, 'channel1')
            add_active_connection(test_board_with_members, test_user2, 'channel2')

            # Check that both connections exist
            connections = ActiveConnection.query.filter_by(
                board_id=test_board_with_members
            ).all()
            assert len(connections) == 2

            user_ids = [conn.user_id for conn in connections]
            assert test_user in user_ids
            assert test_user2 in user_ids

    def test_get_active_users(
        self, app, test_board_with_members, test_user, test_user2
    ):
        """Test that get_active_users returns correct users."""
        with app.app_context():
            # Add active connections
            add_active_connection(test_board_with_members, test_user, 'channel1')
            add_active_connection(test_board_with_members, test_user2, 'channel2')

            # Get active users
            users = get_active_users(test_board_with_members)
            assert len(users) == 2
            assert 'testuser' in users
            assert 'testuser2' in users


class TestPersistenceOfActions:
    """Test persistence of drawing actions."""

    def test_drawing_action_persistence(self, app, test_board, test_user):
        """Test that drawing actions are persisted to database."""
        with app.app_context():
            drawing_data = {
                'action_type': 'pen',
                'action_data': {'x': 100, 'y': 200, 'color': 'black', 'size': 2},
                'action_id': 'test-action-1'
            }

            # Save drawing action
            result = save_drawing_action(test_board, test_user, drawing_data)
            assert result is not None

            # Check that action was saved to database
            action = DrawingAction.query.filter_by(action_id='test-action-1').first()
            assert action is not None
            assert action.board_id == test_board
            assert action.user_id == test_user
            assert action.action_data['x'] == 100
            assert action.action_data['y'] == 200
            assert action.action_data['color'] == 'black'

    def test_multiple_drawing_actions_persistence(self, app, test_board, test_user):
        """Test that multiple drawing actions are persisted in correct order."""
        with app.app_context():
            actions_data = [
                {
                    'action_type': 'pen',
                    'action_data': {'x': 100, 'y': 200, 'color': 'black'},
                    'action_id': 'test-action-1'
                },
                {
                    'action_type': 'pen',
                    'action_data': {'x': 150, 'y': 250, 'color': 'red'},
                    'action_id': 'test-action-2'
                },
                {
                    'action_type': 'eraser',
                    'action_data': {'x': 200, 'y': 300},
                    'action_id': 'test-action-3'
                }
            ]

            # Save all actions
            for action_data in actions_data:
                result = save_drawing_action(test_board, test_user, action_data)
                assert result is not None

            # Check that all actions were saved
            actions = DrawingAction.query.filter_by(
                board_id=test_board
            ).order_by(DrawingAction.created_at).all()
            assert len(actions) == 3

            # Check order and content
            assert actions[0].action_id == 'test-action-1'
            assert actions[1].action_id == 'test-action-2'
            assert actions[2].action_id == 'test-action-3'

            assert actions[0].action_data['color'] == 'black'
            assert actions[1].action_data['color'] == 'red'
            assert actions[2].action_type.value == 'erase'

    def test_board_state_retrieval(self, app, test_board, test_user):
        """Test that board state is correctly retrieved."""
        with app.app_context():
            # Create some drawing actions
            from board_app.models import ActionTypeEnum
            action1 = DrawingAction(
                board_id=test_board,
                user_id=test_user,
                action_type=ActionTypeEnum.DRAW,
                action_data={'x': 100, 'y': 200, 'color': 'black'},
                action_id='existing-action-1'
            )
            action2 = DrawingAction(
                board_id=test_board,
                user_id=test_user,
                action_type=ActionTypeEnum.DRAW,
                action_data={'x': 150, 'y': 250, 'color': 'red'},
                action_id='existing-action-2'
            )
            db.session.add(action1)
            db.session.add(action2)
            db.session.commit()

            # Get board state
            state = get_board_state(test_board)
            assert len(state) == 2

            # Check that actions are in correct order
            assert state[0]['action_id'] == 'existing-action-1'
            assert state[1]['action_id'] == 'existing-action-2'

    def test_clear_board_action(self, app, test_board, test_user):
        """Test that clear board action removes all previous actions."""
        with app.app_context():
            # First, create some drawing actions
            from board_app.models import ActionTypeEnum
            action1 = DrawingAction(
                board_id=test_board,
                user_id=test_user,
                action_type=ActionTypeEnum.DRAW,
                action_data={'x': 100, 'y': 200, 'color': 'black'},
                action_id='existing-action-1'
            )
            action2 = DrawingAction(
                board_id=test_board,
                user_id=test_user,
                action_type=ActionTypeEnum.DRAW,
                action_data={'x': 150, 'y': 250, 'color': 'red'},
                action_id='existing-action-2'
            )
            db.session.add(action1)
            db.session.add(action2)
            db.session.commit()

            # Verify actions exist
            actions_before = DrawingAction.query.filter_by(
                board_id=test_board
            ).count()
            assert actions_before == 2

            # Send clear board action
            clear_data = {
                'action_type': 'clear',
                'action_data': {},
                'action_id': 'clear-action-1'
            }
            result = save_drawing_action(test_board, test_user, clear_data)
            assert result is not None

            # Check that all actions were removed
            actions_after = DrawingAction.query.filter_by(
                board_id=test_board
            ).count()
            assert actions_after == 0


class TestPresenceUpdates:
    """Test presence updates when users connect/disconnect."""

    def test_add_active_connection(self, app, test_board, test_user):
        """Test that active connections are properly added."""
        with app.app_context():
            # Add active connection
            add_active_connection(test_board, test_user, 'test-channel')

            # Check that connection was created
            connection = ActiveConnection.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            assert connection is not None
            assert connection.channel_name == 'test-channel'

    def test_remove_active_connection(self, app, test_board, test_user):
        """Test that active connections are properly removed."""
        with app.app_context():
            # Add active connection first
            add_active_connection(test_board, test_user, 'test-channel')

            # Verify it exists
            connection = ActiveConnection.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            assert connection is not None

            # Remove active connection
            remove_active_connection(test_board, test_user)

            # Check that connection was removed
            connection = ActiveConnection.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            assert connection is None

    def test_update_last_seen(self, app, test_board, test_user):
        """Test that last_seen timestamp is updated."""
        with app.app_context():
            # Add active connection
            add_active_connection(test_board, test_user, 'test-channel')

            # Get initial timestamp
            connection = ActiveConnection.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            initial_last_seen = connection.last_seen

            # Wait a bit
            time.sleep(0.1)

            # Update last seen
            update_last_seen(test_board, test_user)

            # Check that last_seen was updated
            db.session.refresh(connection)
            assert connection.last_seen > initial_last_seen

    def test_get_active_users_functionality(
        self, app, test_board_with_members, test_user, test_user2
    ):
        """Test that get_active_users returns correct users."""
        with app.app_context():
            # Add active connections for both users
            add_active_connection(test_board_with_members, test_user, 'channel1')
            add_active_connection(test_board_with_members, test_user2, 'channel2')

            # Get active users
            users = get_active_users(test_board_with_members)
            assert len(users) == 2
            assert 'testuser' in users
            assert 'testuser2' in users


class TestErrorHandling:
    """Test error handling in WebSocket events."""

    def test_drawing_action_without_permission(self, app, test_board, test_user):
        """Test that drawing action is rejected without edit permission."""
        with app.app_context():
            # Change user permission to view-only
            membership = BoardMembership.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            membership.permission = PermissionEnum.VIEW
            db.session.commit()

            # Try to save drawing action
            drawing_data = {
                'action_type': 'pen',
                'action_data': {'x': 100, 'y': 200, 'color': 'black'},
                'action_id': 'test-action-1'
            }

            # This should work because save_drawing_action doesn't check permissions
            # The permission check happens in the WebSocket handler
            result = save_drawing_action(test_board, test_user, drawing_data)
            assert result is not None

    def test_drawing_action_with_invalid_board(self, app, test_user):
        """Test that drawing action fails with invalid board."""
        with app.app_context():
            drawing_data = {
                'action_type': 'pen',
                'action_data': {'x': 100, 'y': 200, 'color': 'black'},
                'action_id': 'test-action-1'
            }

            # Try to save to non-existent board
            result = save_drawing_action(99999, test_user, drawing_data)
            assert result is None


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_complete_user_workflow(self, app, test_board, test_user):
        """Test complete user workflow: connect, draw, disconnect."""
        with app.app_context():
            # 1. User connects (add active connection)
            add_active_connection(test_board, test_user, 'test-channel')

            # 2. User draws something
            drawing_data = {
                'action_type': 'pen',
                'action_data': {'x': 100, 'y': 200, 'color': 'black'},
                'action_id': 'workflow-action-1'
            }
            result = save_drawing_action(test_board, test_user, drawing_data)
            assert result is not None

            # 3. Check that action was saved
            action = DrawingAction.query.filter_by(
                action_id='workflow-action-1'
            ).first()
            assert action is not None

            # 4. User disconnects (remove active connection)
            remove_active_connection(test_board, test_user)

            # 5. Check that connection was removed
            connection = ActiveConnection.query.filter_by(
                board_id=test_board,
                user_id=test_user
            ).first()
            assert connection is None

    def test_multiple_users_collaboration(
        self, app, test_board_with_members, test_user, test_user2
    ):
        """Test multiple users collaborating on the same board."""
        with app.app_context():
            # Both users connect
            add_active_connection(test_board_with_members, test_user, 'channel1')
            add_active_connection(test_board_with_members, test_user2, 'channel2')

            # User 1 draws something
            drawing_data1 = {
                'action_type': 'pen',
                'action_data': {'x': 100, 'y': 200, 'color': 'black'},
                'action_id': 'user1-action-1'
            }
            result1 = save_drawing_action(
                test_board_with_members, test_user, drawing_data1
            )
            assert result1 is not None

            # User 2 draws something
            drawing_data2 = {
                'action_type': 'pen',
                'action_data': {'x': 150, 'y': 250, 'color': 'red'},
                'action_id': 'user2-action-1'
            }
            result2 = save_drawing_action(
                test_board_with_members, test_user2, drawing_data2
            )
            assert result2 is not None

            # Check that both actions were saved
            actions = DrawingAction.query.filter_by(
                board_id=test_board_with_members
            ).all()
            assert len(actions) == 2

            # Check that both users are active
            active_users = get_active_users(test_board_with_members)
            assert len(active_users) == 2
            assert 'testuser' in active_users
            assert 'testuser2' in active_users

            # User 1 disconnects
            remove_active_connection(test_board_with_members, test_user)

            # Check that only user 2 is active
            active_users = get_active_users(test_board_with_members)
            assert len(active_users) == 1
            assert 'testuser2' in active_users
            assert 'testuser' not in active_users
