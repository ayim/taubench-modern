package tests

import (
	"path/filepath"
	"testing"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v2"
)

func TestUseExistingActionPath(t *testing.T) {
	assistant := &AgentServer.Agent{
		ActionPackages: []AgentServer.AgentActionPackage{
			{
				Name:         "test-action",
				Organization: "test-org",
				Version:      "1.0.0",
				Whitelist:    "test-action",
			},
		},
	}

	availableActions := map[common.ActionPackageCompositeKey]string{
		{
			ActionPackageName: "test-action",
			Version:           "1.0.0",
			Organization:      "test-org",
		}: "/path/to/the/test-action/1.0.0",
	}

	projectPath := "/path/to/project"

	agentProjectSpec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "1.0.0",
			Agents: []common.SpecAgent{
				{
					ActionPackages: []common.SpecAgentActionPackage{
						{
							Name:         "test-action",
							Version:      "1.0.0",
							Organization: "test-org",
							Path:         "existing/old_path",
						},
					},
				},
			},
		},
	}

	expectedSourcePath := availableActions[common.ActionPackageCompositeKey{
		ActionPackageName: "test-action",
		Version:           "1.0.0",
		Organization:      "test-org",
	}]

	actionPackagesPaths, err := common.MapActionPackagesPathsFromAgentSpec(*assistant, availableActions, projectPath, agentProjectSpec)
	assert.NoError(t, err, "Expected no error when mapping action packages paths from agent spec")
	assert.Len(t, actionPackagesPaths, 1, "Expected one action package path to be returned")
	assert.Equal(t, filepath.Join(projectPath, "actions", assistant.ActionPackages[0].Organization, "old_path"), actionPackagesPaths[0].TargetPath, "Expected target path to match the existing path in agent spec")
	assert.Equal(t, filepath.Join(assistant.ActionPackages[0].Organization, "old_path"), actionPackagesPaths[0].RelativePath, "Expected relative path to match the existing path in agent spec")
	assert.Equal(t, filepath.Join(expectedSourcePath), actionPackagesPaths[0].SourcePath, "Expected source path to match the available action path")
}

func TestExistingActionNotFound(t *testing.T) {
	assistant := &AgentServer.Agent{
		ActionPackages: []AgentServer.AgentActionPackage{
			{
				Name:         "test-action",
				Organization: "test-org",
				Version:      "1.0.0",
				Whitelist:    "test-action",
			},
		},
	}

	availableActions := map[common.ActionPackageCompositeKey]string{
		{
			ActionPackageName: "test-action",
			Version:           "1.0.0",
			Organization:      "test-org",
		}: "/path/to/the/test-action/1.0.0",
	}

	projectPath := "/path/to/project"

	agentProjectSpec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "1.0.0",
			Agents: []common.SpecAgent{
				{
					ActionPackages: []common.SpecAgentActionPackage{
						{
							Name:         "other-action",
							Version:      "1.0.0",
							Organization: "test-org",
							Path:         "existing/old_path",
						},
					},
				},
			},
		},
	}

	expectedSourcePath := availableActions[common.ActionPackageCompositeKey{
		ActionPackageName: "test-action",
		Version:           "1.0.0",
		Organization:      "test-org",
	}]

	actionPackagesPaths, err := common.MapActionPackagesPathsFromAgentSpec(*assistant, availableActions, projectPath, agentProjectSpec)
	assert.NoError(t, err, "Expected no error when mapping action packages paths from agent spec")
	assert.Len(t, actionPackagesPaths, 1, "Expected one action package path to be returned")
	assert.Equal(t, filepath.Join(projectPath, "actions", assistant.ActionPackages[0].Organization, filepath.Base(filepath.Dir(expectedSourcePath))), actionPackagesPaths[0].TargetPath, "Expected target path to match the source path")
	assert.Equal(t, filepath.Join(assistant.ActionPackages[0].Organization, assistant.ActionPackages[0].Name), actionPackagesPaths[0].RelativePath, "Expected relative path to match the action name")
	assert.Equal(t, filepath.Join(expectedSourcePath), actionPackagesPaths[0].SourcePath, "Expected source path to match the available action path")
}

func TestNoSpecFileToMapActionPath(t *testing.T) {
	assistant := &AgentServer.Agent{
		ActionPackages: []AgentServer.AgentActionPackage{
			{
				Name:         "test-action",
				Organization: "test-org",
				Version:      "1.0.0",
				Whitelist:    "test-action",
			},
		},
	}

	availableActions := map[common.ActionPackageCompositeKey]string{
		{
			ActionPackageName: "test-action",
			Version:           "1.0.0",
			Organization:      "test-org",
		}: "/path/to/the/test-action/1.0.0",
	}

	projectPath := "/path/to/project"

	expectedSourcePath := availableActions[common.ActionPackageCompositeKey{
		ActionPackageName: "test-action",
		Version:           "1.0.0",
		Organization:      "test-org",
	}]

	actionPackagesPaths, err := common.MapActionPackagesPathsFromAgentSpec(*assistant, availableActions, projectPath, nil)
	assert.NoError(t, err, "Expected no error when mapping action packages paths from agent spec")
	assert.Len(t, actionPackagesPaths, 1, "Expected one action package path to be returned")
	assert.Equal(t, filepath.Join(projectPath, "actions", assistant.ActionPackages[0].Organization, filepath.Base(filepath.Dir(expectedSourcePath))), actionPackagesPaths[0].TargetPath, "Expected target path to match the source path")
	assert.Equal(t, filepath.Join(assistant.ActionPackages[0].Organization, assistant.ActionPackages[0].Name), actionPackagesPaths[0].RelativePath, "Expected relative path to match the action name")
	assert.Equal(t, filepath.Join(expectedSourcePath), actionPackagesPaths[0].SourcePath, "Expected source path to match the available action path")
}

