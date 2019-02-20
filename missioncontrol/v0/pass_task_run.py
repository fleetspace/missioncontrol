from connexion.exceptions import ProblemException

from home.models import TaskRun, Pass, TaskStack


def search(pass_uuid=None):
    return [x.to_dict() for x in TaskRun.objects.all()]

def get(pass_uuid=None, uuid=None):
    result = TaskRun.objects.get(uuid=uuid, task_pass=pass_uuid)
    return result.to_dict()

def put(pass_uuid=None, uuid=None, task_run=None):
    _pass = Pass.objects.get(uuid=pass_uuid)
    task_stack = TaskStack.objects.get(uuid=task_run['task_stack'])


    pass_uuid_body = task_run.pop('pass', None)
    if pass_uuid_body and pass_uuid_body != pass_uuid:
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='pass in url does not match body',
        )

    task_run["uuid"] = uuid
    task_run["task_pass"] = _pass
    task_run["task_stack"] = task_stack

    tr_obj, created = TaskRun.objects.get_or_create(uuid=uuid, defaults=task_run)

    result = tr_obj.to_dict()
    if not created:
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='The provided task run already exists',
            ext={'task_run': result}
        )
    return result, 201
