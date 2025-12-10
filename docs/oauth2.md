The Oauth2 flow must be used to access MCP Servers and we must be able to do this flow from the Agent Server
(and clients should use it to authenticate).

Now, to implement this the plan is creating the following APIs in the agent-server:

/oauth2/login: will get the current user / mcp server and make the authentication to store the refresh token/auth token.

    - We need a table in the database to store the refresh token/auth token (with foreign key to the user, but the mcp server will just be referenced by the url)
    - This starts the oauth2 flow by:
        - Creating a httpx.AsyncClient (passing `follow_redirects=True`) and `auth` set to a `agent_platform.server.oauth.oauth_provider.OAuth` instance.
        - Doing the `with httpx.AsyncClient(follow_redirects=True, auth=auth) as client:` should be enough to start the oauth2 flow.

/oauth2/logout -- will delete the refresh token/auth token from the database

/oauth2/status -- gets the status of the oauth2 connection (if the user is authenticated and if the refresh token is valid)

    - may return status from all mcp servers the user has access to or a single mcp server.

/oauth2/callback: will be used to get the code and state from the oauth2 provider and will be used to get the access token and refresh token.

    - At this point the user is authenticated and the access token and refresh token are stored in the database.

/oauth2/refresh: will be used to refresh the access token.
