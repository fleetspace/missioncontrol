import uuid
import json
from unittest.mock import patch, call

import pytest
from django.conf import settings
from django.utils import timezone, dateformat


@pytest.mark.django_db
def test_put_what(test_client, simple_file):
    what = simple_file["what"]
    response = test_client.put(
        f'/api/v0/datalake/admin/whats/{what}/'
    )

@pytest.mark.django_db
def test_list_whats(test_client):
    whats = ["a", "b", "c"]
    for what in whats:
        response = test_client.put(
            f'/api/v0/datalake/admin/whats/{what}/'
        )
        assert response.status_code == 201, response.get_body()
    response = test_client.get(
        '/api/v0/datalake/admin/whats/'
    )
    assert response.status_code == 200, response.get_body()
    assert response.json == whats

@pytest.mark.django_db
def test_delete_what(test_client):
    whats = ["a", "b", "c"]
    for what in whats:
        response = test_client.put(
            f'/api/v0/datalake/admin/whats/{what}/'
        )
        assert response.status_code == 201, response.get_body()

    del_what = whats.pop()
    response = test_client.delete(
        f'/api/v0/datalake/admin/whats/{del_what}/'
    )
    assert response.status_code == 204

    response = test_client.get(
        '/api/v0/datalake/admin/whats/'
    )
    assert response.status_code == 200, response.get_body()
    assert response.json == whats

