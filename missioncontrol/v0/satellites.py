from home.models import Satellite


def search(limit=100):
    return [sat.to_dict() for sat
            in Satellite.objects.all().order_by('hwid')[:limit]]


def get_hwid(hwid):
    return Satellite.objects.get(hwid=hwid).to_dict()


def patch(hwid, satellite):
    satellite["hwid"] = hwid
    sat = Satellite.objects.get(hwid=hwid)
    for key, value in satellite.items():
        setattr(sat, key, value)
    sat.save()
    return sat.to_dict()


def put(hwid, satellite):
    satellite["hwid"] = hwid
    m = Satellite(**satellite).to_dict()
    sat, _created = Satellite.objects.update_or_create(
        defaults=m, hwid=hwid
    )
    status_code = 201 if _created else 200
    return sat.to_dict(), status_code


def delete(hwid):
    sat = Satellite.objects.get(hwid=hwid)
    sat.delete()
    return None, 204
