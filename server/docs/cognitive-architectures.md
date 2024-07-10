# Cognitive Architectures

This refers to the logic of how the GPT works.
There are currently three different architectures supported, but because they are all written in LangGraph, it is very 
easy to modify them or add your own.

The three different architectures supported are assistants, RAG, and chatbots.

**Assistants**

Assistants can be equipped with arbitrary amount of tools and use an LLM to decide when to use them. This makes them 
the most flexible choice, but they work well with fewer models and can be less reliable.

When creating an assistant, you specify a few things.

First, you choose the language model to use. Only a few language models can be used reliably well: GPT-3.5, GPT-4, 
Claude, and Gemini.

Second, you choose the tools to use. These can be predefined tools OR a retriever constructed from uploaded files. You 
can choose however many you want.

The cognitive architecture can then be thought of as a loop. First, the LLM is called to determine what (if any) 
actions to take. If it decides to take actions, then those actions are executed and it loops back. If no actions are 
decided to take, then the response of the LLM is the final response, and it finishes the loop.

![](_static/agent.png)

This can be a really powerful and flexible architecture. This is probably closest to how us humans operate. However, 
these also can be not super reliable, and generally only work with the more performant models (and even then they can 
mess up). Therefore, we introduced a few simpler architecures.

Assistants are implemented with [LangGraph](https://github.com/langchain-ai/langgraph) `MessageGraph`. A `MessageGraph` is a graph that models its state as a `list` of messages.

**RAGBot**

One of the big use cases of the GPT store is uploading files and giving the bot knowledge of those files. What would it 
mean to make an architecture more focused on that use case?

We added RAGBot - a retrieval-focused GPT with a straightforward architecture. First, a set of documents are retrieved. 
Then, those documents are passed in the system message to a separate call to the language model so it can respond.

Compared to assistants, it is more structured (but less powerful). It ALWAYS looks up something - which is good if you 
know you want to look things up, but potentially wasteful if the user is just trying to have a normal conversation. 
Also importantly, this only looks up things once - so if it doesn’t find the right results then it will yield a bad 
result (compared to an assistant, which could  decide to look things up again).

![](_static/rag.png)

Despite this being a more simple architecture, it is good for a few reasons. First, because it is simpler it can work 
pretty well with a wider variety of models (including lots of open source models). Second, if you have a use case where 
you don’t NEED the flexibility of an assistant (eg you know users will be looking up information every time) then it 
can be more focused. And third, compared to the final architecture below it can use external knowledge.

RAGBot is implemented with [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph`. A `StateGraph` is a generalized graph that can model arbitrary state (i.e. `dict`), not just a `list` of messages.

**ChatBot**

The final architecture is dead simple - just a call to a language model, parameterized by a system message. This allows 
the GPT to take on different personas and characters. This is clearly far less powerful than Assistants or RAGBots 
(which have access to external sources of data/computation) - but it’s still valuable! A lot of popular GPTs are just 
system messages at the end of the day, and CharacterAI is crushing it despite largely just being system messages as 
well.

![](_static/chatbot.png)

ChatBot is implemented with [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph`. A `StateGraph` is a generalized graph that can model arbitrary state (i.e. `dict`), not just a `list` of messages.

