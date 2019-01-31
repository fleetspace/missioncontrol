from uuid import uuid4
from connexion.exceptions import ProblemException
from home.models import TaskStack, Satellite


def get_task_stack(hwid):
    return  Satellite.objects.get(hwid=hwid).task_stack.to_dict()


def put(hwid, task_stack):
    uuid = task_stack.setdefault("uuid", str(uuid4()))
    ts_obj, _created = TaskStack.objects.get_or_create(uuid=uuid,
                                                       defaults=task_stack)

    ts = ts_obj.to_dict()
    if not _created:
        raise ProblemException(
            status=409,
            title='Conflict',
            detail='The provided task-stack already exists',
            ext={"task_stack": ts}
        )

    sat = Satellite.objects.get(hwid=hwid)
    sat.task_stack = ts_obj
    sat.save()

    return ts, 201
