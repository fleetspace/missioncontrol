import json
import pytest


@pytest.mark.django_db
def test_satellite_task_stack_put(test_client, simple_sat, simple_task_stack):
    read_only_fields = ("created", )

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    response = test_client.put(
        "api/v0/satellites/{hwid}/".format(hwid=simple_sat["hwid"]),
        json=simple_sat
    )

    # create_task_stack
    simple_task_stack.pop("uuid")  # rely on serverside creation
    url = "/api/v0/satellites/{hwid}/task-stack/"
    url = url.format(hwid=simple_sat["hwid"])
    response = test_client.put(url, json=simple_task_stack)
    ret = response.json
    simple_task_stack["uuid"] = ret["uuid"]
    assert response.status_code == 201
    assert remove_read_only(ret) == simple_task_stack
