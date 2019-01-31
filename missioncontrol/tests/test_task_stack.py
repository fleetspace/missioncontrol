import copy
import json
import pytest

from uuid import uuid4

from home.models import Satellite
import api


@pytest.mark.django_db
def test_task_stack_create_conflict_from_put(test_client, simple_task_stack):
    ts_uuid = simple_task_stack["uuid"]

    read_only_fields = ("created", )

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    # create one
    response = test_client.put(
        f"/api/v0/task-stacks/{ts_uuid}/",
        json=simple_task_stack
    )
    assert response.status_code == 201
    assert remove_read_only(response.json) == simple_task_stack

    # create conflict
    response = test_client.put(
        f"/api/v0/task-stacks/{ts_uuid}/",
        json=simple_task_stack
    )
    assert response.status_code == 409
    assert remove_read_only(response.json["task_stack"]) == simple_task_stack


@pytest.mark.django_db
def test_task_stack_list_get_pinned(test_client, simple_task_stack,
                                    pinned_task_stack):
    read_only_fields = ("created", )

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    # create unpinned
    ts0_uuid = simple_task_stack["uuid"]
    response = test_client.put(
        f"/api/v0/task-stacks/{ts0_uuid}/",
        json=simple_task_stack
    )
    assert response.status_code == 201
    assert remove_read_only(response.json) == simple_task_stack

    # create pinned
    ts1_uuid = pinned_task_stack["uuid"]
    response = test_client.put(
        f"/api/v0/task-stacks/{ts1_uuid}/",
        json=pinned_task_stack
    )
    assert response.status_code == 201
    assert remove_read_only(response.json) == pinned_task_stack

    # get list
    response = test_client.get(
        "/api/v0/task-stacks/"
    )
    assert response.status_code == 200
    assert len(response.json) == 1
    assert remove_read_only(response.json[0]) == pinned_task_stack


@pytest.mark.django_db
def test_task_stack_list_text_search(test_client, pinned_task_stack):
    read_only_fields = ("created", )

    def remove_read_only(ts):
        for f in read_only_fields:
            ts.pop(f)
        return ts

    def clone(ts, **kwargs):
        ts_new = copy.deepcopy(ts)
        ts_new["uuid"] = str(uuid4())
        ts_new.update(kwargs)
        return ts_new

    def put(stacks):
        ret = []
        for stack in stacks:
            ts = clone(pinned_task_stack, **stack)
            ts_uuid = ts["uuid"]
            response = test_client.put(
                f"/api/v0/task-stacks/{ts_uuid}/",
                json=ts
            )
            assert response.status_code == 201
            j = copy.deepcopy(response.json)
            ret.append(j)
            assert remove_read_only(response.json) == ts
        return ret

    stacks = [
        {"name": "mominal", "environment": "banana"},
        {"name": "nomilar", "environment": "squash"},
        {"name": "nominar", "environment": "banana"},
        {"name": "lominal", "environment": "squash"}
    ]
    put_stacks = put(stacks)

    # get list
    response = test_client.get(
        "/api/v0/task-stacks/?name=nom&environment=banana"
    )
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0] == put_stacks[2]

    # get list
    response = test_client.get(
        "/api/v0/task-stacks/?environment=squash&name=mi"
    )
    assert response.status_code == 200
    assert len(response.json) == 2
    assert response.json == [put_stacks[1], put_stacks[3]]
