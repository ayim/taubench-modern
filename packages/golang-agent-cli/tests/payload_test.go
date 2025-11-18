package tests

import (
	"encoding/json"
	"testing"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/stretchr/testify/assert"
)

func TestVerifySelectedToolsWhenBuildingPayload(t *testing.T) {
	jsonString := `{"selected_tools":{"tool_names":[{"tool_name":"tool1"}]}}`
	expectedSelectedTools := AgentServer.SelectedTools{
		ToolNames: []AgentServer.SelectedToolConfig{
			{
				ToolName: "tool1",
			},
		},
	}

	payload := &AgentServer.AgentPayload{}
	assert.NoError(t, json.Unmarshal([]byte(jsonString), payload), "Failed to parse JSON")
	agent := AgentServer.BuildAgent(payload)
	assert.NotNil(t, agent.SelectedTools, "Expected one selected tool in the payload")
	assert.Equal(t, agent.SelectedTools, expectedSelectedTools, "Selected tools in the payload do not match the original")

	builtPayload := AgentServer.BuildAgentPayload(agent)
	assert.NotNil(t, builtPayload.SelectedTools, "Expected one selected tool in the payload")
	assert.Equal(t, builtPayload.SelectedTools, expectedSelectedTools, "Selected tools in the payload do not match the original")

	// Verify round-trip JSON serialization
	marshaledJSON, err := json.Marshal(builtPayload.SelectedTools)
	expectedString := `{"tool_names":[{"tool_name":"tool1"}]}`
	assert.NoError(t, err, "Failed to marshal SelectedTools")
	assert.JSONEq(t, expectedString, string(marshaledJSON), "Marshaled JSON should match expected format")
}

func TestVerifySelectedToolsOmitted(t *testing.T) {
	jsonString := `{}`
	payload := &AgentServer.AgentPayload{}
	assert.NoError(t, json.Unmarshal([]byte(jsonString), payload), "Failed to parse JSON")
	agent := AgentServer.BuildAgent(payload)
	assert.Equal(t, agent.SelectedTools, AgentServer.SelectedTools{}, "SelectedTools is created with empty ToolNames")

	builtPayload := AgentServer.BuildAgentPayload(agent)
	assert.Equal(t, builtPayload.SelectedTools, AgentServer.SelectedTools{}, "SelectedTools is created with empty ToolNames")

	// Verify round-trip JSON serialization - SelectedTools should be omitted from full payload
	marshaledPayload, err := json.Marshal(builtPayload.SelectedTools)
	expectedString := `{}`
	assert.NoError(t, err, "Failed to marshal SelectedTools")
	assert.JSONEq(t, expectedString, string(marshaledPayload), "tool_names should be omitted from JSON when empty")
}

func TestVerifySelectedToolsInitializedToEmptySlice(t *testing.T) {
	jsonString := `{"selected_tools": {}}`
	expectedSelectedTools := AgentServer.SelectedTools{
		ToolNames: nil,
	}
	payload := &AgentServer.AgentPayload{}
	assert.NoError(t, json.Unmarshal([]byte(jsonString), payload), "Failed to parse JSON")
	agent := AgentServer.BuildAgent(payload)
	assert.NotNil(t, agent.SelectedTools, "SelectedTools should not be nil")
	assert.Equal(t, agent.SelectedTools, expectedSelectedTools, "Selected tools should have empty ToolNames")
	assert.Empty(t, agent.SelectedTools.ToolNames, "ToolNames should be empty")

	builtPayload := AgentServer.BuildAgentPayload(agent)
	assert.NotNil(t, builtPayload.SelectedTools, "SelectedTools should not be nil")
	assert.Equal(t, builtPayload.SelectedTools, expectedSelectedTools, "Selected tools should have empty ToolNames")
	assert.Empty(t, builtPayload.SelectedTools.ToolNames, "ToolNames should be empty")

	// Verify round-trip JSON serialization
	marshaledJSON, err := json.Marshal(builtPayload.SelectedTools)
	assert.NoError(t, err, "Failed to marshal SelectedTools")
	expectedJSON := `{}`
	assert.JSONEq(t, expectedJSON, string(marshaledJSON), "Marshaled JSON should match expected format with empty selected_tools object")
}
