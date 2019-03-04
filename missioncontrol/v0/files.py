import requests

from django.conf import settings
from django.db.models import Q

from home.models import S3File, TaskRun

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
    retval['post_url_fields'] = obj.get_upload_url()
    return retval

def put(cid, file_body):
    task_run_uuid = file_body.pop('task_run', None)
    task_run = None
    if task_run_uuid:
        # See if it exists
        task_run = TaskRun.objects.get(uuid=task_run_uuid)
        file_body['task_run'] = task_run

    obj, created = S3File.objects.update_or_create(cid=cid, defaults=file_body)

    retval = obj.to_dict()
    retval['post_url_fields'] = obj.get_upload_url()
    return retval, 201 if created else 200