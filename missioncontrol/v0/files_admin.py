from datalake.models import What

def search_whats(limit=250):
    whats = What.objects.all()[:limit].values_list('what', flat=True)
    return whats, 200

def put_what(what):
    obj, created = What.objects.update_or_create(what=what)
    return what, 201 if created else 200

def delete_what(what):
    # what kind of cascade should happen here?
    # should we be hiding existing files from search?
    What.objects.filter(what=what).delete()
    return None, 204
