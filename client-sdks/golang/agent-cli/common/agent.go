package common

import (
	"fmt"
	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
)

type AgentKnowledge struct {
	Name     string `yaml:"name" json:"name"`
	Embedded bool   `yaml:"embedded" json:"embedded"`
	Digest   string `yaml:"digest" json:"digest"`
}

type AgentActionPackageType string

const (
	ActionPackageFolder AgentActionPackageType = "folder"
	ActionPackageZip    AgentActionPackageType = "zip"
)

type AgentActionPackage struct {
	Name         string                 `yaml:"name" json:"name"`
	Organization string                 `yaml:"organization" json:"organization"`
	Type         AgentActionPackageType `yaml:"type" json:"type"`
	Version      string                 `yaml:"version" json:"version"`
	Whitelist    string                 `yaml:"whitelist" json:"whitelist"`
	Path         string                 `yaml:"path" json:"path"`
}

func (a *AgentActionPackage) IsEqual(deployed *AgentServer.AgentActionPackage) bool {
	return a.Name == deployed.Name &&
		a.Organization == deployed.Organization &&
		a.Version == deployed.Version &&
		a.Whitelist == deployed.Whitelist
}

type AgentModel struct {
	Provider AgentServer.AgentModelProvider `yaml:"provider" json:"provider"`
	Name     string                         `yaml:"name" json:"name"`
}

type Agent struct {
	Name           string                        `yaml:"name" json:"name"`
	Description    string                        `yaml:"description" json:"description"`
	Model          AgentModel                    `yaml:"model" json:"model"`
	Version        string                        `yaml:"version" json:"version"`
	Architecture   AgentServer.AgentArchitecture `yaml:"architecture" json:"architecture"`
	Reasoning      AgentServer.AgentReasoning    `yaml:"reasoning" json:"reasoning"`
	Runbook        string                        `yaml:"runbook" json:"runbook"`
	ActionPackages []AgentActionPackage          `yaml:"action-packages" json:"action_packages"`
	Knowledge      []AgentKnowledge              `yaml:"knowledge" json:"knowledge"`
	Metadata       AgentServer.AgentMetadata     `yaml:"metadata" json:"metadata"`
}

func (a *Agent) IsEqual(deployed *AgentServer.Agent) (bool, AgentChanges) {
	changesMap := map[string]bool{
		"name":        a.Name == deployed.Name,
		"description": a.Description == deployed.Description,
		// From Agent Server v2 onwards, only the model provider can be selected by the user.
		// Therefore, when detecting changes, we only compare the model provider.
		"modelProvider":  a.Model.Provider == deployed.Model.Provider,
		"version":        a.Version == deployed.Version,
		"architecture":   a.Architecture == deployed.AdvancedConfig.Architecture,
		"reasoning":      a.Reasoning == deployed.AdvancedConfig.Reasoning,
		"runbook":        a.Runbook == deployed.Runbook,
		"metadata":       isMetadataEqual(a.Metadata, deployed.Metadata),
		"actionPackages": areActionPackagesEqual(a.ActionPackages, deployed.ActionPackages),
	}

	changes := AgentChanges{}

	for key, synced := range changesMap {
		if !synced {
			changes = append(changes, key)
		}
	}

	return len(changes) == 0, changes
}

func areActionPackagesEqual(local []AgentActionPackage, deployed []AgentServer.AgentActionPackage) bool {
	if len(local) != len(deployed) {
		return false
	}

	// Create maps to track which packages we've matched
	matched := make(map[int]bool)

	// For each local package, try to find a matching deployed package
	for _, localPkg := range local {
		found := false
		for j, deployedPkg := range deployed {
			if matched[j] {
				continue
			}
			if localPkg.IsEqual(&deployedPkg) {
				matched[j] = true
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	return true
}

func isMetadataEqual(project AgentServer.AgentMetadata, deployed AgentServer.AgentMetadata) bool {
	if project.Mode != deployed.Mode {
		return false
	}

	projectWorkerConfig := project.WorkerConfig
	deployedWorkerConfig := deployed.WorkerConfig

	if projectWorkerConfig == nil && deployedWorkerConfig == nil {
		return true
	}

	// Agent Server v2 is returning the WorkerConfig even if the mode is not 'worker' - in such a case, fields will be nullish.
	// Therefore, we need to check them explicitly if the projectWorkerConfig is itself null.
	if projectWorkerConfig == nil && deployedWorkerConfig.Type == "" && deployedWorkerConfig.DocumentType == "" {
		return true
	}

	if deployedWorkerConfig == nil && projectWorkerConfig.Type == "" && projectWorkerConfig.DocumentType == "" {
		return true
	}

	return projectWorkerConfig.Type == deployedWorkerConfig.Type && projectWorkerConfig.DocumentType == deployedWorkerConfig.DocumentType
}

func FindDeployedAgentById(agents []*AgentServer.Agent, agentId string) *AgentServer.Agent {
	for _, agent := range agents {
		if agent.ID == agentId {
			return agent
		}
	}

	return nil
}

type AgentPackage struct {
	SpecVersion string   `yaml:"spec-version" json:"spec_version"`
	Agents      []Agent  `yaml:"agents" json:"agents"`
	Exclude     []string `yaml:"exclude" json:"exclude"`
}

type AgentSpec struct {
	AgentPackage AgentPackage `yaml:"agent-package" json:"agent_package"`
}

func GetAgentByName(name, serverURL string) (*AgentServer.Agent, error) {
	client := AgentServer.NewClient(serverURL)
	agents, err := client.GetAgents(false)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch agents: %w", err)
	}

	for _, a := range *agents {
		if a.Name == name {
			return &a, nil
		}
	}

	return nil, fmt.Errorf("agent not found: %s", name)
}
