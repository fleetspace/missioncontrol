import json
import pytest


@pytest.mark.django_db
def test_satellite_does_not_exist(test_client, simple_sat):
    response = test_client.get("api/v0/satellites/{hwid}/".format(hwid="tiangong2"))
    assert response.status_code == 404
    assert response.json


@pytest.mark.django_db
def test_satellite_create_and_update(test_client, simple_sat):
    data = json.dumps(simple_sat)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/satellites/{hwid}/".format(hwid="tiangong2"), data=data, headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_sat

    response = test_client.put(
        "api/v0/satellites/{hwid}/".format(hwid="tiangong2"), data=data, headers=headers
    )
    assert response.status_code == 200
    assert response.json == simple_sat


@pytest.mark.django_db
def test_satellite_create_and_delete(test_client, simple_sat):
    data = json.dumps(simple_sat)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/satellites/{hwid}/".format(hwid="tiangong2"), data=data, headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_sat

    response = test_client.delete("api/v0/satellites/{hwid}/".format(hwid="tiangong2"))
    assert response.status_code == 204


@pytest.mark.django_db
def test_satellite_create_and_patch(test_client, simple_sat):
    data = json.dumps(simple_sat)
    headers = {"content-type": "application/json"}
    response = test_client.put(
        "api/v0/satellites/{hwid}/".format(hwid="tiangong2"), data=data, headers=headers
    )
    assert response.status_code == 201
    assert response.json == simple_sat

    patch = {"catid": "bananas"}
    data = json.dumps(patch)
    headers = {"content-type": "application/json"}
    response = test_client.patch(
        "api/v0/satellites/{hwid}/".format(hwid="tiangong2"), data=data, headers=headers
    )
    assert response.status_code == 200
    simple_sat.update(patch)
    assert response.json == simple_sat
