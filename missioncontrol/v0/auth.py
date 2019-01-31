import time
import six

from django.contrib.auth import authenticate
from jose import JWTError, jwt
from werkzeug.exceptions import Unauthorized
from django.conf import settings


def _current_timestamp():
    return int(time.time())


def generate_token(token_info):
    timestamp = _current_timestamp()
    payload = {
        "iss": settings.JWT_ISSUER,
        "iat": int(timestamp),
        "exp": int(timestamp + settings.JWT_LIFETIME_SECONDS),
        "sub": str(token_info['sub'])
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_jwt(token):
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as e:
        six.raise_from(Unauthorized, e)


def basic_auth(username, password, required_scopes=None):
    user = authenticate(username=username, password=password)
    if user is not None:
        # A backend authenticated the credentials
        groups = list(user.groups.values('name'))
        scopes = [g["name"] for g in groups]
        info = {'sub': user.id, 'scope': scopes}
    else:
        # No backend authenticated the credentials
        return None

    # TODO validate scopes

    return info
