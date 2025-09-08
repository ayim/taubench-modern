FROM node:24-alpine AS build

ARG ACE_SERVICE_VERSION

ENV ACE_SERVICE_VERSION=${ACE_SERVICE_VERSION}

ENV NODE_ENV=production

WORKDIR /app

COPY frontend frontend
COPY backend backend
COPY spar-ui spar-ui
COPY package*.json turbo.json ./

RUN --mount=type=secret,id=npmrc,dst=/app/.npmrc npm ci --include=dev && \
    npm run build && \
    npm prune --production

RUN sed -i -e "s/ACE_WORKROOM_VERSION_PLACEHOLDER/${ACE_SERVICE_VERSION}/g" frontend/dist/assets/index-*.js

#region Final
FROM node:24-alpine

ARG SEMA4AI_WORKROOM_PORT=8001

ENV NODE_ENV=production
ENV SEMA4AI_WORKROOM_PORT=${SEMA4AI_WORKROOM_PORT}

WORKDIR /app

RUN mkdir frontend && mkdir backend

COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules node_modules
COPY --from=build /app/frontend/dist frontend/dist
COPY --from=build /app/frontend/public frontend/public
COPY --from=build /app/backend/dist backend/dist

EXPOSE $SEMA4AI_WORKROOM_PORT

ENTRYPOINT ["node", "./backend/dist/index.js"]

ARG DOCKERFILE_URL
LABEL org.opencontainers.image.source="${DOCKERFILE_URL}"
#endregion
