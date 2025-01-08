# Default Agent Architecture

This Agent Architecture is designed for use with OpenAI and Azure OpenAI models. It supports tool usage and can be integrated into Sema4.ai's Agent Server as an available Agent Architecture.

## Features

- **Tool Usage**: Supports calling tools within the agent's workflow.
- **Model Support**: Compatible with OpenAI and Azure OpenAI models.
- **Reasoning**: Includes reasoning capabilities for more complex workflows.
- **Customizable**: Allows customization of chat prompt templates for execution and reasoning nodes.

## Usage

To use this Agent Architecture, you need to integrate it with the Sema4.ai Agent Server. Ensure that the required environment variables and dependencies are properly configured.

## Environment Variables

The following environment variables are supported:

- `OPENAI_API_KEY`: API key for OpenAI.
- `AZURE_OPENAI_API_KEY`: API key for Azure OpenAI.
- `AZURE_OPENAI_API_BASE`: Base URL for Azure OpenAI.
- `AZURE_OPENAI_API_VERSION`: API version for Azure OpenAI.
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Deployment name for Azure OpenAI.
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME`: Embeddings deployment name for Azure OpenAI.

## Example

Here is an example of how to configure and run the Default Agent Architecture:

```python
from agent_architecture_default import OpenaiToolsAgentArchitecture

agent_architecture = OpenaiToolsAgentArchitecture(
    agent=your_agent_instance,
    tools=your_tools_list,
    knowledge_files=your_knowledge_files,
)
graph = agent_architecture.compile_graph()
graph.invoke(input)
```

For more details, refer to the docstrings and comments within the code.
