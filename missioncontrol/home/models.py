import logging
import six

from datetime import timedelta
from itertools import chain
from uuid import uuid4

from connexion.exceptions import ProblemException
from django.apps import apps
from django.contrib.postgres.fields import JSONField
from django.conf import settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.postgres.fields import JSONField, HStoreField
from django.db import models, transaction
from django import forms
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone, dateformat
from pytz import UTC
from skyfield.api import Topos, EarthSatellite

GS_RESET_TIME_S = 90  # FIXME this is a wag

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


LOCK_MODES = (
    "ACCESS SHARE",
    "ROW SHARE",
    "ROW EXCLUSIVE",
    "SHARE UPDATE EXCLUSIVE",
    "SHARE",
    "SHARE ROW EXCLUSIVE",
    "EXCLUSIVE",
    "ACCESS EXCLUSIVE",
)


def require_lock(lock):
    """
    Decorator for PostgreSQL's table-level lock functionality

    Example:
        @transaction.commit_on_success
        @require_lock(MyModel, 'ACCESS EXCLUSIVE')
        def save(self, *args, **kwargs):
            super().save(*args, **kwargs)

    PostgreSQL's LOCK Documentation:
    http://www.postgresql.org/docs/8.3/interactive/sql-lock.html
    """

    def require_lock_decorator(view_func):
        def wrapper(model, *args, **kwargs):
            if lock not in LOCK_MODES:
                raise ValueError("%s is not a PostgreSQL supported lock mode.")
            from django.db import connection

            cursor = connection.cursor()
            cursor.execute("LOCK TABLE %s IN %s MODE" % (model._meta.db_table, lock))
            return view_func(model, *args, **kwargs)

        return wrapper

    return require_lock_decorator


@receiver(pre_save)
def pre_save_handler(sender, instance, *args, **kwargs):
    # always validate local models before saving
    if sender in apps.all_models["home"].values():
        instance.full_clean()


class ISODateTimeField(models.DateTimeField):
    """
    We *REALLY* want stuff to be UTC here

    Check it and convert if nessesary at all steps
    """

    def value_to_string(self, obj):
        val = self.value_from_object(obj)
        if val:
            if val.tzinfo is None:
                raise ValueError("Naive timezone was passed in")
            if val.tzinfo != UTC:
                val = val.astimezone(tz=UTC)
            formatter = dateformat.DateFormat(val)
            return formatter.format(settings.DATETIME_FORMAT)
        return ""

    def to_python(self, value):
        result = super().to_python(value)
        if result:
            if result.tzinfo is None:
                raise ValidationError("Timezone must be specified")
            if result.tzinfo != UTC:
                result = result.astimezone(tz=UTC)
        return result


class Serializable(object):
    """ A mixin for turning the django record into an object that can be
        serialized.
    """

    def to_dict(self):
        """ Adapted from django.forms.models.model_to_dict()
            https://docs.djangoproject.com/en/2.1/_modules/django/forms/models/

            The main difference is that this includes fields that are not editable.
        """
        opts = self._meta
        data = {}
        for f in chain(opts.concrete_fields, opts.private_fields, opts.many_to_many):
            if f.name is "id":
                continue
            data[f.name] = f.value_from_object(self)
        return data


class ActiveTaskStacks(models.Manager):
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(pinned=True)


class TaskStack(models.Model, Serializable):
    """ A TaskStack is an immutable list of tasks, and an environment
        to run them in.
    """

    name = models.CharField(max_length=100, blank=True)
    environment = models.CharField(max_length=100, blank=True)
    uuid = models.UUIDField(default=uuid4, unique=True)
    tasks = JSONField(default=list)
    created = ISODateTimeField(auto_now_add=True)
    pinned = models.BooleanField(default=False)

    objects = models.Manager()
    active = ActiveTaskStacks()

    def clean(self):
        # TODO compare against known environments
        # TODO compare against known scripts
        if not isinstance(self.tasks, list):
            raise ProblemException(
                status=400,
                title="ValidationError",
                detail="tasks must be a list of tasks to run",
                ext=self.tasks,
            )
        if any([not isinstance(task, six.string_types) for task in self.tasks]):
            raise ProblemException(
                status=400,
                title="ValidationError",
                detail="tasks must be strings",
                ext=self.tasks,
            )

    def __repr__(self):
        return "<TaskStack: {uuid} - {name}>".format(**self.__dict__)

    def __str__(self):
        return self.__repr__()


