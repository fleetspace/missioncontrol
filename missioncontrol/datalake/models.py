import logging
import six

import json
import datetime
from itertools import chain
from uuid import uuid4

from connexion.exceptions import ProblemException
from datalake_common import Metadata, InvalidDatalakeMetadata
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django.db.models import Max
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone, dateformat
import boto3
from pytz import UTC

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@receiver(pre_save)
def pre_save_handler(sender, instance, *args, **kwargs):
    # always validate local models before saving
    if sender in apps.all_models['datalake'].values():
        instance.full_clean()


class DatalakeJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types, and
    UUIDs.
    Based on DjangoJSONEncoder but uses ISO8601 with microsecond precision
    instead of ECMA-262
    """
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat('T', timespec='microseconds')
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if is_aware(o):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            return r
        elif isinstance(o, datetime.timedelta):
            return duration_iso_string(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID, Promise)):
            return str(o)
        else:
            return super().default(o)


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
            if f.name == 'id':
                continue

            if f.name == '_related_to':
                continue

            if f.name == 'uuid':
                data[f.name] = str(f.value_from_object(self))
                continue

            data[f.name] = f.value_from_object(self)
        return data


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
        return ''

    def to_python(self, value):
        result = super().to_python(value)
        if result:
            if result.tzinfo is None:
                raise ValidationError("Timezone must be specified")
            if result.tzinfo != UTC:
                result = result.astimezone(tz=UTC)
        return result


class What(models.Model, Serializable):
    what = models.CharField(unique=True, max_length=128)

    def __repr__(self):
        return self.what

    def __str__(self):
        return self.__repr__()


class RelatedFile(models.Model):
    work_id = models.CharField(max_length=256)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return self.work_id

    @classmethod
    def from_datalake_file(cls, dlfile):
        try:
            model, uuid = dlfile.work_id.split(".")
            if model.startswith("mc-"):
                model = model[len("mc-"):]
            else:
                return None
            ct = ContentType(app_label="home", model=model)
            try:
                obj = ct.get_object_for_this_type(uuid=uuid)
                rel = cls(content_object=obj, work_id=dlfile.work_id)
                rel.save()
                return rel
            except ObjectDoesNotExist:
                if not settings.DATALAKE_STRICT_WORK_ID:
                    return

                raise ProblemException(
                    status=400,
                    title='ValidationError',
                    detail=('work_id is in the missioncontrol namespace, '
                            'but the object with the given id does not exist.'),
                    ext={
                        "work_id": dlfile.work_id,
                        "model": model,
                        "id": uuid
                    }
                )
        except (IndexError, AttributeError) as e:
            pass
            

class DatalakeFile(models.Model, Serializable):
    uuid = models.UUIDField(default=uuid4, unique=True)
    cid = models.CharField(max_length=33)
    what = models.TextField()
    where = models.TextField()
    path = models.TextField(null=True, blank=True)
    start = ISODateTimeField(
        help_text='The time of the first event in the file. '
                  'If instantaneous, set this and leave end as null',
        default=timezone.now)
    end = ISODateTimeField(
        help_text='The time of the last event in the file. '
                  'Can be blank if instantaneous file.',
        null=True, blank=True)
    created = ISODateTimeField(auto_now_add=True)
    work_id = models.TextField(null=True, blank=True)
    version = models.IntegerField(choices=((1, 1),))  # FIXME
    _related_to = models.ForeignKey(RelatedFile, on_delete=models.SET_NULL,
                                    null=True, editable=False, blank=True)

    class Meta:
        ordering = ('-start', 'created')
        get_latest_by = ('start', 'created')

    @property
    def related(self):
        if self._related_to is None:
            self._related_to = RelatedFile.from_datalake_file(self)
        if self._related_to is not None:
            return self._related_to.content_object

    def clean(self):
        try:
            Metadata(self.to_dict())
        except InvalidDatalakeMetadata as e:
            raise ProblemException(
                status=400,
                title='InvalidDatalakeMetadata',
                detail=e.args[0],
                ext={"invalid_object": self.to_dict()}
            )
        if (
            settings.DATALAKE_STRICT_WHATS and
            not What.objects.filter(what=self.what).exists()
        ):
            raise ProblemException(
                status=400,
                title='ValidationError',
                detail=f'Unknown what: {self.what}',
                ext={"invalid_object": self.to_dict()}
            )
        if self._related_to is None:
            self._related_to = RelatedFile.from_datalake_file(self)

    # s3://bucket/some_path
    @property
    def prefix(self):
        path = settings.FILE_STORAGE_PATH
        if path.startswith('s3://'):
            return '/'.join(path.split('/')[3:])
        # TODO
        raise NotImplementedError("Not yet implemented non s3 paths")

    @property
    def bucket(self):
        path = settings.FILE_STORAGE_PATH
        if path.startswith('s3://'):
            return path.split('/')[2]
        # TODO
        raise NotImplementedError("Not yet implemented non s3 paths")

    @property
    def key(self):
        return f'{self.prefix}{self.cid}/data'

    @property
    def metadata_key(self):
        return f'{self.prefix}{self.cid}/metadata/{self.uuid}'

    def get_download_url(self):
        s3 = boto3.client('s3')
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': self.bucket,
                'Key': self.key,
            }
        )
        return url

    @classmethod
    def get_post_data_fields(cls, **kwargs):
        # Create the object but don't save it
        obj = cls(**kwargs)
        s3 = boto3.client('s3')
        post = s3.generate_presigned_post(
            Bucket=obj.bucket,
            Key=obj.key,
            Fields={"Content-Encoding": "gzip"},
            Conditions=[
                ["eq", "$Content-Encoding", "gzip"],
            ]
        )
        return post


@receiver(post_save, sender=DatalakeFile)
def save_metadata_to_s3(sender, instance, *args, **kwargs):
    # store metadata for recovery
    s3 = boto3.client('s3')
    s3.put_object(
        Body=json.dumps(instance.to_dict(), cls=DatalakeJSONEncoder, sort_keys=True),
        Bucket=instance.bucket,
        Key=instance.metadata_key,
        ContentType="application/json"
    )
    return instance
