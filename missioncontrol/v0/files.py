import requests

from connexion.exceptions import ProblemException
from django.conf import settings
from django.db.models import Q

from home.models import S3File

def search(**kwargs):
    # remove some unused ones
    kwargs.pop('token_info', None)
    kwargs.pop('user', None)

    start = kwargs.pop('range_start', None)
    # Some data
    args = []
    if start:
        args.append(Q(end__gte=start) | (Q(end__isnull=True) & Q(start__gte=start)))
    end = kwargs.pop('range_end', None)
    if end:
        kwargs['start__lte'] = end
    results = S3File.objects.filter(*args, **kwargs)
    return [x.to_dict() for x in results]


def get_data(cid):
    obj = S3File.objects.get(cid=cid)
    url = obj.get_download_url()
    headers = {'Location': url}
    return '', 302, headers

def get(cid):
    obj = S3File.objects.get(cid=cid)
    retval = obj.to_dict()
    return retval

def put(cid, file_body):
    body_cid = file_body.pop('cid', None)
    if body_cid is not None and cid != body_cid:
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='cid in url does not match body',
        )
    obj, created = S3File.objects.update_or_create(cid=cid, defaults=file_body)
    retval = obj.to_dict()
    return retval, 201 if created else 200

def get_post_data_fields(cid):
    if S3File.objects.filter(cid=cid).exists():
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='This cid already exists in metadata',
        )
    return S3File.get_post_data_fields(cid=cid)
