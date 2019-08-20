import json
import pytest


@pytest.mark.django_db
def test_satellite_task_stack_put(
    test_client, simple_sat, simple_gs, simple_task_stack, some_uuid
):
    read_only_fields = ("created",)

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(f"/api/v0/{asset_type}s/{asset_hwid}/", json=asset)

    create_asset("satellite", simple_sat)
    create_asset("groundstation", simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00.000000Z",
        "end_time": "2018-11-25T01:00:00.000000Z",
    }

    # create
    response = test_client.put(f"/api/v0/passes/{some_uuid}/", json=_pass)
    assert response.status_code == 201
    _pass = response.json

    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/task-stack/", json=simple_task_stack
    )
    ret = response.json
    assert response.status_code == 201
    assert remove_read_only(ret) == simple_task_stack

    response = test_client.get(f"/api/v0/passes/{some_uuid}/task-stack/")
    assert (
        response.status_code == 200
    ), f"status code {response.status_code} not 200. Data: {response.get_data()}"
    ret = response.json
    assert remove_read_only(ret) == simple_task_stack


@pytest.mark.django_db
def test_task_stack_no_exist(
    test_client, simple_task_stack, simple_pass, simple_sat, simple_gs, some_uuid
):
    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(f"/api/v0/{asset_type}s/{asset_hwid}/", json=asset)

    create_asset("satellite", simple_sat)
    create_asset("groundstation", simple_gs)

    test_client.put(f"/api/v0/passes/{some_uuid}/", json=simple_pass)

    response = test_client.get(f"/api/v0/passes/{some_uuid}/task-stack/")

    assert (
        response.status_code == 404
    ), f"status code {response.status_code} not 404. Data: {response.get_data()}"
