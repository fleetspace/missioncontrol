import pytest
from base64 import b64encode
from uuid import uuid4

from flask.testing import FlaskClient
from django.contrib.auth.models import User

class AuthorizedClient(FlaskClient):
    def __init__(self, *args, **kwargs):
        username = kwargs.pop("username", "test_user")
        password = kwargs.pop("password", "test_password")
        creds =  "Basic {basic}"
        to_encode = "{user}:{password}"
        to_encode = to_encode.format(user=username, password=password)
        b64encoded_ascii = b64encode(to_encode.encode()).decode("ascii")
        creds = creds.format(basic=b64encoded_ascii)
        self._headers = {
            "Authorization": creds
        }
        super(AuthorizedClient, self).__init__(*args, **kwargs)
        jwt = self.get(
            "/api/v0/auth/jwt"
        ).data
        self._headers = {
            "Authorization": "Bearer {jwt}".format(
                jwt=jwt.decode("ascii")
            )
        }

    def open(self, *args, **kwargs):
        kwargs.setdefault("headers", {})
        kwargs["headers"].update(self._headers)
        return super(AuthorizedClient, self).open( *args, **kwargs)



@pytest.fixture
@pytest.mark.django_db
def test_client():
    from api import app
    flask_app = app.app

    test_user = 'test_user'
    test_password = 'test_password'

    my_admin = User.objects.create_superuser(
        test_user, 'myemail@test.com', test_password
    )

    flask_app.test_client_class = AuthorizedClient
    client = flask_app.test_client(username=test_user,
                                   password=test_password)

    return client


@pytest.fixture
def simple_gs():
    return {
        "hwid": "moonbase7",
        "latitude": 0.0,
        "longitude": 0.0,
        "elevation": 0,
        "horizon_mask": [5]*360,
        "passes_read_only": False,
    }


@pytest.fixture
def simple_task_stack():
    return {
        "uuid": "2e365919-73ae-456c-89ac-7a92bce704c6",
        "tasks": ["hello.py"],
        "environment": "docker.bar.space/missioncontrol_tasks:0.4.3",
        "name": "nominal-chops",
        "pinned": False
    }


@pytest.fixture
def pinned_task_stack():
    return {
        "uuid": "9f6236cc-6bce-4e78-b8fa-8de758c20d72",
        "tasks": ["hello.py", "byeee.py"],
        "environment": "docker.bar.space/missioncontrol_tasks:0.4.3",
        "name": "nominal-hops",
        "pinned": True
    }


@pytest.fixture
def simple_sat():
    return {
        "hwid": "tiangong2",
        "tle": ["1 41765U 16057A   18336.62979237  .00002898  00000-0  39285-4 0  9996",
                "2 41765  42.7853  58.4157 0008242 337.7306 164.9140 15.60111034126320"],
        "catid": "41765U",
        "logger_state": None,
        "task_stack": None
    }


@pytest.fixture
def simple_pass(simple_sat, simple_gs):
    return {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00.000000Z",
        "end_time": "2018-11-25T01:00:00.000000Z",
    }


@pytest.fixture
def some_uuid():
    return str(uuid4())


@pytest.fixture
def another_uuid():
    return str(uuid4())
