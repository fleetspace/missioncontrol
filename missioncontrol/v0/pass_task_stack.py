from uuid import uuid4
from connexion.exceptions import ProblemException
from home.models import TaskStack, Pass


def get_task_stack(uuid):
    return TaskStack.objects.get(pass__uuid=uuid).to_dict()


def put(uuid, task_stack):
    ts_uuid = task_stack.setdefault("uuid", str(uuid4()))
    ts_obj, _created = TaskStack.objects.get_or_create(uuid=ts_uuid,
                                                       defaults=task_stack)

    ts = ts_obj.to_dict()
    if not _created:
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='The provided task-stack already exists',
            ext={"task_stack": ts}
        )

    _pass = Pass.objects.get(uuid=uuid)
    _pass.task_stack = ts_obj
    _pass.save()

    return ts, 201
