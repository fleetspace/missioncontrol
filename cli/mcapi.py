import argparse
import json
import os
from urllib.parse import urljoin

import requests


class MCAPI(object):
    def __init__(self, mc_base, jwt=None):
        self.mc_base = mc_base
        self.s = requests.session()
        self.jwt = None

    def get(self, path, *args, **kwargs):
        r = self.s.get(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r

    def getj(self, path, *args, **kwargs):
        r = self.get(path, *args, **kwargs)
        return r.json()

    def put(self, path, *args, **kwargs):
        r = self.s.put(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r

    def putj(self, path, *args, **kwargs):
        r = self.s.put(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r.json()

    def patch(self, path, *args, **kwargs):
        r = self.s.patch(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r

    def patchj(self, path, *args, **kwargs):
        r = self.s.patch(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r.json()

    def delete(self, path, *args, **kwargs):
        r = self.s.delete(urljoin(self.mc_base, path), *args, **kwargs)
        r.raise_for_status()
        return r

    def get_passes(self, **kwargs):
        passes = self.getj("/api/v0/passes/", params=kwargs)
        return passes

    def get_accesses(self, **kwargs):
        accesses = self.getj("/api/v0/accesses/", params=kwargs)
        return accesses

    def put_pass(self, pass_id, **kwargs):
        """ requesting a pass signals intent that you'd like it to happen.
            If the pass already exists, then it will be marked is_desired
            If it does not exist, it will be created.
            A pass can be created from either an access_id, or a
              satellite, groundstation, start_time, and end_time.
            If you provide an access_id, you can override the start and end
              times by providing them as well.
        """
        return self.putj(f"/api/v0/passes/{pass_id}/", json=kwargs)

    def delete_pass(self, pass_id, **kwargs):
        return self.delete(f"/api/v0/passes/{pass_id}/", json=kwargs)

    def patch_pass(self, pass_id, **kwargs):
        return self.patchj(f"/api/v0/passes/{pass_id}/", json=kwargs)

    def get_pass_track(self, pass_id, fmt="json"):
        if fmt == "leaf":
            headers = {"accept": "application/vnd.leaf+text"}
            return self.get(
                "/api/v0/passes/{pass_id}/track/".format(pass_id=pass_id),
                headers=headers,
            ).text
        return self.getj("/api/v0/passes/{pass_id}/track/".format(pass_id=pass_id))

    def patch_pass_attributes(self, pass_id, attributes):
        return self.patchj(f"/api/v0/passes/{pass_id}/attributes/", json=attributes)

    def get_groundstations(self):
        return self.getj("/api/v0/groundstations/")

    def get_satellite(self, hwid):
        return self.getj(f"/api/v0/satellites/{hwid}")

    def get_satellites(self):
        return self.getj("/api/v0/satellites/")

    def patch_satellite(self, hwid, **kwargs):
        return self.patchj(f"/api/v0/satellites/{hwid}/", json=kwargs)

    def get_task_stacks(self, **kwargs):
        return self.getj("/api/v0/task-stacks/", params=kwargs)

    def put_task_stack(self, uuid, **kwargs):
        return self.putj(f"/api/v0/task-stacks/{uuid}/", json=kwargs)

    def login(self, username=None, password=None, jwt=None):
        if username is not None and jwt is not None:
            raise ValueError("Can't give both a username and a jwt")
        if username is not None:
            self.s.auth = (username, password)
            self.jwt = self.get("/api/v0/auth/jwt").text
            self.s.auth = None
        else:
            self.jwt = jwt

        self.s.headers.update({"Authorization": f"Bearer {self.jwt}"})
        # TODO save token to disk?


def add_parser_defaults(parser):
    parser.add_argument(
        "--mc-base",
        dest="mc_api",
        required="MC_BASE" not in os.environ,
        type=MCAPI,
        default=MCAPI(os.environ.get("MC_BASE")),
    )

    add_login_to_parser(parser)
    add_ssl_to_parser(parser)


def add_login_to_parser(parser):
    auth = parser.add_mutually_exclusive_group(
        required=(not os.environ.get("MC_USERNAME") and not os.environ.get("MC_JWT"))
    )
    auth.add_argument(
        "--username", "-u", dest="username", default=os.environ.get("MC_USERNAME")
    )
    parser.add_argument(
        "--password", "-p", dest="password", default=os.environ.get("MC_PASSWORD")
    )
    auth.add_argument("--jwt", "-j", dest="jwt", default=os.environ.get("MC_JWT"))


def add_ssl_to_parser(parser):
    parser.add_argument("--ignore-ssl", action="store_true", default=False)


def get_parser():
    parser = argparse.ArgumentParser()
    add_parser_defaults(parser)
    return parser


def handle_default_args(args):
    if args.ignore_ssl:
        args.mc_api.s.verify = False

    if args.jwt:
        args.mc_api.login(jwt=args.jwt)
    else:
        args.mc_api.login(username=args.username, password=args.password)
