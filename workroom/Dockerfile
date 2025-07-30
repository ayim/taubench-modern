FROM node:24-alpine AS build

ARG ACE_SERVICE_VERSION
ARG VITE_INSTANCE_ID
ARG VITE_DEPLOYMENT_TYPE
ARG VITE_DEV_WORKROOM_TENANT_LIST_URL
ARG VITE_DEV_SERVER_PORT

ENV ACE_SERVICE_VERSION=${ACE_SERVICE_VERSION}
ENV VITE_INSTANCE_ID=$VITE_INSTANCE_ID
ENV VITE_DEPLOYMENT_TYPE=$VITE_DEPLOYMENT_TYPE
ENV VITE_DEV_WORKROOM_TENANT_LIST_URL=$VITE_DEV_WORKROOM_TENANT_LIST_URL
ENV VITE_DEV_SERVER_PORT=$VITE_DEV_SERVER_PORT

ENV NODE_ENV=production

WORKDIR /app

COPY frontend frontend
COPY backend backend
COPY package*.json vite.config.ts tailwind.config.js postcss.config.js ./

RUN --mount=type=secret,id=npmrc,dst=/app/.npmrc npm ci --include=dev && \
    npm run build && \
    npm prune --production

RUN sed -i -e "s/ACE_WORKROOM_VERSION_PLACEHOLDER/${ACE_SERVICE_VERSION}/g" frontend/dist/assets/index-*.js

#region Final
FROM node:24-alpine

ARG PORT

ENV NODE_ENV=production

ENV AGENT_SERVER_HOST=
ENV AGENT_SERVER_PORT=
ENV ACE_SERVICE_VERSION=
ENV PORT=${PORT}

WORKDIR /app

RUN mkdir frontend && mkdir backend

COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules node_modules
COPY --from=build /app/frontend/dist frontend/dist
COPY --from=build /app/frontend/public frontend/public
COPY --from=build /app/backend/dist backend/dist

EXPOSE $PORT

ENTRYPOINT ["node", "./backend/dist/index.js"]

ARG DOCKERFILE_URL
LABEL org.opencontainers.image.source="${DOCKERFILE_URL}"
#endregion
