import requests

from connexion.exceptions import ProblemException
from django.conf import settings
from django.db.models import Q

from datalake.models import DatalakeFile
from v0.time import utc


def search_by_cid(cid, limit=100):
    files = DatalakeFile.objects.filter(cid=cid)

    results = files.all()[:limit]
    return [x.to_dict() for x in results]


def search_work_id(work_id, what=None, where=None, limit=100):
    files = DatalakeFile.objects.filter(work_id=work_id)
    if what is not None:
        files = files.filter(what=what)

    if where is not None:
        files = files.filter(where=where)

    results = files.all()[:limit]
    return [x.to_dict() for x in results]


def search(what, where=None, range_start=None, range_end=None,
           range_inclusive="both", limit=100, order_by='-start'):

    files = DatalakeFile.objects.filter(what=what)

    if where is not None:
        files = files.filter(where=where)

    # filter the start of the range
    if range_start is not None:
        range_start = utc(range_start)
        if range_inclusive in ['end', 'neither']:
            files = files.filter(start__gte=range_start)
        else:
            # can overlap if window, else instant must be >= range_start
            files = files.filter(
                Q(end__gte=range_start) |
                (Q(start__gte=range_start) & Q(end=None))
            )

    # filter the end of the range
    if range_end is not None:
        range_end = utc(range_end)
        if range_inclusive in ['start', 'neither']:
            # can overlap if window, else instant must be < range_end
            files = files.filter(
                Q(end__lte=range_end) |
                (Q(start__lte=range_end) & Q(end=None))
            )
        else:
            files = files.filter(start__lte=range_end)

    results = files.all().order_by(order_by)[:limit]
    return [x.to_dict() for x in results]


def get_latest(what, where):
    files = DatalakeFile.objects.filter(what=what, where=where)
    result = files.latest()
    return result.to_dict()


def get_raw(cid):
    obj = DatalakeFile.objects.filter(cid=cid).first()
    url = obj.get_download_url()
    headers = {'Location': url}
    return '', 302, headers


def get_data(uuid):
    obj = DatalakeFile.objects.get(uuid=uuid)
    url = obj.get_download_url()
    headers = {'Location': url}
    return '', 302, headers


def get(uuid):
    obj = DatalakeFile.objects.get(uuid=uuid)
    retval = obj.to_dict()
    return retval


def put(uuid, file_meta):
    file_meta["uuid"] = uuid
    obj, created = DatalakeFile.objects.update_or_create(
        uuid=uuid, defaults=file_meta
    )
    retval = obj.to_dict()
    return retval, 201 if created else 200


def presign_upload(file_meta):
    cid = file_meta["cid"]
    if DatalakeFile.objects.filter(cid=cid).exists():
        raise ProblemException(
            status=202,
            title='Accepted',
            detail='File already exists in datalake, no upload is required',
        )
    return DatalakeFile.get_post_data_fields(**file_meta)
