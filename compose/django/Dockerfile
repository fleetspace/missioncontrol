FROM node:8 AS frontend


WORKDIR /app
COPY frontend /app


ENV NODE_PATH=/app/node_modules
ENV PATH=$PATH:/app/node_modules/.bin

ARG NODE_ENV

RUN npm ci
RUN npm run build


FROM ubuntu:18.04

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install --yes python3 python3-pip libpq-dev
RUN pip3 install poetry
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN addgroup django \
  && adduser --ingroup django --disabled-password --gecos "" django

WORKDIR /app
RUN chown -R django /app
USER django

# Do this before the copy so the python requirements can be
# cached
COPY --chown=django:django ./pyproject.toml ./poetry.lock /app/
RUN poetry install

# Load ephemeris as this is slow - and put it before app copy as files change more often
RUN poetry run python -c 'from skyfield.api import Loader; load = Loader("app/"); load("de405.bsp")'
RUN poetry run python -c 'from skyfield.api import Loader; load = Loader("app/"); load.timescale(builtin=True)'

COPY --chown=django:django ./compose/django/entrypoint /entrypoint
COPY --chown=django:django ./compose/django/start /start

COPY --chown=django:django . /app
COPY --from=frontend --chown=django:django /app/build /app/frontend/build

ARG DJANGO_SETTINGS_MODULE
# As collectstatic requires the secret key to be set, use a temporary one
RUN env DJANGO_SECRET_KEY='collectstatic' poetry run python /app/manage.py collectstatic --noinput --settings=${DJANGO_SETTINGS_MODULE}

ENTRYPOINT ["/entrypoint"]
