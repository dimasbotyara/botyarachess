"""Server-side localization helpers.

The heavy lifting (all static UI strings) is done client-side via JS
dictionaries; this module only handles flash/system messages produced by
Flask itself and picks the effective locale for a request.
"""
from __future__ import annotations

from flask import request

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "welcome_back": "Welcome back, {name}!",
        "account_created": "Account created. Welcome to botyarachess, {name}!",
        "bye": "See you soon!",
        "user_exists": "That username is already taken.",
        "bad_credentials": "Wrong username or password.",
        "login_required": "Please log in first.",
        "username_len": "Username must be 3–32 characters.",
        "username_chars": "Username may only contain letters, digits, _ and -.",
        "password_len": "Password must be at least 6 characters.",
        "passwords_differ": "Passwords do not match.",
        "settings_saved": "Settings saved.",
        "invalid_input": "Invalid input.",
    },
    "ru": {
        "welcome_back": "С возвращением, {name}!",
        "account_created": "Аккаунт создан. Добро пожаловать в botyarachess, {name}!",
        "bye": "До скорой встречи!",
        "user_exists": "Это имя уже занято.",
        "bad_credentials": "Неверное имя пользователя или пароль.",
        "login_required": "Сначала войдите в аккаунт.",
        "username_len": "Имя пользователя должно быть от 3 до 32 символов.",
        "username_chars": "Имя может содержать только буквы, цифры, _ и -.",
        "password_len": "Пароль должен быть не короче 6 символов.",
        "passwords_differ": "Пароли не совпадают.",
        "settings_saved": "Настройки сохранены.",
        "invalid_input": "Некорректный ввод.",
    },
}


def best_locale() -> str:
    """Locale for anonymous visitors: Accept-Language header, defaulting to en."""
    header = request.headers.get("Accept-Language", "")
    for chunk in header.split(","):
        code = chunk.split(";")[0].strip().lower()
        if code.startswith("ru"):
            return "ru"
        if code.startswith("en"):
            return "en"
    return "en"


def locale_for(user) -> str:
    """Effective locale: explicit user choice beats browser auto-detection."""
    if user is not None and getattr(user, "locale", ""):
        return user.locale
    return best_locale()


def t(key: str, locale: str = "en", **params) -> str:
    template = STRINGS.get(locale, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return template.format(**params) if params else template
