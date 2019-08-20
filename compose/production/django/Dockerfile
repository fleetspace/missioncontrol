FROM node:8 AS frontend


WORKDIR /app
COPY frontend /app


ENV NODE_PATH=/app/node_modules
ENV PATH=$PATH:/app/node_modules/.bin

ARG NODE_ENV

RUN yarn
RUN yarn build


FROM ubuntu:18.04

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install --yes python3 python3-pip
RUN pip3 install pipenv
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN addgroup --system django \
  && adduser --system --ingroup django django

WORKDIR /app
RUN chown -R django /app
USER django

# Do this before the copy so the python requirements can be
# cached
# TODO Do this with yarn as well
COPY --chown=django:django ./Pipfile* /app/
RUN pipenv install --deploy

# Load ephemeris as this is slow - and put it before app copy as files change more often
RUN pipenv run python -c 'from skyfield.api import Loader; load = Loader("app/"); load("de405.bsp"); load.timescale()'

COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
COPY --chown=django:django ./compose/production/django/start /start

COPY --chown=django:django . /app
COPY --from=frontend --chown=django:django /app/build /app/frontend/build

ARG DJANGO_SETTINGS_MODULE
RUN pipenv run python /app/manage.py collectstatic --noinput --settings=${DJANGO_SETTINGS_MODULE}

ENTRYPOINT ["/entrypoint"]
