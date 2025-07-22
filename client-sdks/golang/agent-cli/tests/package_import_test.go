package tests

import (
	"encoding/json"
	"testing"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"
)

func minimalMetadata() []*common.AgentPackageMetadata {
	return []*common.AgentPackageMetadata{{
		Version:             "1.0.0",
		Name:                "test-agent",
		Description:         "desc",
		Model:               common.SpecAgentModel{Provider: "openai", Name: "gpt-4o"},
		Architecture:        "agent",
		Reasoning:           "disabled",
		Knowledge:           []common.AgentPackageMetadataKnowledge{{Embedded: true, Name: "k1", Digest: "d1"}},
		Datasources:         []common.AgentPackageDatasource{{CustomerFacingName: "ds1", Engine: "engine1", Description: "dsdesc", Configuration: map[string]interface{}{"foo": "bar"}}},
		QuestionGroups:      []AgentServer.QuestionGroup{{Title: "qg1", Questions: []string{"q1", "q2"}}},
		ConversationStarter: "What tools do you have?",
		WelcomeMessage:      "Hi, How can I help you today?",
		Metadata:            AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode, WelcomeMessage: "meta-welcome"},
		ActionPackages: []common.AgentPackageActionPackageMetadata{{
			ActionPackageMetadata: common.ActionPackageMetadata{
				Name:        "ap1",
				Description: "apdesc",
				Version:     "0.1.0",
				Actions:     []common.ActionPackageMetadataAction{{Description: "actdesc", Name: "act1", Summary: "sum", OperationKind: "op"}},
			},
			Whitelist: "w1,w2",
			Path:      "MyActions/ap1",
		}, {
			ActionPackageMetadata: common.ActionPackageMetadata{
				Name:        "ap2",
				Description: "apdesc",
				Version:     "0.2.0",
			},
			Whitelist: "w3,w4",
			Path:      "Sema4ai/ap2",
		}},
		McpServers: []common.AgentPackageMcpServer{{
			Name:                 "mcp1",
			Transport:            "auto",
			Description:          "mcpdesc",
			URL:                  "http://localhost:1234",
			Headers:              common.AgentPackageMcpServerVariables{"h1": {Default: "hv1", Type: "string"}},
			ForceSerialToolCalls: true,
		}},
	}}
}

func TestBuildAgentPayload_Success(t *testing.T) {
	metadata := minimalMetadata()
	spec := &common.AgentSpec{}
	runbook := "runbook-content"

	payload, err := cmd.BuildAgentPayload(metadata, spec, runbook, "", "", "", false)
	assert.NoError(t, err)
	assert.NotNil(t, payload)
	assert.Equal(t, metadata[0].Name, payload.Name)
	assert.Equal(t, metadata[0].Description, payload.Description)
	assert.Equal(t, metadata[0].Version, payload.Version)
	assert.Equal(t, metadata[0].Model.Provider, payload.Model.Provider)
	assert.Equal(t, metadata[0].Model.Name, payload.Model.Name)
	assert.Equal(t, metadata[0].ConversationStarter, payload.Extra.ConversationStarter)
	assert.Equal(t, metadata[0].WelcomeMessage, payload.Extra.WelcomeMessage)
	assert.Equal(t, metadata[0].Metadata.Mode, payload.Metadata.Mode)
	if assert.Len(t, payload.ActionPackages, 2) {
		ap1 := payload.ActionPackages[0]
		ap2 := payload.ActionPackages[1]
		assert.Equal(t, metadata[0].ActionPackages[0].Name, ap1.Name)
		assert.Equal(t, metadata[0].ActionPackages[0].Version, ap1.Version)
		assert.Equal(t, "MyActions", ap1.Organization)
		assert.Equal(t, metadata[0].ActionPackages[1].Name, ap2.Name)
		assert.Equal(t, metadata[0].ActionPackages[1].Version, ap2.Version)
		assert.Equal(t, "Sema4ai", ap2.Organization)
	}
}

func TestBuildAgentPayload_InvalidActionPackagePath(t *testing.T) {
	metadata := minimalMetadata()
	spec := &common.AgentSpec{}
	runbook := "runbook-content"
	payload, err := cmd.BuildAgentPayload(metadata, spec, runbook, "", "", "", false)
	assert.NoError(t, err)
	assert.NotNil(t, payload)
	assert.Len(t, payload.ActionPackages, 2)
}

func TestBuildAgentPayload_InvalidModelConfig(t *testing.T) {
	metadata := minimalMetadata()
	spec := &common.AgentSpec{}
	runbook := "runbook-content"
	payload, err := cmd.BuildAgentPayload(metadata, spec, runbook, "{invalid-json}", "", "", false)
	assert.Error(t, err)
	assert.Nil(t, payload)
}

func TestBuildAgentPayload_InvalidLangSmithConfig(t *testing.T) {
	metadata := minimalMetadata()
	spec := &common.AgentSpec{}
	runbook := "runbook-content"
	payload, err := cmd.BuildAgentPayload(metadata, spec, runbook, "", "", "{invalid-json}", false)
	assert.Error(t, err)
	assert.Nil(t, payload)
}

func TestBuildAgentPayload_ActionServerConfig(t *testing.T) {
	metadata := minimalMetadata()
	spec := &common.AgentSpec{}
	runbook := "runbook-content"
	ap := map[string]interface{}{
		"Name":         "ap3",
		"Organization": "MyActions",
		"Version":      "0.2.0",
	}
	apJson, _ := json.Marshal(ap)
	payload, err := cmd.BuildAgentPayload(metadata, spec, runbook, "", string(apJson), "", false)
	assert.NoError(t, err)
	assert.NotNil(t, payload)
	assert.Equal(t, metadata[0].Name, payload.Name)
	assert.Equal(t, metadata[0].Description, payload.Description)
	assert.Equal(t, metadata[0].Version, payload.Version)
	assert.Equal(t, metadata[0].Model.Provider, payload.Model.Provider)
	assert.Equal(t, metadata[0].Model.Name, payload.Model.Name)
	assert.Equal(t, metadata[0].ConversationStarter, payload.Extra.ConversationStarter)
	assert.Equal(t, metadata[0].WelcomeMessage, payload.Extra.WelcomeMessage)
	assert.Equal(t, metadata[0].Metadata.Mode, payload.Metadata.Mode)
	if assert.Len(t, payload.ActionPackages, 3) {
		ap1 := payload.ActionPackages[0]
		ap2 := payload.ActionPackages[1]
		ap3 := payload.ActionPackages[2]
		assert.Equal(t, metadata[0].ActionPackages[0].Name, ap1.Name)
		assert.Equal(t, metadata[0].ActionPackages[0].Version, ap1.Version)
		assert.Equal(t, "MyActions", ap1.Organization)
		assert.Equal(t, metadata[0].ActionPackages[1].Name, ap2.Name)
		assert.Equal(t, metadata[0].ActionPackages[1].Version, ap2.Version)
		assert.Equal(t, "Sema4ai", ap2.Organization)
		assert.Equal(t, "ap3", ap3.Name)
		assert.Equal(t, "0.2.0", ap3.Version)
		assert.Equal(t, "MyActions", ap3.Organization)
	}
}
