import json
import pytest


@pytest.mark.django_db
def test_satellite_task_stack_put(test_client, simple_sat, simple_gs,
                                  simple_task_stack, some_uuid):
    read_only_fields = ("created", )

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            json=asset
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00.000000Z",
        "end_time": "2018-11-25T01:00:00.000000Z",
    }

    # create
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        json=_pass
    )
    assert response.status_code == 201
    _pass = response.json

    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/task-stack/",
        json=simple_task_stack
    )
    ret = response.json
    assert response.status_code == 201
    assert remove_read_only(ret) == simple_task_stack

    response = test_client.get(
        f"/api/v0/passes/{some_uuid}/task-stack/",
    )
    ret = response.json
    assert response.status_code == 200
    assert remove_read_only(ret) == simple_task_stack
