package agent_server_client

// BuildAgentPayload builds an AgentPayload from an Agent.
func BuildAgentPayload(agent *Agent) AgentPayload {
	return AgentPayload{
		Name:           agent.Name,
		Description:    agent.Description,
		Version:        agent.Version,
		Runbook:        agent.Runbook,
		Model:          agent.Model,
		AdvancedConfig: agent.AdvancedConfig,
		ActionPackages: agent.ActionPackages,
		McpServers:     agent.McpServers,
		QuestionGroups: agent.QuestionGroups,
		Metadata:       agent.Metadata,
		Extra:          agent.Extra,
		Files:          agent.Files,
		Public:         agent.Public,
	}
}

// BuildAgent builds an Agent from an AgentPayload.
func BuildAgent(payload *AgentPayload) *Agent {
	return &Agent{
		Name:           payload.Name,
		Description:    payload.Description,
		Version:        payload.Version,
		Runbook:        payload.Runbook,
		Model:          payload.Model,
		AdvancedConfig: payload.AdvancedConfig,
		ActionPackages: payload.ActionPackages,
		McpServers:     payload.McpServers,
		QuestionGroups: payload.QuestionGroups,
		Metadata:       payload.Metadata,
		Extra:          payload.Extra,
		Files:          payload.Files,
		Public:         payload.Public,
	}
}
