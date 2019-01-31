import json
import pytest

from home.models import GroundStation
import api


@pytest.mark.django_db
def test_groundstation_does_not_exist(test_client, simple_gs):
    response = test_client.get("api/v0/groundstations/{hwid}/".format(hwid="moonbase7"))
    assert response.status_code == 404
    assert response.json


@pytest.mark.django_db
def test_groundstation_create_and_update(test_client, simple_gs):
    data = json.dumps(simple_gs)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
        data=data,
        headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_gs

    response = test_client.put(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
        data=data,
        headers=headers
    )
    assert response.status_code == 200
    assert response.json == simple_gs


@pytest.mark.django_db
def test_groundstation_create_and_delete(test_client, simple_gs):
    data = json.dumps(simple_gs)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
        data=data,
        headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_gs

    response = test_client.delete(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
    )
    assert response.status_code == 204


@pytest.mark.django_db
def test_groundstation_create_and_patch(test_client, simple_gs):
    data = json.dumps(simple_gs)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
        data=data,
        headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_gs

    patch = {"latitude": 0.01}
    data = json.dumps(patch)
    headers = {"content-type": "application/json"}
    response = test_client.patch(
        "api/v0/groundstations/{hwid}/".format(hwid="moonbase7"),
        data=data,
        headers=headers
    )
    assert response.status_code == 200
    simple_gs.update(patch)
    assert response.json == simple_gs

