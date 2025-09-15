from datetime import datetime
from typing import List, Optional
from board_app import db
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, JSON, UniqueConstraint, Enum
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    boards_created: Mapped[List["Board"]] = relationship(back_populates="created_by")
    memberships: Mapped[List["BoardMembership"]] = relationship(back_populates="user")
    drawing_actions: Mapped[List["DrawingAction"]] = relationship(back_populates="user")
    active_connections: Mapped[List["ActiveConnection"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User(username={self.username})>"

    # Password helpers
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Board(db.Model):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    created_by: Mapped["User"] = relationship(back_populates="boards_created")
    memberships: Mapped[List["BoardMembership"]] = relationship(back_populates="board")
    drawing_actions: Mapped[List["DrawingAction"]] = relationship(back_populates="board")
    snapshots: Mapped[List["BoardSnapshot"]] = relationship(back_populates="board")
    active_connections: Mapped[List["ActiveConnection"]] = relationship(back_populates="board")

    def __repr__(self):
        return f"<Board(name={self.name})>"

    def get_current_state(self):
        """Return board state (all saved drawing actions)."""
        return [
            {
                "id": action.id,
                "action_type": action.action_type,
                "action_data": action.action_data,
                "action_id": action.action_id,
                "timestamp": str(action.created_at),
                "user": action.user.username if action.user else None,
            }
            for action in sorted(self.drawing_actions, key=lambda a: a.created_at)
        ]


class PermissionEnum(enum.Enum):
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class BoardMembership(db.Model):
    __tablename__ = "board_memberships"
    __table_args__ = (UniqueConstraint("user_id", "board_id", name="uix_user_board"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"), nullable=False)
    permission: Mapped[PermissionEnum] = mapped_column(
        Enum(PermissionEnum),
        default=PermissionEnum.VIEW
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    board: Mapped["Board"] = relationship(back_populates="memberships")

    def __repr__(self):
        return f"<BoardMembership(user={self.user.username}, board={self.board.name}"


class ActionTypeEnum(enum.Enum):
    DRAW = "draw"
    SHAPE = "shape"
    TEXT = "text"
    ERASE = "erase"
    CLEAR = "clear"


class DrawingAction(db.Model):
    __tablename__ = "drawing_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action_type: Mapped[ActionTypeEnum] = mapped_column(Enum(ActionTypeEnum), nullable=False)
    action_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    action_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Relationships
    board: Mapped["Board"] = relationship(back_populates="drawing_actions")
    user: Mapped["User"] = relationship(back_populates="drawing_actions")

    def __repr__(self):
        return f"<DrawingAction(type={self.action_type.value}, board={self.board.name})>"


class BoardSnapshot(db.Model):
    __tablename__ = "board_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"), nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # full board state
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    board: Mapped["Board"] = relationship(back_populates="snapshots")

    def __repr__(self):
        return f"<BoardSnapshot(board={self.board.name}, created_at={self.created_at})>"


class ActiveConnection(db.Model):
    __tablename__ = "active_connections"
    __table_args__ = (UniqueConstraint("board_id", "user_id", name="uix_board_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(200), nullable=False)  # WebSocket channel
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    board: Mapped["Board"] = relationship(back_populates="active_connections")
    user: Mapped["User"] = relationship(back_populates="active_connections")

    def __repr__(self):
        return f"<ActiveConnection(user={self.user.username}, board={self.board.name})>"
