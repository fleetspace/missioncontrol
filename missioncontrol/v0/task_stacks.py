
from connexion.exceptions import ProblemException
from home.models import TaskStack


def get_task_stack(uuid):
    return  TaskStack.objects.get(uuid=uuid).to_dict()


def search(environment=None, name=None, limit=100):

    qs = TaskStack.active

    if environment is not None:
        qs = qs.filter(environment__icontains=environment)

    if name is not None:
        qs = qs.filter(name__icontains=name)

    return [ts.to_dict() for ts in qs.all()[:limit]]


def put(uuid, task_stack):
    task_stack["uuid"] = uuid
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
    return ts, 201
