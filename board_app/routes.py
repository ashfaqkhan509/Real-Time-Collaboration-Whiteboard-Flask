from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from board_app import db
from board_app.models import Board, BoardMembership, PermissionEnum, User
from board_app.forms import RegistrationForm, LoginForm, CreateBoardForm


auth_bp = Blueprint("auth", __name__)
board_bp = Blueprint("board", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("board.list_boards"))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("auth.register"))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.username}! Your account has been created.", "success")
        return redirect(url_for("board.list_boards"))

    return render_template("register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("board.list_boards"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("You have been logged in!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("board.list_boards"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@board_bp.route("/")
@login_required
def list_boards():
    boards = Board.query.all()
    return render_template("list_boards.html", boards=boards)


@board_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_board():
    form = CreateBoardForm()
    if form.validate_on_submit():
        board = Board(
            name=form.name.data,
            created_by=current_user
        )
        db.session.add(board)
        db.session.commit()

        membership = BoardMembership(
            board_id=board.id,
            user_id=current_user.id,
            permission=PermissionEnum.ADMIN
        )
        db.session.add(membership)
        db.session.commit()

        flash("Board created successfully.", "success")
        return redirect(url_for("board.board_detail", board_id=board.id))

    return render_template("create_board.html", form=form)


@board_bp.route("/<int:board_id>")
@login_required
def board_detail(board_id):
    board = Board.query.get(board_id)

    membership = BoardMembership.query.filter_by(board_id=board_id, user_id=current_user.id).first()
    if not membership:
        flash("You are not a member of this board.", "danger")
        return redirect(url_for("board.list_boards"))
    
    can_draw = membership.permission in [PermissionEnum.ADMIN, PermissionEnum.EDIT]

    return render_template(
        'board_detail.html',
        board=board,
        membership=membership,
        can_draw=can_draw
    )


@board_bp.route("/<int:board_id>/add_member", methods=["GET", "POST"])
@login_required
def add_member(board_id):
    board = Board.query.get_or_404(board_id)

    # Check admin rights
    membership = BoardMembership.query.filter_by(board_id=board.id, user_id=current_user.id).first()
    if not membership or membership.permission != PermissionEnum.ADMIN:
        flash("You do not have permission to add members.", "danger")
        return redirect(url_for("board.board_detail", board_id=board.id))

    if request.method == "POST":
        user_id = request.form.get("user_id")
        permission_value = request.form.get("permission", "view")

        user = User.query.get(user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("board.add_member", board_id=board.id))

        # Check if already member
        existing = BoardMembership.query.filter_by(board_id=board.id, user_id=user.id).first()
        if existing:
            flash(f"{user.username} is already a member.", "warning")
            return redirect(url_for("board.add_member", board_id=board.id))

        # Validate permission
        try:
            permission = PermissionEnum(permission_value)
        except ValueError:
            flash("Invalid permission type.", "danger")
            return redirect(url_for("board.add_member", board_id=board.id))

        # Add membership
        new_membership = BoardMembership(
            board_id=board.id,
            user_id=user.id,
            permission=permission
        )
        db.session.add(new_membership)
        db.session.commit()

        flash(f"{user.username} added with {permission.value} permission.", "success")
        return redirect(url_for("board.board_detail", board_id=board.id))

    # For GET → fetch users not in board
    existing_member_ids = [m.user_id for m in board.memberships]
    available_users = User.query.filter(~User.id.in_(existing_member_ids)).all()

    return render_template("add_member.html", board=board, users=available_users)
