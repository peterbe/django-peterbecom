.PHONY: build clean migrate revision shell currentshell stop test run django-shell docs psql build-frontend

help:
	@echo "Welcome to the django-peterbe\n"
	@echo "The list of commands for local development:\n"
	@echo "  build            Builds the docker images for the docker-compose setup"
	@echo "  ci               Run the test with the CI specific Docker setup"
	@echo "  clean            Stops and removes all docker containers"
	@echo "  migrate          Runs the Django database migrations"
	@echo "  redis-cache-cli  Opens a Redis CLI to the cache Redis server"
	@echo "  shell            Opens a Bash shell"
	@echo "  currentshell     Opens a Bash shell into existing running 'web' container"
	@echo "  test             Runs the Python test suite"
	@echo "  run              Runs the whole stack, served on http://localhost:8000/"
	@echo "  stop             Stops the docker containers"
	@echo "  django-shell     Django integrative shell"
	@echo "  psql             Open the psql cli"

# Dev configuration steps
.docker-build:
	make build


build:
	docker-compose build base
	touch .docker-build

clean: stop
	docker-compose rm -f
	rm -fr .docker-build

migrate:
	docker-compose run web python manage.py migrate --run-syncdb

shell: .docker-build
	# Use `-u 0` to automatically become root in the shell
	docker-compose run --user 0 web bash

currentshell: .docker-build
	# Use `-u 0` to automatically become root in the shell
	docker-compose exec --user 0 web bash

# redis-cache-cli: .docker-build
	# docker-compose run redis-cache redis-cli -h redis-cache

psql: .docker-build
	docker-compose run db psql -h db -U postgres

stop:
	docker-compose stop

test: .docker-build
	@bin/test.sh

run: .docker-build
	docker-compose up web worker

django-shell: .docker-build
	docker-compose run web python manage.py shell
