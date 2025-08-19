package tests

import (
	"path/filepath"
	"testing"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/stretchr/testify/assert"
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
