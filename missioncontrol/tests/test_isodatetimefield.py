from datetime import datetime

import pytest
from pytz import UTC
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test.utils import isolate_apps

from home.models import ISODateTimeField


@isolate_apps("home")
def test_isodatetimefield():
    class TestModel(models.Model):
        class Meta:
            app_label = "home"

        datetime = ISODateTimeField()

    naive = datetime(2018, 2, 3, 4, 5, 6, 7)
    utc = datetime(2018, 2, 3, 4, 5, 6, 7, tzinfo=UTC)

    expected = "2018-02-03T04:05:06.000007Z"

    model = TestModel()
    field = model._meta.get_field("datetime")

    model.datetime = naive
    with pytest.raises(ValueError) as exc:
        field.value_to_string(model)
    assert "Naive timezone was passed in" in str(exc.value)

    model.datetime = utc
    assert field.value_to_string(model) == "2018-02-03T04:05:06.000007Z"

    with pytest.raises(ValidationError):
        field.to_python("test")

    assert field.to_python(expected) == utc
    # No timezone should raise an error
    with pytest.raises(ValidationError):
        field.to_python(naive.isoformat())
