# Tools

Sema4.ai Agent Server comes with a set of tools that can be used to extend the functionality of an agent.

**_Sema4.ai Action Server_**

Run AI Python based actions with [Sema4.ai Action Server](https://github.com/Sema4AI/actions).
Does not require a service API key, but it requires the credentials for a running Action Server instance to be defined.
These you set while creating an assistant.

**_Connery Actions_**

Connect Action Server to the real world with [Connery](https://github.com/connery-io/connery).

Requires setting an environment variable, which you get during the [Connery Runner setup](https://docs.connery.io/docs/runner/quick-start/):

```shell
CONNERY_RUNNER_URL=https://your-personal-connery-runner-url
CONNERY_RUNNER_API_KEY=...
```

**DuckDuckGo Search**

Search the web with [DuckDuckGo](https://pypi.org/project/duckduckgo-search/). Does not require any API keys.

**Tavily Search**

Uses the [Tavily](https://app.tavily.com/) search engine. Requires setting an environment variable:

```shell
export TAVILY_API_KEY=tvly-...
```

Sign up for an API key [here](https://app.tavily.com/).

**Tavily Search (Answer Only)**

Uses the [Tavily](https://app.tavily.com/) search engine.
This returns only the answer, no supporting evidence.
Good when you need a short response (small context windows).
Requires setting an environment variable:

```shell
export TAVILY_API_KEY=tvly-...
```

Sign up for an API key [here](https://app.tavily.com/).

**You.com Search**

Uses [You.com](https://you.com/) search, optimized responses for LLMs.
Requires setting an environment variable:

```shell
export YDC_API_KEY=...
```

Sign up for an API key [here](https://you.com/)

**SEC Filings (Kay.ai)**

Searches through SEC filings using [Kay.ai](https://www.kay.ai/).
Requires setting an environment variable:

```shell
export KAY_API_KEY=...
```

Sign up for an API key [here](https://www.kay.ai/)

**Press Releases (Kay.ai)**

Searches through press releases using [Kay.ai](https://www.kay.ai/).
Requires setting an environment variable:

```shell
export KAY_API_KEY=...
```

Sign up for an API key [here](https://www.kay.ai/)

**Arxiv**

Searches [Arxiv](https://arxiv.org/). Does not require any API keys.

**PubMed**

Searches [PubMed](https://pubmed.ncbi.nlm.nih.gov/). Does not require any API keys.

**Wikipedia**

Searches [Wikipedia](https://pypi.org/project/wikipedia/). Does not require any API keys.

