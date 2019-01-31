#!/usr/bin/env python3

import os
import connexion

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from flask.json import JSONEncoder
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings.dev")
apps.populate(settings.INSTALLED_APPS)


def object_does_not_exist(exception):
    problem = connexion.problem(404, "Object Does Not Exist", str(exception))
    return connexion.FlaskApi.get_response(problem)


def validation_error(exception):
    problem = connexion.problem(400, "Validation Error", str(exception))
    return connexion.FlaskApi.get_response(problem)



class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                return obj.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


def create_app():
    app = connexion.FlaskApp(__name__, specification_dir='openapi/', arguments={})
    flask_app = app.app
    flask_app.json_encoder = CustomJSONEncoder
    app.add_api('openapi.yaml', strict_validation=True)
    app.add_error_handler(ObjectDoesNotExist, object_does_not_exist)
    app.add_error_handler(ValidationError, validation_error)
    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=settings.DEBUG)
