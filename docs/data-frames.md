# Data frames

Data frames in the agent server context mean some tabular data that is stored in the agent server.
It should usually be initially provided by the user through a file upload (say a csv file or
an excel file -- note that an excel file may end up having multiple sheets, which means
that we may actually have multiple data frames from one single file).

Also, a data frame could be created automatically if some action/tool returns tabular data
(i.e.: an action/mcp tool that returns an object with a Response[Table(columns, rows)] or just
Table(columns, rows) shape).

# References:

[Miro board: Internals behind the Data Model API in Agent Server](https://miro.com/app/board/uXjVImChMn0=/?moveToWidget=3458764636556067436&cot=14)
[Linear: Data frames](https://linear.app/sema4ai/project/dataframes-fka-tables-4c740da3f7f2/overview)
[Figma: Data frames](https://www.figma.com/design/rNDLIqnUCT0SaiBWUvnpcL/Sema4.ai-Studio?node-id=12139-208045&t=r5IlfyVdDwYGrvFt-4)
[Hackaton for data frames](https://github.com/Sema4AI/agent-platform/compare/main...hackathon/better-tables)

# Workflow supported (phase 1)

- User uploads a csv or excel file.
- At that point the user is then asked if he wants to treat that file as a data frame.
  - Feature needed: Given a file upload, generate an "agent" message that asks what the user wants to do with the file.
    - One option should be: "Generate Data Frame"

# What happens when a user uploads a file you may ask:

1. The agent server API to upload a file is called in Studio (workroom) and then an attachment message is automatically created right
   afterwards (from the UI). Something as:

   ```typescript
   const uploadedFiles = await apiClient.uploadFiles(...)
   ...
   // Stream a new message with "attachment" kind
   // https://github.com/Sema4AI/agents-workroom/blob/main/src/components/Files.tsx#L110
   streamManager.initiateStream(createAttachmentMessage(...), currentChatId, agentId);
   ```

Internally the agent server deserializes that as a `ThreadAttachmentContent` message and that becomes something as `Uploaded [{attachment_content.name}]({attachment_content.uri})` when sent to the agent.

Note: it uses the `uri` when referenced here which is something as `agent-server-file://${file.file_id}`.

Note2: this is different from when the file is uploaded by an action/tool where none of the above happens (the file just
"appears" in the chat sidebar without any further processing -- also, the file in this case is nearly invisible in the thread,
it just appears in the related storage).

Given that, new APIs will be added to the agent server to create data frames from the internal file ids, but the `ThreadAttachmentContent`
will not be used (as we should be able to create data frames even from files that are uploaded by actions/tools).

REST APIs created:

- threads/{thread_id}/inspect-file-as-data-frame (GET)
- threads/{thread_id}/data-frames/from-file (POST)
- threads/{thread_id}/data-frames (GET)

Next work:

- Create (builtin) tools that can be used by the agent to create new data frames based on existing data frames based on some computation (SQL)
- Update the runbook system prompt so that such tools and the related dataframes are available to the agent.
- Make the result of named queries (Tables) be available as data frames automatically.
- Create tools that allow an agent to read the contents of data frames.