class TLEField(models.Field):
    sep = "|"

    @staticmethod
    def verify_checksum(tle):
        for line in tle:
            checksum = (
                sum([int(x) for x in line[:-1].replace("-", "1") if x in "0123456789"])
                % 10
            )
            if f"{checksum}" != line[-1]:
                raise ValidationError(f"Checksum invalid: {checksum} != {line[-1]}")

    @classmethod
    def _make_tle(cls, tle_str):
        # TODO better validation
        tle = tle_str.split(cls.sep)
        if len(tle) != 2:
            tle = tle_str.splitlines()
            if len(tle) != 2:
                raise ValidationError("TLE must have two elements!")

        cls.verify_checksum(tle)

        return tle

    def get_internal_type(self):
        return "TextField"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._make_tle(value)

    def to_python(self, value):
        if isinstance(value, list):
            return value

        if value is None:
            return value

        return self._make_tle(value)

    def get_prep_value(self, value):
        if value is None:
            return None

        if len(value) != 2:
            raise ValidationError("TLE must have two elements!")
        if self.sep in value[0] or self.sep in value[1]:
            raise ValidationError("TLE cannot contain '{sep}'".format(sep=self.sep))
        return self.sep.join(value)

    def formfield(self, **kwargs):
        defaults = {
            "widget": forms.Textarea(
                attrs={"rows": 4, "cols": 69, "style": "font-family: monospace"}
            )
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if len(value) != 2:
            raise ValidationError("TLE must have two lines only")
        self.verify_checksum(value)


class Satellite(models.Model, Serializable):
    hwid = models.CharField(unique=True, max_length=20)
    catid = models.CharField(blank=True, max_length=20)
    tle = TLEField(blank=True, null=True)
    logger_state = JSONField(blank=True, null=True)
    task_stack = models.ForeignKey(
        TaskStack, null=True, blank=True, on_delete=models.SET_NULL, to_field="uuid"
    )

    @property
    def tle1(self):
        return self.tle[0]

    @property
    def tle2(self):
        return self.tle[1]

    def __sub__(self, other):
        return self._vec - other._vec

    @property
    def _vec(self):
        if not self.tle:
            raise RuntimeError("Satellite TLE is undefined")
        return EarthSatellite(self.tle1, self.tle2, self.hwid)

    def __repr__(self):
        return "<Satellite: {hwid}>".format(**self.__dict__)

    def __str__(self):
        return self.__repr__()


class HorizonMaskField(models.Field):
    def get_internal_type(self):
        return "TextField"

    def _to_list(self, value):
        value = value.strip("[]")
        hmask = list(map(float, value.split(",")))
        if len(hmask) != 360:
            raise ValidationError("horizon_mask must have length=360")
        return hmask

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._to_list(value)

    def to_python(self, value):
        if isinstance(value, list):
            return value

        if value is None:
            return value

        return self._to_list(value)

    def get_prep_value(self, value):
        if type(value) is not list:
            raise ValidationError("horizon_mask must be a list")
        if len(value) != 360:
            raise ValidationError("horizon_mask must have length=360")
        return ",".join([str(round(l, 2)) for l in value])


class GroundStation(models.Model, Serializable):
    hwid = models.CharField(unique=True, max_length=30)
    latitude = models.FloatField()
    longitude = models.FloatField()
    elevation = models.FloatField(help_text="In meters")
    horizon_mask = HorizonMaskField(default=[5] * 360)
    passes_read_only = models.BooleanField(default=False)

    class Meta(object):
        verbose_name_plural = "Groundstations"

    @property
    def _vec(self):
        return Topos(
            latitude_degrees=float(self.latitude),
            longitude_degrees=float(self.longitude),
            elevation_m=float(self.elevation),
        )

    def observe(self, satellite):
        return satellite._vec - self._vec

    def __str__(self):
        return f"Ground Station: {self.hwid}"


class UpcomingPasses(models.Manager):
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(start_time__gt=now)


class CurrentPasses(models.Manager):
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(start_time_lte=now, end_time__gt=now)


class HistoricalPasses(models.Manager):
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(end_time__lte=now)

    class Meta:
        ordering = ("-start_time",)


class Pass(models.Model, Serializable):
    # TODO conflicts when passes overlap (or are within antenna reset time)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    access_id = models.CharField(max_length=100, blank=True)
    satellite = models.ForeignKey(Satellite, on_delete=models.PROTECT, to_field="hwid")
    # save the TLE that created this pass, in case the satellite TLE updates
    source_tle = TLEField(blank=True, null=True)
    groundstation = models.ForeignKey(
        GroundStation, on_delete=models.PROTECT, to_field="hwid"
    )
    start_time = ISODateTimeField()
    end_time = ISODateTimeField()
    scheduled_on_sat = models.BooleanField(default=False)
    scheduled_on_gs = models.BooleanField(default=False)
    is_desired = models.BooleanField(default=True)
    is_valid = models.BooleanField(default=True)
    external_id = models.TextField(
        help_text="3rd parties may reference this pass by a different name, save it here",
        default=None,
        null=True,
        blank=True,
    )
    task_stack = models.ForeignKey(
        TaskStack, null=True, blank=True, on_delete=models.SET_NULL, to_field="uuid"
    )
    attributes = HStoreField(null=True, blank=True)

    objects = models.Manager()
    upcoming = UpcomingPasses()
    current = CurrentPasses()
    historical = HistoricalPasses()

    class Meta(object):
        verbose_name_plural = "Passes"

    @transaction.atomic
    @require_lock("SHARE ROW EXCLUSIVE")
    def save(self, *args, **kwargs):
        # Make this locked, so only a single process can save a Pass at a time,
        # otherwise conflicting passes may be added.
        # (as the constraint cannot be added to the db directly)
        # Conflict check is done inside `Pass.clean` which is called via `pre_save_handler`
        super().save(*args, **kwargs)

    def clean(self):
        stale = not (self.is_desired or self.scheduled_on_sat or self.scheduled_on_gs)
        if stale:
            return

        gs_reset_time = timedelta(seconds=GS_RESET_TIME_S)
        overlap_range = (self.start_time - gs_reset_time, self.end_time)
        start_overlaps_qs = Q(start_time__range=overlap_range)
        end_overlaps_qs = Q(end_time__range=overlap_range)
        not_stale = (
            Q(scheduled_on_sat=True) | Q(scheduled_on_gs=True) | Q(is_desired=True)
        )
        same_sat = Q(satellite=self.satellite)
        same_gs = Q(groundstation=self.groundstation)
        different_id = ~Q(uuid=self.uuid)
        overlapping_pass_qs = Pass.objects.filter(
            (same_gs | same_sat)
            & different_id
            & not_stale
            & (start_overlaps_qs | end_overlaps_qs)
        )
        overlaps = overlapping_pass_qs.all()
        if overlaps:
            ext = {"conflicts": [p.to_dict() for p in overlaps]}
            raise ProblemException(
                status=409,
                title="Conflict",
                detail="The provided pass conflicts with one on the server",
                ext=ext,
            )

    def refresh_tle(self):
        self.source_tle = self.satellite.tle
        return self.source_tle

    def recompute(self):
        mid_time = self.start_time + ((self.end_time - self.start_time) / 2)
        try:
            access = Access.from_time(mid_time, self.satellite, self.groundstation)
        except ObjectDoesNotExist:
            self.is_valid = False
            return self.is_valid
        self.access_id = access.access_id
        self.start_time = access.start_time
        self.end_time = access.end_time
        self.source_tle = self.satellite.tle
        self.is_valid = True
        self.save()
        return self.is_valid

    @classmethod
    def from_access_id(cls, access_id):
        access = Access.from_id(access_id)
        return cls.from_access(access)

    @classmethod
    def from_access(cls, access):
        if access.groundstation.passes_read_only:
            raise ValidationError("Cannot add passes manually to this ground station")
        return cls(
            access_id=access.access_id,
            start_time=access.start_time,
            end_time=access.end_time,
            satellite=access.satellite,
            groundstation=access.groundstation,
            source_tle=access.satellite.tle,
        )

    @classmethod
    def from_times(cls, satellite, groundstation, start_time, end_time):
        return cls(
            start_time=start_time,
            end_time=end_time,
            satellite=satellite,
            groundstation=groundstation,
            source_tle=satellite.tle,
        )

    def access(self):
        return Access.from_id(self.access_id)

    def __str__(self):
        return f"Pass: {self.uuid} - {self.satellite} - {self.groundstation} - {self.start_time}"


class CachedAccess(models.Model):
    # we store computed accesses by bucket_hash, where the hash is
    # hash(tle1, tle2, lat, lng, el, horizon_mask) + bucket_start + bucket_end
    bucket_hash = models.CharField(max_length=100)
    bucket_index = models.IntegerField(default=0)
    satellite = models.ForeignKey(Satellite, on_delete=models.CASCADE, to_field="hwid")
    groundstation = models.ForeignKey(
        GroundStation, on_delete=models.CASCADE, to_field="hwid"
    )
    start_time = ISODateTimeField(blank=True, null=True)
    end_time = ISODateTimeField(blank=True, null=True)
    modified = ISODateTimeField(auto_now=True)
    max_alt = models.FloatField(blank=True, null=True)
    placeholder = models.BooleanField(default=False)

    class Meta:
        unique_together = ("bucket_hash", "bucket_index")

    @classmethod
    def invalidate_satellite(cls, satellite):
        cls.objects.filter(satellite=satellite).delete()

    @classmethod
    def invalidate_groundstation(cls, groundstation):
        cls.objects.filter(groundstation=groundstation).delete()

    def to_dict(self):
        return {
            "satellite": self.satellite.hwid,
            "groundstation": self.groundstation.hwid,
            "start_time": iso(self.start_time),
            "end_time": iso(self.end_time),
            "max_alt": self.max_alt,
        }

    def to_access(self, base_url=""):
        return Access(
            self.start_time,
            self.end_time,
            self.satellite,
            self.groundstation,
            self.max_alt,
            base_url=base_url,
        )


from v0.accesses import Access
