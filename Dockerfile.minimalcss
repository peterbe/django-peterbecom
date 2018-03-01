# Note! If you make changes it in this file, to rebuild it use:
#   docker-compose build minimalcss
#
# To get into a bash session use:
#
#   docker-compose run minimalcss bash
#
# Or with the port forward to the host:
#
#   docker-compose run --service-ports minimalcss bash
#
# Or, as root:
#
#   docker-compose run --user 0 minimalcss bash
#

# Using node:8 will segfault :)
FROM node:9

WORKDIR /app
ADD minimalcss /app

EXPOSE 5000

WORKDIR /app
COPY minimalcss/package.json /package.json
COPY minimalcss/yarn.lock /yarn.lock
RUN yarn
COPY minimalcss /app

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
