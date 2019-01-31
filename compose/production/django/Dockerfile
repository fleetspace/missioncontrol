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

COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
COPY --chown=django:django ./compose/production/django/start /start

COPY --chown=django:django . /app


ENTRYPOINT ["/entrypoint"]
