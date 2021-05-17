test:
	# Build it first, just in case!
	docker-compose -f test.yml build django
	docker-compose -f test.yml run --rm django poetry run pytest
