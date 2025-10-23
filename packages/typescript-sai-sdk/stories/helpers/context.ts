export const AGENT_SETUP_CONTEXT = {
  agentName: 'Customer Support Agent',
  agentDescription: 'An AI agent that helps customers with their questions and issues',
  agentRunbook: 'Handle customer inquiries professionally and efficiently',
  agentConversationStarter: 'Hello! How can I help you today?',
  agentQuestionGroups:
    '[{ "name": "Product questions", "description": "Questions about the product", "questions": ["What is the product?", "What is the price?", "What is the warranty?"] }, { "name": "Technical support", "description": "Questions about the technical support", "questions": ["How do I install the product?", "How do I use the product?", "How do I troubleshoot the product?"] }, { "name": "Billing inquiries", "description": "Questions about the billing", "questions": ["How do I pay for the product?", "How do I cancel the product?", "How do I get a refund?"] }]',
  agentAvailableActions:
    '[{ "organization": "example", "name": "send_email", "version": "1.0.0" }, { "organization": "example", "name": "create_ticket", "version": "1.0.0" }, { "organization": "example", "name": "search_knowledge_base", "version": "1.0.0" }]',
};
