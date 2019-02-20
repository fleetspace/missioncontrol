import json
import pytest


@pytest.mark.django_db
def test_pass_task_run(test_client, simple_task_stack, simple_pass,
                             simple_sat, simple_gs, simple_task_run, some_uuid, another_uuid, yet_another_uuid):

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/", json=asset)

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)
    response = test_client.put(f'/api/v0/passes/{some_uuid}/', json=simple_pass)
    assert response.status_code == 201, f"status code {response.status_code} not 201. Data: {response.get_data()}"
    response = test_client.put(f'/api/v0/task-stacks/{yet_another_uuid}/', json=simple_task_stack)
    assert response.status_code == 201, f"status code {response.status_code} not 201. Data: {response.get_data()}"

    # TODO test this not being used
    simple_pass['task_stack'] = yet_another_uuid
    simple_task_run['task_stack'] = yet_another_uuid

    # Create a task_run
    response = test_client.put(f"/api/v0/passes/{some_uuid}/task-runs/{another_uuid}/", json=simple_task_run)

    expected = simple_task_run.copy()
    expected['pass'] = some_uuid
    expected['uuid'] = another_uuid
    expected['stdout'] = None
    expected['stderr'] = None

    assert response.status_code == 201, f"status code {response.status_code} not 201. Data: {response.get_data()}"
    assert response.json == expected
