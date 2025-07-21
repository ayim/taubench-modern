FROM nginx:stable-alpine

ARG VITE_INSTANCE_ID
ARG VITE_DEPLOYMENT_TYPE
ARG VITE_DEV_WORKROOM_TENANT_LIST_URL
ARG VITE_DEV_SERVER_PORT

ENV VITE_INSTANCE_ID=$VITE_INSTANCE_ID
ENV VITE_DEPLOYMENT_TYPE=$VITE_DEPLOYMENT_TYPE
ENV VITE_DEV_WORKROOM_TENANT_LIST_URL=$VITE_DEV_WORKROOM_TENANT_LIST_URL
ENV VITE_DEV_SERVER_PORT=$VITE_DEV_SERVER_PORT

ENV AGENT_SERVER_HOST=
ENV AGENT_SERVER_PORT=
ENV ACE_SERVICE_VERSION=
ENV WORKROOM_URL=

WORKDIR /app

RUN apk upgrade --no-cache && \
  apk add --no-cache npm

COPY package*.json ./

RUN --mount=type=secret,id=npmrc,dst=/app/.npmrc npm install

COPY public ./public
COPY src ./src
COPY index.html entrypoint.sh postcss.config.js tailwind.config.js tsconfig.json tsconfig.node.json tsr.config.json vite.config.ts ./
COPY nginx.*.conf /etc/nginx/

RUN npm run build && \
  npm prune --omit=dev && \
  cp -r /app/dist /var/www && \
  sed -i -e "s/ACE_WORKROOM_VERSION_PLACEHOLDER/${ACE_SERVICE_VERSION}/g" /var/www/assets/index-*.js

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3001/meta || exit 1

ENTRYPOINT ["sh", "/app/entrypoint.sh"]

ARG DOCKERFILE_URL
LABEL org.opencontainers.image.source="${DOCKERFILE_URL}"
