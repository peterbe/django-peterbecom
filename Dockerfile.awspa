# Note! If you make changes it in this file, to rebuild it use:
#   docker-compose build awspa
#

# This should match what we have in the Node section of the main Dockerfile.
FROM node:8

ADD awspa/package.json /package.json
RUN yarn

ENV NODE_PATH=/node_modules
ENV PATH=$PATH:/node_modules/.bin
WORKDIR /app
ADD awspa /app

EXPOSE 4000


ENTRYPOINT ["/bin/bash", "/app/bin/run.sh"]
CMD ["start"]
