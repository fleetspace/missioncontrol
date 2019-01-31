.PHONY: docker export collectstatic

GIT_TAG := $(shell git describe --always --dirty)

collectstatic:
	cd missioncontrol && pipenv run ./manage.py collectstatic

docker:
	docker build -t docker.fleet.space/missioncontrol:$(GIT_TAG) .

export: docker
	docker save -o missioncontrol.tar docker.fleet.space/missioncontrol:$(GIT_TAG)
