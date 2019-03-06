import uuid
from unittest.mock import patch, call

import pytest
from django.conf import settings
from django.utils import timezone, dateformat


# TODO use botocore.Stubber
@patch('home.models.boto3')
@pytest.mark.django_db
def test_file_put_get(boto3_mock, test_client, some_hash, simple_file):
    post_values = {
        'url': 'https://test.example',
        'url_fields': {},
    }
    boto3_mock.client.return_value.generate_presigned_post.return_value = post_values

    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(f'/api/v0/files/{some_hash}/', json=simple_file)
    assert response.status_code == 201, response.get_data()
    response = test_client.get(f'/api/v0/files/{some_hash}/')

    assert response.status_code == 200, response.get_data()
    expected = simple_file.copy()

    formatter = dateformat.DateFormat(created)
    expected['created'] = formatter.format(settings.DATETIME_FORMAT)
    expected['version'] = 1
    assert response.json == expected

    try:
        boto3_mock.assert_has_calls([
            call.client('s3'),
            call.client().generate_presigned_post(
                Bucket='bucketname', Key=f'django-file-storage/{some_hash}'),
            call.client('s3'),
            call.client().generate_presigned_post(
                Bucket='bucketname', Key=f'django-file-storage/{some_hash}'),
        ],
            any_order=True
        ) is None
    except AssertionError:
        assert boto3_mock.mock_calls == []




@patch('home.models.boto3')
@pytest.mark.django_db
def test_file_download(boto3_mock, test_client, simple_file, some_hash):
    test_url = 'http://someurl'
    boto3_mock.client.return_value.generate_presigned_url.return_value = test_url
    response = test_client.put(f'/api/v0/files/{some_hash}/', json=simple_file)
    assert response.status_code == 201, response.get_data()

    response = test_client.get(f'/api/v0/files/{some_hash}/data/')
    assert response.status_code == 302, response.get_data()

    assert response.headers['Location'] == test_url


@pytest.mark.django_db
def test_file_search_empty(test_client, some_uuid):
    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'what': 'a thing',
            'cid': 'nope',
            'where': 'nowhere',
            'work_id': some_uuid,
            'range_start': "2018-11-25T00:00:00.000000Z",
            'range_end': "2018-11-25T00:00:00.000000Z",
        })
    assert response.status_code == 200, response.get_data()

    assert response.json == []

@pytest.mark.django_db
def test_file_search_one_key(test_client):
    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'what': 'a thing',
        })
    assert response.status_code == 200, response.get_data()

    assert response.json == []

@pytest.mark.django_db
def test_file_search_required_what(test_client):
    response = test_client.get(
        f'/api/v0/files/',
        query_string={
            'where': 'a thing',
        })
    assert response.status_code == 400, response.get_data()

    assert response.json['detail'] == "Missing query parameter 'what'"

@patch('home.models.boto3')
@pytest.mark.django_db
def test_file_search_after_put(boto_patch, test_client, simple_task_run,
                               simple_pass, another_uuid, some_uuid, some_hash,
                               simple_file, simple_sat, simple_gs,
                               yet_another_uuid, simple_task_stack):
    def create_asset(asset_type, asset):
        asset_hwid = asset.get("hwid", None) or asset.get("uuid")
        response = test_client.put(
            f"/api/v0/{asset_type}s/{asset_hwid}/", json=asset)

    create_asset('satellite', simple_sat)
    create_asset('groundstation', simple_gs)
    create_asset('task-stack', simple_task_stack)
    create_asset('passe', simple_pass)

    response = test_client.put(
        f'/api/v0/passes/{simple_pass["uuid"]}/task-runs/{some_uuid}/',
        json=simple_task_run)
    assert response.status_code == 201, response.get_data()

    simple_file['work_id'] = some_uuid
    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(f'/api/v0/files/{some_hash}/', json=simple_file)
    assert response.status_code == 201, response.get_data()

    expected = simple_file.copy()
    formatter = dateformat.DateFormat(created)
    expected['created'] = formatter.format(settings.DATETIME_FORMAT)
    expected['version'] = 1

    search_query = simple_file.copy()
    search_query['range_start'] = search_query.pop('start')
    search_query['range_end'] = search_query['range_start']

    response = test_client.get(f'/api/v0/files/', query_string=search_query)
    assert response.status_code == 200, response.get_data()

    assert response.json == [expected]

    # Make sure changing some of the searches *DON'T* find it.
    simple_query_false = simple_file.copy()
    simple_query_false['work_id'] = uuid.uuid4()
    simple_query_false['range_start'] = simple_query_false.pop('start')
    response = test_client.get(f'/api/v0/files/', query_string=simple_query_false)
    assert response.status_code == 200, response.get_data()
    assert response.json == []

    # Check that querying the task_run gets it
    with patch('home.models.S3File.get_download_url') as obj:
        obj.return_value = 'aURLhere'
        response = test_client.get(f'/api/v0/passes/{simple_pass["uuid"]}/task-runs/{some_uuid}/')
    assert response.status_code == 200, response.get_data()
    expected = simple_task_run.copy()
    expected['pass'] = simple_pass['uuid']
    expected['uuid'] = some_uuid
    expected['stdout'] = simple_file['cid']
    expected['stderr'] = None

    assert response.json == expected


@pytest.mark.django_db
def test_version_increment(test_client, simple_file, some_hash, another_hash):
    created = timezone.now()
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(f'/api/v0/files/{some_hash}/', json=simple_file)
    assert response.status_code == 201, response.get_data()
    result1 = response.json

    simple_file['cid'] = another_hash
    with patch('django.utils.timezone.now', return_value=created):
        response = test_client.put(f'/api/v0/files/{another_hash}/', json=simple_file)
    assert response.status_code == 201, response.get_data()
    result2 = response.json

    assert result1.pop('version') == 1
    assert result2.pop('version') == 2

    assert result1.pop('cid') == some_hash
    assert result2.pop('cid') == another_hash
    assert result1 == result2
