import uuid
import json
from unittest.mock import patch, call

import pytest

from django.conf import settings
from django.utils import timezone, dateformat


# Still needs a database for the user setup.
@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_signing(boto3_mock, test_client, some_hash, simple_file):
    post_values = {
        'url': 'https://test.example',
        'url_fields': {},
    }
    presign_mock = boto3_mock.client.return_value.generate_presigned_post
    presign_mock.return_value = post_values

    response = test_client.post(
        f'/api/v0/files/presign/',
        json=simple_file
    )
    assert response.status_code == 200, response.get_data()
    assert response.json == post_values

    # we require gzip
    presign_mock.assert_called_with(
        Bucket=settings.FILE_STORAGE_PATH.split('/')[2],
        Key=f'django-file-storage/{some_hash}/data',
        Conditions=[['eq', '$Content-Encoding', 'gzip']],
        Fields={'Content-Encoding': 'gzip'}
    )


# TODO use botocore.Stubber
@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_metadata_put(boto3_mock, test_client, some_hash, some_uuid,
                           simple_file, settings):
    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False

    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    assert response.status_code == 201, response.get_data()
    response = test_client.get(f'/api/v0/files/{some_uuid}/')

    assert response.status_code == 200, response.get_data()
    expected = simple_file.copy()

    formatter = dateformat.DateFormat(created)
    expected['created'] = formatter.format(settings.DATETIME_FORMAT)
    assert response.json == expected

    # ensure metadata is written to S3 for backup
    boto3_mock.assert_has_calls([
        call.client('s3'),
        call.client().put_object(
            Body=json.dumps(expected, sort_keys=True),
            ContentType='application/json',
            Bucket='bucketname',
            Key=f'django-file-storage/{some_hash}/metadata/{some_uuid}'),
    ])


# TODO use botocore.Stubber
@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_metadata_put_strict_whats(boto3_mock, test_client, some_hash,
                                        some_uuid, simple_file, settings):
    settings.DATALAKE_STRICT_WHATS = True
    settings.DATALAKE_STRICT_WORK_ID = False
    wat = simple_file["what"]

    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    # expect failure, unknown what
    assert response.status_code == 400, response.get_data()
    assert response.json["detail"] == f"Unknown what: {wat}"

    # add file what to allowed whats
    response = test_client.put(f'/api/v0/datalake/admin/whats/{wat}/')
    assert response.status_code == 201, response.get_data()

    # try PUT again
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    assert response.status_code == 201, response.get_data()

    # check with GET
    response = test_client.get(f'/api/v0/files/{some_uuid}/')
    assert response.status_code == 200, response.get_data()


# TODO use botocore.Stubber
@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_metadata_put_strict_work_id(boto3_mock, test_client, some_hash,
                                          some_uuid, simple_file, simple_sat,
                                          simple_gs, settings):
    settings.DATALAKE_STRICT_WHATS = True
    settings.DATALAKE_STRICT_WORK_ID = True
    wat = simple_file["what"]

    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    # expect failure, pass does not exist
    assert response.status_code == 400, response.get_data()

    # add file what to allowed whats
    response = test_client.put(f'/api/v0/datalake/admin/whats/{wat}/')
    assert response.status_code == 201, response.get_data()

    # try PUT again
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
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create
    response = test_client.put(
        f'/api/v0/passes/{simple_file["work_id"].split(".")[1]}/',
        json=_pass
    )
    assert response.status_code == 201
    assert response.json

    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    assert response.status_code == 201, response.get_data()

    # check with GET
    response = test_client.get(f'/api/v0/files/{some_uuid}/')
    assert response.status_code == 200, response.get_data()


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_download(boto3_mock, test_client, simple_file, some_uuid,
                       settings):
    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False
    test_url = 'http://someurl'
    signed_get_mock = boto3_mock.client.return_value.generate_presigned_url
    signed_get_mock.return_value = test_url
    response = test_client.put(f'/api/v0/files/{some_uuid}/', json=simple_file)
    assert response.status_code == 201, response.get_data()

    response = test_client.get(f'/api/v0/files/{some_uuid}/data/')
    assert response.status_code == 302, response.get_data()

    assert response.headers['Location'] == test_url


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_raw_content_download(boto3_mock, test_client, simple_file, some_uuid,
                              settings):
    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False
    test_url = 'http://someurl'
    signed_get_mock = boto3_mock.client.return_value.generate_presigned_url
    signed_get_mock.return_value = test_url
    response = test_client.put(f'/api/v0/files/{some_uuid}/', json=simple_file)
    assert response.status_code == 201, response.get_data()

    response = test_client.get(f'/api/v0/files/content/{simple_file["cid"]}/')
    assert response.status_code == 302, response.get_data()
    assert response.headers['Location'] == test_url


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_latest_search(boto3_mock, test_client, file_gen, settings):
    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False

    last = None
    for _ in range(0, 10):
        last = f = next(file_gen)
        response = test_client.put(
            f'/api/v0/files/{f["uuid"]}/',
            json=f
        )
        assert response.status_code == 201, response.get_data()

    response = test_client.get(
        f'/api/v0/files/latest/{f["what"]}/{f["where"]}/')
    assert response.status_code == 200, response.get_data()
    resp = response.json
    resp.pop("created")
    assert resp == last


