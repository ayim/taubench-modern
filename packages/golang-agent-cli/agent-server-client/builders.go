package agent_server_client

// BuildAgentPayload builds an AgentPayload from an Agent.
func BuildAgentPayload(agent *Agent) AgentPayload {
	agentSettings := agent.AgentSettings
	if agentSettings == nil {
		agentSettings = agent.Extra.AgentSettings
	}
	documentIntelligence := agent.DocumentIntelligence
	if documentIntelligence == "" || documentIntelligence == DocumentIntelligenceVersion("") {
		documentIntelligence = agent.Extra.DocumentIntelligence
	}
	return AgentPayload{
		Name:                 agent.Name,
		Description:          agent.Description,
		Version:              agent.Version,
		Runbook:              agent.Runbook,
		Model:                agent.Model,
		AdvancedConfig:       agent.AdvancedConfig,
		ActionPackages:       agent.ActionPackages,
		McpServers:           agent.McpServers,
		QuestionGroups:       agent.QuestionGroups,
		AgentSettings:        agentSettings,
		DocumentIntelligence: documentIntelligence,
		Metadata:             agent.Metadata,
		Extra:                agent.Extra,
		Files:                agent.Files,
		Public:               agent.Public,
		SelectedTools:        agent.SelectedTools,
	}
}

// BuildAgent builds an Agent from an AgentPayload.
func BuildAgent(payload *AgentPayload) *Agent {
	agentSettings := payload.AgentSettings
	if agentSettings == nil {
		agentSettings = payload.Extra.AgentSettings
	}
	extra := payload.Extra

	documentIntelligence := payload.DocumentIntelligence
	if documentIntelligence == "" || documentIntelligence == DocumentIntelligenceVersion("") {
		documentIntelligence = extra.DocumentIntelligence
	}
	if extra.AgentSettings == nil {
		extra.AgentSettings = agentSettings
		extra.DocumentIntelligence = documentIntelligence
	}

	return &Agent{
		Name:                 payload.Name,
		Description:          payload.Description,
		Version:              payload.Version,
		Runbook:              payload.Runbook,
		Model:                payload.Model,
		AdvancedConfig:       payload.AdvancedConfig,
		ActionPackages:       payload.ActionPackages,
		McpServers:           payload.McpServers,
		QuestionGroups:       payload.QuestionGroups,
		AgentSettings:        agentSettings,
		DocumentIntelligence: documentIntelligence,
		Metadata:             payload.Metadata,
		Extra:                extra,
		Files:                payload.Files,
		Public:               payload.Public,
		SelectedTools:        payload.SelectedTools,
	}
}
