import json
import pytest


@pytest.mark.django_db
def test_attributes(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset),
        )

    create_asset("satellite", simple_sat)
    create_asset("groundstation", simple_gs)

    test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(
            {
                "satellite": simple_sat["hwid"],
                "groundstation": simple_gs["hwid"],
                "start_time": "2018-11-25T00:00:00Z",
                "end_time": "2018-11-25T01:00:00Z",
            }
        ),
    ).json

    attrs = test_client.get(f"/api/v0/passes/{some_uuid}/attributes/", headers=headers)

    assert attrs.status_code == 200

    assert attrs.json == {}

    # Put one
    attrs = test_client.put(
        f"/api/v0/passes/{some_uuid}/attributes/",
        headers=headers,
        data=json.dumps({"test": "value"}),
    ).json
    assert attrs == {"test": "value"}

    # Make sure a patch doesn't overwrite existing ones
    attrs = test_client.patch(
        f"/api/v0/passes/{some_uuid}/attributes/",
        headers=headers,
        data=json.dumps({"test2": "also here"}),
    ).json
    assert attrs == {"test": "value", "test2": "also here"}

    # Make sure put overwrites existing ones
    attrs = test_client.put(
        f"/api/v0/passes/{some_uuid}/attributes/",
        headers=headers,
        data=json.dumps({"test": "value"}),
    ).json
    assert attrs == {"test": "value"}

    # Check get works as well when there are arguments
    attrs = test_client.get(
        f"/api/v0/passes/{some_uuid}/attributes/", headers=headers
    ).json
    assert attrs == {"test": "value"}


@pytest.mark.django_db
def test_invalid_attribute(test_client, simple_sat, simple_gs, some_uuid):
    headers = {"content-type": "application/json"}

    def create_asset(asset_type, asset):
        asset_hwid = asset["hwid"]
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/",
            headers=headers,
            data=json.dumps(asset),
        )

    create_asset("satellite", simple_sat)
    create_asset("groundstation", simple_gs)

    test_client.put(
        f"/api/v0/passes/{some_uuid}/",
        headers=headers,
        data=json.dumps(
            {
                "satellite": simple_sat["hwid"],
                "groundstation": simple_gs["hwid"],
                "start_time": "2018-11-25T00:00:00Z",
                "end_time": "2018-11-25T01:00:00Z",
            }
        ),
    )

    # Put a number (expect failure)
    attrs = test_client.put(
        f"/api/v0/passes/{some_uuid}/attributes/",
        headers=headers,
        data=json.dumps({"test": 1234}),
    )
    assert attrs.status_code == 400

    # Put an object (expect failure)
    attrs = test_client.put(
        f"/api/v0/passes/{some_uuid}/attributes/",
        headers=headers,
        data=json.dumps({"test": {"test": "hhi"}}),
    )
    assert attrs.status_code == 400
