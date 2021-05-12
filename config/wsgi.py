"""
WSGI config for my_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# This allows easy placement of apps within the interior
# missioncontrol directory.
app_path = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)
sys.path.append(os.path.join(app_path, "missioncontrol"))

# We defer to a DJANGO_SETTINGS_MODULE already in the environment. This breaks
# if running multiple sites in the same mod_wsgi process. To fix this, use
# mod_wsgi daemon mode with each site in its own daemon process, or use
# os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
application = get_wsgi_application()

# Can't import this until after path is altered
from api import app as api


class FullPathDispatcher(DispatcherMiddleware):
    """
    Like DispatcherMiddleware, but passes the full path to the application
    (e.g. /api/v0/ui)
    """

    def __call__(self, environ, start_response):
        script = environ.get("PATH_INFO", "")
        path_info = ""
        while "/" in script:
            if script in self.mounts:
                app = self.mounts[script]
                break
            script, last_item = script.rsplit("/", 1)
            path_info = "/%s%s" % (last_item, path_info)
        else:
            app = self.mounts.get(script, self.app)
        original_script_name = environ.get("SCRIPT_NAME", "")
        environ["SCRIPT_NAME"] = original_script_name + script
        environ["PATH_INFO"] = script + path_info
        return app(environ, start_response)


application = FullPathDispatcher(application, {"/api": api})
