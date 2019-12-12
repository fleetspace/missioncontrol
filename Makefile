test:
	docker-compose -f local.yml run --rm django pipenv run pytest