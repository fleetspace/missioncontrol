import json
import pytest

from home.models import Satellite
import api


@pytest.mark.django_db
def test_pass_does_not_exist(test_client, some_uuid):
    response = test_client.get(f"api/v0/passes/{some_uuid}/")
    assert response.status_code == 404
    assert response.json


@pytest.mark.django_db
def test_pass_create_from_times(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201
    assert response.json

    # update
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 200
    assert response.json

    # get individual
    response = test_client.get(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json

    # get collection
    response = test_client.get(
        f"/api/v0/passes/",
        query_string={"range_start": _pass["start_time"]},
        headers=headers
    )
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["uuid"] == some_uuid
 

@pytest.mark.django_db
def test_pass_create_and_patch(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201

    # patch field
    _pass = response.json
    patch = {"is_desired": False}
    response = test_client.patch(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(patch)
    )
    assert response.status_code == 200
    _pass.update(patch)
    assert response.json == _pass


@pytest.mark.django_db
def test_pass_create_conflict_from_put(test_client, simple_sat, simple_gs, some_uuid,
                              another_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create one
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201

    # create conflict
    response = test_client.put(
        f"/api/v0/passes/{another_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 409
    assert len(response.json["conflicts"]) == 1


@pytest.mark.django_db
def test_pass_create_conflict_from_patch(test_client, simple_sat, simple_gs, some_uuid,
                              another_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create one
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201

    # mark first pass stale
    patch = {"is_desired": False}
    response = test_client.patch(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(patch)
    )

    # create second pass that overlaps stale pass
    response = test_client.put(
        f"/api/v0/passes/{another_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201

    # mark first pass as desired
    patch = {"is_desired": True}
    response = test_client.patch(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(patch)
    )
    assert response.status_code == 409
    assert len(response.json["conflicts"]) == 1


@pytest.mark.django_db
def test_pass_create_and_get_track(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)

    params = {
        "range_start": "2018-12-04T21:46:00Z",
        "range_end": "2018-12-04T21:46:00Z"
    }
    response = test_client.get(
        f"/api/v0/accesses/",
        headers=headers,
        query_string=params
    )
    access = response.json[0]

    _pass = {
        "access_id": access["id"]
    }

    # create
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201
    _pass = response.json
    assert _pass["satellite"] == access["satellite"]
    assert _pass["groundstation"] == access["groundstation"]
    assert _pass["start_time"][:-8] == access["start_time"][:-8]
    assert _pass["end_time"][:-8] == access["end_time"][:-8]

    # get track
    response = test_client.get(
        f"/api/v0/passes/{some_uuid}/track/",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json

    five_step_track = response.json

    # Assumes default step is 5
    response = test_client.get(
        f"/api/v0/passes/{some_uuid}/track/?step=10",
        headers=headers
    )
    assert response.status_code == 200, response.get_data()
    # Subtract one for the edge point included, expected
    assert len(response.json) - 1 == len(five_step_track) / 2


@pytest.mark.django_db
def test_pass_create_and_list_stale(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
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
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201
    _pass = response.json

    # patch is_desired false
    patch = {"is_desired": False}
    response = test_client.patch(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(patch)
    )
    assert response.status_code == 200
    _pass.update(patch)
    assert response.json == _pass

    # check that we don't get back stale pass
    response = test_client.get(
        f"/api/v0/passes/",
        query_string={"range_start": _pass["start_time"]},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json == []

    # check that we get back stale with show_stale
    response = test_client.get(
        f"/api/v0/passes/",
        query_string={"show_stale": True,
                      "range_start": _pass["start_time"]},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json == [_pass]

@pytest.mark.django_db
def test_pass_task_stack_put(test_client, simple_sat, simple_gs, some_uuid, simple_task_stack):
    headers = {"content-type": "application/json"}
    ts_uuid = simple_task_stack["uuid"]

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset)
        )
        assert response.status_code == 201

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)
    test_client.put(
        f"/api/v0/task-stacks/{ts_uuid}/",
        json=simple_task_stack
    )

    _pass = {
        "satellite": simple_sat["hwid"],
        "groundstation": simple_gs["hwid"],
        "start_time": "2018-11-25T00:00:00.000000Z",
        "end_time": "2018-11-25T01:00:00.000000Z",
        "task_stack": ts_uuid,
    }
    # create
    response = test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(_pass)
    )
    assert response.status_code == 201
    _pass = response.json

    assert _pass['task_stack'] == ts_uuid