// TestSemanticDataModelsWithData tests that SDMs are included in the spec when they exist
func TestSemanticDataModelsWithData(t *testing.T) {
	spec := common.SpecAgent{
		Name:        "Test Agent",
		Description: "Agent with SDMs",
		Model: common.SpecAgentModel{
			Provider: "OpenAI",
			Name:     "gpt-4",
		},
		Version:      "1.0.0",
		Architecture: "agent",
		Reasoning:    "disabled",
		Runbook:      "runbook.md",
	SemanticDataModels: []common.SpecSemanticDataModel{
		{
			Name: "customer-analytics.yaml",
		},
		{
			Name: "sales-model.yaml",
		},
	},
		Metadata: AgentServer.AgentMetadata{
			Mode: "conversational",
		},
	}

	// Marshal to YAML
	data, err := yaml.Marshal(spec)
	assert.NoError(t, err, "Expected no error when marshaling spec with SDMs")

	// Unmarshal back to verify structure
	var unmarshaled common.SpecAgent
	err = yaml.Unmarshal(data, &unmarshaled)
	assert.NoError(t, err, "Expected no error when unmarshaling spec")

	// Verify SDMs are present
	assert.Len(t, unmarshaled.SemanticDataModels, 2, "Expected 2 semantic data models")
	assert.Equal(t, "customer-analytics.yaml", unmarshaled.SemanticDataModels[0].Name)
	assert.Equal(t, "sales-model.yaml", unmarshaled.SemanticDataModels[1].Name)
}

// TestSemanticDataModelsWithoutData tests that SDMs field is omitted when empty (backward compatibility)
func TestSemanticDataModelsWithoutData(t *testing.T) {
	spec := common.SpecAgent{
		Name:        "Test Agent",
		Description: "Agent without SDMs",
		Model: common.SpecAgentModel{
			Provider: "OpenAI",
			Name:     "gpt-4",
		},
		Version:            "1.0.0",
		Architecture:       "agent",
		Reasoning:          "disabled",
		Runbook:            "runbook.md",
		SemanticDataModels: nil, // No SDMs
		Metadata: AgentServer.AgentMetadata{
			Mode: "conversational",
		},
	}

	// Marshal to YAML
	data, err := yaml.Marshal(spec)
	assert.NoError(t, err, "Expected no error when marshaling spec without SDMs")

	// Convert to string to check the YAML content
	yamlStr := string(data)

	// Verify semantic-data-models field is NOT in the YAML (omitempty)
	assert.NotContains(t, yamlStr, "semantic-data-models", "Expected semantic-data-models to be omitted when nil")
}

// TestSemanticDataModelsEmptySlice tests that SDMs field is omitted when empty slice
func TestSemanticDataModelsEmptySlice(t *testing.T) {
	spec := common.SpecAgent{
		Name:        "Test Agent",
		Description: "Agent with empty SDM slice",
		Model: common.SpecAgentModel{
			Provider: "OpenAI",
			Name:     "gpt-4",
		},
		Version:            "1.0.0",
		Architecture:       "agent",
		Reasoning:          "disabled",
		Runbook:            "runbook.md",
		SemanticDataModels: []common.SpecSemanticDataModel{}, // Empty slice
		Metadata: AgentServer.AgentMetadata{
			Mode: "conversational",
		},
	}

	// Marshal to YAML
	data, err := yaml.Marshal(spec)
	assert.NoError(t, err, "Expected no error when marshaling spec with empty SDM slice")

	// Convert to string to check the YAML content
	yamlStr := string(data)

	// Verify semantic-data-models field is NOT in the YAML (omitempty)
	assert.NotContains(t, yamlStr, "semantic-data-models", "Expected semantic-data-models to be omitted when empty slice")
}

// TestSemanticDataModelStruct tests the SpecSemanticDataModel struct
func TestSemanticDataModelStruct(t *testing.T) {
	sdm := common.SpecSemanticDataModel{
		Name: "test-model.yaml",
	}

	assert.Equal(t, "test-model.yaml", sdm.Name, "Expected SDM name to match")

	// Marshal to YAML
	data, err := yaml.Marshal(sdm)
	assert.NoError(t, err, "Expected no error when marshaling SDM")

	yamlStr := string(data)
	assert.Contains(t, yamlStr, "name: test-model.yaml", "Expected name to be in YAML")

	// Unmarshal and verify
	var unmarshaled common.SpecSemanticDataModel
	err = yaml.Unmarshal(data, &unmarshaled)
	assert.NoError(t, err, "Expected no error when unmarshaling SDM")
	assert.Equal(t, "test-model.yaml", unmarshaled.Name)
}
