
import secrets
import time

from django.core.cache import cache

from ..models import User

OTP_TTL = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_INTERVAL = 30
OTP_CACHE_PREFIX = "users:otp:"


def _cache_key(otp_token):
    return f"{OTP_CACHE_PREFIX}{otp_token}"


def create_otp(user_id):
    otp_token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(10_000):04d}"
    now = time.time()

    data = {
        "user_id": user_id,
        "code": code,
        "attempts": 0,
        "created_at": now,
        "last_sent_at": now,
    }

    cache.set(_cache_key(otp_token), data, timeout=OTP_TTL)

    return otp_token, code


def get_otp_user(otp_token):
    data = cache.get(_cache_key(otp_token))

    if data is None:
        return None

    return User.objects.filter(
        pk=data["user_id"],
        is_active=True,
    ).first()


def verify_otp(otp_token, code):
    key = _cache_key(otp_token)
    data = cache.get(key)

    if data is None:
        return False, None, "Código expirado ou inválido."

    if data["attempts"] >= OTP_MAX_ATTEMPTS:
        cache.delete(key)
        return False, None, "Limite de tentativas atingido."

    if not secrets.compare_digest(data["code"], str(code)):
        data["attempts"] += 1

        if data["attempts"] >= OTP_MAX_ATTEMPTS:
            cache.delete(key)
        else:
            remaining = max(
                1,
                OTP_TTL - int(time.time() - data["created_at"]),
            )
            cache.set(key, data, timeout=remaining)

        return False, None, "Código incorreto."

    cache.delete(key)
    return True, data["user_id"], None


def resend_otp(otp_token, send_callback):
    key = _cache_key(otp_token)
    data = cache.get(key)

    if data is None:
        return False, "Código expirado ou inválido."

    elapsed = time.time() - data["last_sent_at"]

    if elapsed < OTP_RESEND_INTERVAL:
        return False, "Aguarde antes de solicitar outro código."

    user = User.objects.filter(
        pk=data["user_id"],
        is_active=True,
    ).first()

    if user is None or not user.email:
        return False, "Usuário inválido ou sem e-mail cadastrado."

    code = f"{secrets.randbelow(10_000):04d}"

    # Só atualiza o código se o envio do e-mail funcionar.
    send_callback(user, code)

    data["code"] = code
    data["last_sent_at"] = time.time()

    remaining = max(
        1,
        OTP_TTL - int(time.time() - data["created_at"]),
    )
    cache.set(key, data, timeout=remaining)

    return True, None
