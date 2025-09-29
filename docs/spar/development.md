# SPAR development

Both the agent server and workroom (interaction UI) are available in this repository - you can develop against both projects at the same time in a combined manner (SPAR stack). The recommended approach is with Docker, but you can run both components outside of the Docker stack with hot reloading for improved development experience.

## Prerequisites

To develop the Workroom application, you must have **NodeJS** and **NPM** installed, alongside **Docker**, with valid Sema4.ai authentication configured with which to install packages needed by Workroom and associated dependencies.

1. You **must** have an `~/.npmrc` file.

   _This is needed for both local and docker-based development._

   You must generate a Personal Access Token (PAT) in [GitHub settings](https://github.com/settings/tokens). The token must be granted access to at least the `read:packages` scope.

   The structure of the `~/.npmrc` file should be as follows:

   ```
   //npm.pkg.github.com/:_authToken=ghp_<snip>
   @sema4ai:registry=https://npm.pkg.github.com/
   ```

1. You need to set up authentication against GitHub Container Registry (GHCR).

   This is required to pull the **Data Server** Docker image.

   Run the following command, supplying your GitHub **username** and the **PAT** you created in the previous step (`ghp_xxx...`):

   ```
   $ docker login ghcr.io
   Username: mygithubusername
   Password: <paste your PAT here>
   Login Succeeded
   $
   ```

1. Create a `.env` file in `./workroom` by copying the example file. Run this command from the `workroom` directory:

   ```
   cp .env.example .env
   ```

   This will create a `.env` file with the default environment variable values, which you can then edit as needed.

   _Note that copying the `.env.auth.example` file will setup Workroom to use authentication._

1. Run `npm install` inside the `workroom` directory

> [!NOTE]
> The `.env` file in `./workroom` is only necessary for non-docker-based Workroom development. If using workroom via Docker, you don't need to touch these files.

## Running the Docker stack

Often times you'll want to run some portion of the SPAR stack, if not all of it, within Docker.

> [!NOTE]
> Docker builds using the local source code in this repository (for agent server and workroom), but doesn't provide hot reload functionality.

The docker stack comes in several flavours:

| Agent Server | Workroom | Authentication | Command                                                                                                                |
| :----------: | :------: | :------------: | ---------------------------------------------------------------------------------------------------------------------- |
|     Yes      |    No    |       No       | `COMPOSE_PROFILES=agent-server docker compose up --build`                                                              |
|     Yes      |    No    |      Yes       | `COMPOSE_PROFILES=agent-server docker compose -f compose.yml -f compose.override.auth.yml up --build`                  |
|     Yes      |   Yes    |       No       | `COMPOSE_PROFILES=spar docker compose up --build`                                                                      |
|     Yes      |   Yes    |      Yes       | `COMPOSE_PROFILES=spar docker compose -f compose.yml -f compose.override.auth.yml --env-file workroom/.env up --build` |

> [!TIP]
> Compose profiles are just like "tags". You can set one or more by either using `COMPOSE_PROFILES=one,two docker compose up` or `docker compose --profile one --profile two up`.

For builds _without_ workroom, you can then spin up a local build by performing the following:

1.  Change directory to `./workroom`
2.  Install dependencies - `npm install`
3.  Create a `.env` file from one of the examples. Use an authenticated example if the stack calls for it.
4.  Run `npm run dev` to start the workroom service.

> [!TIP]
> The running agent server will be available on [`http://localhost:8000`](http://localhost:8000), and workroom on [`http://localhost:8001`](http://localhost:8001). Additionally, the private/internal workroom API will be exposed in development on `http://localhost:8002`.
