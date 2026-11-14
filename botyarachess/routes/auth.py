"""Registration and login."""
from __future__ import annotations

import re

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..localization.strings import locale_for, t
from ..models import User

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[\w-]{3,32}$", re.UNICODE)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request_is_post():
        username = (form_value("username") or "").strip()
        password = form_value("password") or ""
        confirm = form_value("confirm") or ""
        locale = locale_for(None)

        if not USERNAME_RE.match(username):
            flash(t("username_len", locale), "error")
        elif len(password) < 6:
            flash(t("password_len", locale), "error")
        elif password != confirm:
            flash(t("passwords_differ", locale), "error")
        elif User.query.filter(db.func.lower(User.username) == username.lower()).first():
            flash(t("user_exists", locale), "error")
        else:
            user = User(username=username, locale="")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(t("account_created", locale, name=username), "success")
            return redirect(url_for("main.index"))
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request_is_post():
        username = (form_value("username") or "").strip()
        password = form_value("password") or ""
        user = User.query.filter(
            db.func.lower(User.username) == username.lower()).first()
        if user is not None and user.check_password(password):
            login_user(user)
            flash(t("welcome_back", locale_for(user), name=user.username), "success")
            return redirect(url_for("main.index"))
        flash(t("bad_credentials", locale_for(None)), "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash(t("bye", locale_for(None)), "success")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------- helpers
def request_is_post() -> bool:
    from flask import request
    return request.method == "POST"


def form_value(key: str) -> str | None:
    from flask import request
    return request.form.get(key)
