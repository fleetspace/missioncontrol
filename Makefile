test:
	docker-compose -f test.yml run --rm django pipenv run pytest