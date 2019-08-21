from home.models import GroundStation


def search(limit=100):
    return [gs.to_dict() for gs in GroundStation.objects.all().order_by("hwid")[:limit]]


def get_hwid(hwid):
    return GroundStation.objects.get(hwid=hwid).to_dict()


def sanitize(groundstation):
    # XXX move to custom field on model
    if "latitude" in groundstation:
        groundstation["latitude"] = str(round(groundstation["latitude"], 6))
    if "longitude" in groundstation:
        groundstation["longitude"] = str(round(groundstation["longitude"], 6))
    return groundstation


def patch(hwid, groundstation):
    groundstation["hwid"] = hwid
    groundstation = sanitize(groundstation)
    gs = GroundStation.objects.get(hwid=hwid)
    for key, value in groundstation.items():
        setattr(gs, key, value)
    gs.save()
    return gs.to_dict()


def put(hwid, groundstation):
    groundstation["hwid"] = hwid
    groundstation = sanitize(groundstation)
    m = GroundStation(**groundstation).to_dict()
    gs, _created = GroundStation.objects.update_or_create(defaults=m, hwid=hwid)
    status_code = 201 if _created else 200
    return gs.to_dict(), status_code


def delete(hwid):
    gs = GroundStation.objects.get(hwid=hwid)
    gs.delete()
    return None, 204
