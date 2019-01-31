FROM ubuntu:18.04

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install --yes python3 python3-pip
RUN pip3 install pipenv
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

COPY ./compose/production/django/entrypoint /entrypoint
COPY ./compose/local/django/start /start

WORKDIR /app

# Do this before the copy so the python requirements can be
# cached
# TODO Do this with yarn as well
COPY ./Pipfile* /app/
RUN pipenv install --deploy --dev

ENTRYPOINT ["/entrypoint"]
