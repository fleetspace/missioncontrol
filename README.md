# missioncontrol  
Mission Control stores all of the state about satellites, grounstations, passes, telemetry, etc.  

## Configuration
A large part of this project was built using cookiecutter-django.  
See here for some additional configuration options : http://cookiecutter-django.readthedocs.io/en/latest/settings.html

## Getting started (development)
1. Clone this repo

    `git clone <missioncontrol repo>`
    `git submodule update --init`


2. Start the development server

      `docker-compose -f local.yml up --build`

      Optionally export the configuration filename so you  
      don't have to specify the config file every time:  
      `export COMPOSE_FILE=local.yml`  
      `docker-compose up`

3. Migrate the database and create a user  
      `docker-compose -f local.yml run --rm django pipenv run ./manage.py migrate`  
      `docker-compose -f local.yml run --rm django pipenv run ./manage.py createsuperuser`

## Deployment method (production)

1. `git pull`
2. `git submodule update`
3. `docker-compose -f production.yml up --build -d`
4. `docker-compose -f production.yml run --rm django pipenv run ./manage.py migrate`

## Initial deployment (production)

* Set up environment files:

    ```
    # .envs/.production/.caddy
    DOMAIN_NAME=<hostname / ip>
    ```

    ```
    # .envs/.production/.django

    # General
    # ------------------------------------------------------------------------------
    DJANGO_SETTINGS_MODULE=config.settings.production
    DJANGO_SECRET_KEY=<keep this safe>
    DJANGO_JWT_SECRET=<keep this safe too>
    DJANGO_ADMIN_URL=<if you want something other than '/admin'>
    DJANGO_ALLOWED_HOSTS=<hostname / ip>

    # Security
    # ------------------------------------------------------------------------------
    # TIP: better off using DNS, however, redirect is OK too
    DJANGO_SECURE_SSL_REDIRECT=True

    # Gunicorn
    # ------------------------------------------------------------------------------
    WEB_CONCURRENCY=4
    ```

    ```
    # .envs/.production/.postgres
    # PostgreSQL
    # ------------------------------------------------------------------------------
    POSTGRES_HOST=postgres
    POSTGRES_PORT=5432
    POSTGRES_DB=missioncontrol
    POSTGRES_USER=<fill me in>
    POSTGRES_PASSWORD=<fill me in>
    ```

* Create a superuser: 
    ```
    docker-compose -f production.yml run --rm django pipenv run ./manage.py createsuperuser
    ```

* Follow the [Deployment Method](#deployment-method) steps.