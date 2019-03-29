import json
import datetime

from base64 import b64encode, b64decode
from collections import namedtuple
from connexion.exceptions import ProblemException
from itertools import product
from skyfield.api import Loader, Topos, EarthSatellite
from home.leaf import LeafPassFile
from flask import request, Response

from home.models import GroundStation, Satellite, Pass, TaskStack
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from v0.accesses import Access
from v0.track import get_track_file, DEF_STEP_S
from v0.time import utc


TWO_DAYS_S = 2 * 24 * 60 * 60


def search(limit=100, range_start=None, range_end=None, range_inclusive='both',
           satellites=None, groundstations=None, order_by='start_time',
           show_stale=False):

    if satellites is None:
        dj_sats = Satellite.objects.all()
    else:
        dj_sats = Satellite.objects.filter(hwid__in=satellites)

    if groundstations is None:
        dj_gss = GroundStation.objects.all()
    else:
        dj_gss = GroundStation.objects.filter(hwid__in=groundstations)

    passes = Pass.objects.filter(
        satellite__in=dj_sats, groundstation__in=dj_gss,
    )

    # set the default time range, if no range is specified
    if range_start is None and range_end is None:
        range_start = utc("now")
        range_end = range_start + datetime.timedelta(days=2)

    # filter the start of the range
    if range_start is not None:
        range_start = utc(range_start)
        if range_inclusive in ['end', 'neither']:
            passes = passes.filter(start_time__gte=range_start)
        else:
            passes = passes.filter(end_time__gte=range_start)

    # filter the end of the range
    if range_end is not None:
        range_end = utc(range_end)
        if range_inclusive in ['start', 'neither']:
            passes = passes.filter(end_time__lte=range_end)
        else:
            passes = passes.filter(start_time__lte=range_end)

    if not show_stale:
        passes = passes.exclude(Q(scheduled_on_gs=False) &
                                Q(scheduled_on_sat=False) &
                                Q(is_desired=False))

    passes = passes.all().order_by(order_by)[:limit]

    return [p.to_dict() for p in passes]


def get_pass(uuid):
    return Pass.objects.get(uuid=uuid).to_dict()


def delete(uuid):
    pass_obj = Pass.objects.get(uuid=uuid)
    problems = []
    if pass_obj.scheduled_on_gs:
        problems += [
            'pass is scheduled on the groundstation ({hwid})'.format(
                hwid=pass_obj.groundstation.hwid)
        ]

    if pass_obj.scheduled_on_sat:
        problems += [
            'pass is scheduled on the satellite ({hwid})'.format(
                hwid=pass_obj.satellite.hwid)
        ]

    if problems:
        raise ProblemException(
            status=400,
            title='Cannot delete pass that is scheduled',
            detail=problems
        )

    pass_obj.delete()
    return None, 204


def patch(uuid, _pass):
    _pass["uuid"] = uuid
    pass_obj = Pass.objects.get(uuid=uuid)
    for key, value in _pass.items():
        setattr(pass_obj, key, value)
    pass_obj.save()
    return pass_obj.to_dict()


def get_track(uuid, step=DEF_STEP_S):
    _pass = Pass.objects.get(uuid=uuid)
    access = _pass.access().clip(_pass.start_time, _pass.end_time)
    return get_track_file(access, step=step)


def recalculate(uuid):
    _pass = get_pass(uuid)
    valid = _pass.recompute()
    status = 200 if valid else 400
    return None, status


def put(uuid, _pass):
    _pass["uuid"] = uuid

    try:
        access_id = _pass["access_id"]
        access = Access.from_id(access_id)
        sat_obj = access.satellite
        gs_obj = access.groundstation
        _pass.setdefault("start_time", utc(access.start_time))
        _pass.setdefault("end_time", utc(access.end_time))
    except KeyError:
        # user provided all required fields instead of access id
        sat_hwid = _pass["satellite"]
        sat_obj = Satellite.objects.get(hwid=sat_hwid)
        gs_hwid = _pass["groundstation"]
        gs_obj = GroundStation.objects.get(hwid=gs_hwid)
        try:
            access_id = Access.from_overlap(
                _pass["start_time"], _pass["end_time"],
                sat_obj, gs_obj
            ).access_id
        except ObjectDoesNotExist:
            _pass["is_valid"] = False

    # FIXME we are creating an new Pass object to get all of the defaults
    # but we don't want to create the foreign keys yet, so we pop them
    # out, create the object, then add them back in...
    _pass.pop("satellite", None)
    _pass.pop("groundstation", None)
    task_stack_uuid = _pass.pop("task_stack", None)

    if task_stack_uuid:
        task_stack = TaskStack.objects.get(uuid=task_stack_uuid)
    else:
        task_stack = None

    po = Pass(**_pass)
    m = po.to_dict()

    m["satellite"] = sat_obj
    m["groundstation"] = gs_obj
    m["task_stack"] = task_stack
    m["source_tle"] = m["satellite"].tle

    _pass, _created = Pass.objects.update_or_create(
        defaults=m, uuid=uuid
    )
    status_code = 201 if _created else 200
    return _pass.to_dict(), status_code

def get_attributes(uuid):
    _pass = Pass.objects.get(uuid=uuid)
    return _pass.attributes or {}

def patch_attributes(uuid, attributes):
    _pass = Pass.objects.get(uuid=uuid)
    if _pass.attributes:
        _pass.attributes.update(attributes)
    else:
        _pass.attributes = attributes
    _pass.save()
    return _pass.attributes or {}

def put_attributes(uuid, attributes):
    _pass = Pass.objects.get(uuid=uuid)
    _pass.attributes = attributes
    _pass.save()
    return _pass.attributes or {}