@pytest.mark.django_db
def test_file_latest_search_empty(test_client, some_uuid):
    response = test_client.get(f'/api/v0/files/latest/a_thing/mc-flat/')
    assert response.status_code == 404, response.get_data()
    assert response.json


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_work_id_search(boto3_mock, test_client, some_uuid, simple_file,
                             simple_sat, simple_gs):
    settings.DATALAKE_STRICT_WHATS = True
    settings.DATALAKE_STRICT_WORK_ID = True

    wat = simple_file["what"]

    created = timezone.now()

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
        "start_time": "2018-11-25T00:00:00Z",
        "end_time": "2018-11-25T01:00:00Z",
    }

    # create
    response = test_client.put(
        f'/api/v0/passes/{simple_file["work_id"].split(".")[1]}/',
        json=_pass
    )
    assert response.status_code == 201
    assert response.json

    # add file what to allowed whats
    response = test_client.put(f'/api/v0/datalake/admin/whats/{wat}/')
    assert response.status_code == 201, response.get_data()

    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(
            f'/api/v0/files/{some_uuid}/',
            json=simple_file
        )
    assert response.status_code == 201, response.get_data()

    # check with GET
    response = test_client.get(
        f'/api/v0/files/work-id/{simple_file["work_id"]}/')
    assert response.status_code == 200, response.get_data()
    assert len(response.json) == 1
    resp = response.json[0]
    resp.pop("created")
    assert resp == simple_file


@pytest.mark.django_db
def test_file_work_id_search_empty(test_client, some_uuid):
    response = test_client.get('/api/v0/files/work-id/mc-jenkins.13203002/')
    assert response.status_code == 200, response.get_data()
    assert response.json == []


@pytest.mark.django_db
def test_file_timeline_search_empty(test_client):
    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'what': 'banana',
        })
    assert response.status_code == 200, response.get_data()
    assert response.json == []


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_file_timeline_search(boto3_mock, test_client, file_gen):

    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False

    files = []
    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        for _ in range(0, 10):
            last = f = next(file_gen)
            response = test_client.put(
                f'/api/v0/files/{f["uuid"]}/',
                json=f
            )
            f["created"] = created.isoformat(
                "T", timespec="microseconds").replace("+00:00", "Z")
            files += [f]
            assert response.status_code == 201, response.get_data()

    # create an arbitrary slice of files
    _slice = files[2:7]

    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'what': last["what"],
            'range_start': _slice[0]["start"],
            'range_end': _slice[-1]["start"]
        }
    )
    assert response.status_code == 200, response.get_data()
    assert response.json == _slice[::-1]  # results go back in time


@patch('datalake.models.boto3')
@pytest.mark.django_db
def test_reverse_metadata_loopkup(boto3_mock, test_client, file_gen):

    settings.DATALAKE_STRICT_WHATS = False
    settings.DATALAKE_STRICT_WORK_ID = False

    files = []
    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        for _ in range(0, 10):
            last = f = next(file_gen)
            response = test_client.put(
                f'/api/v0/files/{f["uuid"]}/',
                json=f
            )
            f["created"] = created.isoformat(
                "T", timespec="microseconds").replace("+00:00", "Z")
            files += [f]
            assert response.status_code == 201, response.get_data()

    response = test_client.get(
        f'/api/v0/files/cid/{f["cid"]}/',
    )
    assert response.status_code == 200, response.get_data()
    assert response.json == files[::-1]  # results go back in time


@pytest.mark.django_db
def test_file_search_required_what(test_client):
    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'where': 'a thing',
        }
    )
    assert response.status_code == 400, response.get_data()
    assert response.json['detail'] == "Missing query parameter 'what'"
