# SAI SDK Storybook

Interactive documentation and testing environment for the Sema4.ai SDK features.

## 🚀 Getting Started

### Launch Storybook

```bash
npm run storybook
```

This will start Storybook on `http://localhost:6006`

### Build Storybook

To build a static version of Storybook:

```bash
npm run build-storybook
```

## 📚 Available Stories

### 1. Agent Prompt Demo

Test the Agent Prompt feature with:

- **Synchronous generation**: Send a prompt and get a complete response
- **Streaming**: Watch responses stream in real-time
- **System instructions**: Customize agent behavior
- **Response metadata**: View model, tokens, and stop reasons

**Configuration needed:**

- Base URL (e.g., `https://api.sema4.ai` or `http://localhost:8080`)
- API Key (your OpenAI API key)
- Model (default: `gpt-4o`)

### 2. Scenario Demo

Test the Scenario feature with:

- **Custom tools**: Define tools with callbacks (e.g., weather API)
- **Context control**: Adjust temperature, max tokens, system instructions
- **Streaming execution**: Watch tool calls and responses in real-time
- **Tool chains**: See tools being called and their results

**Features:**

- Pre-configured weather tool example
- Real-time tool call tracking
- Incremental streaming updates
- Full response viewing

### 3. Ephemeral Agent Chat

Test the Ephemeral Agent feature with:

- **Real-time chat**: WebSocket-based streaming conversation
- **Multi-turn conversations**: Maintain context across messages
- **Client tools**: Execute tools in the browser (e.g., weather API)
- **Agent configuration**: Customize name, description, and runbook

**Features:**

- Interactive chat interface
- Real-time message streaming
- Tool execution tracking
- Connection status indicators

## 🔧 Configuration

All demos require:

1. **Base URL**: Your SAI platform endpoint

   - Production: `https://api.sema4.ai`
   - Local dev: `http://localhost:8080`
   - WebSocket: `wss://api.sema4.ai` (auto-converted for Ephemeral Agent)

2. **API Key**: Your OpenAI API key

   - Get one from: https://platform.openai.com/api-keys

3. **Model** (optional):
   - `gpt-4o` (default, most capable)
   - `gpt-4o-mini` (faster, cheaper)
   - `gpt-4-turbo`
   - `gpt-3.5-turbo`

## 💡 Usage Tips

### Testing Agent Prompt

1. Start with the default prompt or enter your own
2. Try both "Generate" and "Stream" buttons to see the difference
3. Adjust system instructions to change agent behavior
4. Check the "Raw Response" section for full API response details

### Testing Scenarios

1. The weather tool is pre-configured for testing
2. Try different prompts like:
   - "What's the weather in Tokyo?"
   - "Compare weather in Paris and London"
   - "Is it raining in New York?"
3. Watch the "Tool Calls" section to see when the weather tool is invoked
4. Use "Stream Scenario" to see real-time updates

### Testing Ephemeral Agent Chat

1. Configure the agent's name, description, and runbook
2. Click "Connect to Agent" to establish WebSocket connection
3. Send messages and watch responses stream in real-time
4. The weather tool will be called automatically when you ask about weather
5. Check "Tool Calls" to see when tools are executed

## 🎨 Customization

### Adding New Tools

Edit the tool definitions in the component files:

```typescript
const myTool = defineTool({
  name: 'my_tool',
  description: 'What my tool does',
  input_schema: {
    type: 'object',
    properties: {
      param: { type: 'string', description: 'Parameter description' },
    },
    required: ['param'],
  },
  callback: async (input: { param: string }) => {
    // Your tool logic here
    return { result: 'success' };
  },
});
```

### Changing Styles

This project uses Tailwind CSS for styling. To customize the appearance:

- Edit the Tailwind classes directly in the component files
- Modify `tailwind.config.js` to extend the default theme
- Add custom styles in `stories/components/tailwind.css` if needed

## 🐛 Troubleshooting

### "Failed to fetch" or connection errors

- Check that your Base URL is correct
- Verify your API key is valid
- For localhost, ensure your server is running
- For WebSocket (Ephemeral Agent), ensure the URL uses `ws://` or `wss://`

### Tool callbacks not firing

- Check browser console for errors
- Verify tool name matches between definition and agent prompt
- Ensure input_schema is valid JSON Schema

### Streaming not working

- Some browsers may block WebSocket connections
- Check CORS settings on your server
- Try with a different browser or disable extensions

## 📖 Documentation

For more information about the SAI SDK:

- [Agent Prompt Documentation](../src/agent-prompt/README.md)
- [Scenarios Documentation](../src/sdk/README.md)
- [Ephemeral Agent Documentation](../src/agent-ephemeral/README.md)

## 🤝 Contributing

To add new stories:

1. Create a new component in `stories/components/`
2. Create a corresponding story file in `stories/`
3. Follow the existing patterns for consistency
4. Test thoroughly before committing

## 📝 Notes

- These demos use mock tools for demonstration purposes
- In production, replace mock implementations with real API calls
- API keys are only used client-side and not stored
- All demos support both production and localhost environments
