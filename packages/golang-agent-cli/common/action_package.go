package common

import (
	"fmt"
	"os"
	"path/filepath"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"gopkg.in/yaml.v2"
)

type ActionPackageYamlDependencies struct {
	CondaForge []string `yaml:"conda-forge"`
	PyPi       []string `yaml:"pypi"`
}

type ActionPackageYamlPackaging struct {
	Exclude []string `yaml:"exclude"`
}

type ActionPackageYaml struct {
	Name         string                         `yaml:"name"`
	Description  string                         `yaml:"description"`
	Version      string                         `yaml:"version"`
	Dependencies *ActionPackageYamlDependencies `yaml:"dependencies"`
	Packaging    *ActionPackageYamlPackaging    `yaml:"packaging"`
}

type ActionPackagePaths struct {
	Action       *AgentServer.AgentActionPackage
	SourcePath   string
	TargetPath   string
	RelativePath string
}

type ActionPackageCompositeKey struct {
	ActionPackageName string
	Version           string
	Organization      string
}

func GetActionPackageYaml(packageYamlPath string) (*ActionPackageYaml, error) {
	var packageYaml *ActionPackageYaml

	rawPackageYaml, err := os.ReadFile(packageYamlPath)
	if err != nil {
		return nil, err
	}

	if err := yaml.Unmarshal(rawPackageYaml, &packageYaml); err != nil {
		return nil, err
	}

	return packageYaml, nil
}

func MapActionPackagesPathsFromAgentSpec(
	agent AgentServer.Agent,
	availableActions map[ActionPackageCompositeKey]string,
	projectPath string,
	agentProjectSpec *AgentSpec,
) ([]*ActionPackagePaths, error) {
	var actionPackagesPaths []*ActionPackagePaths

	actionPackageDirPathLookup := make(map[string]string)

	if agentProjectSpec != nil && agentProjectSpec.AgentPackage.Agents != nil {
		for _, a := range agentProjectSpec.AgentPackage.Agents {
			if a.Name == agent.Name {
				for _, ap := range a.ActionPackages {
					actionPackageDirPathLookup[ap.Name] = ap.Path
				}
			}
		}
	}

	for _, actionPackage := range agent.ActionPackages {
		source, ok := availableActions[ActionPackageCompositeKey{ActionPackageName: actionPackage.Name, Version: actionPackage.Version, Organization: actionPackage.Organization}]
		if !ok {
			return nil, fmt.Errorf("[MapActionPackagesPathshFromAgentSpec] failed to find Action Package for %s > %s > %s", actionPackage.Organization, actionPackage.Name, actionPackage.Version)
		}

		packageFolderName := filepath.Base(filepath.Dir(source))
		// If the action package folder is already in the project, use the existing path
		if existingPath, exists := actionPackageDirPathLookup[actionPackage.Name]; exists {
			packageFolderName = filepath.Base(filepath.Clean(existingPath))
		}

		var targetActionPackagePath string
		var actionRelPath string
		var actionPackageOrganization string = actionPackage.Organization

		// Added a fail safe in case the organization is empty for some reason
		if actionPackageOrganization == "" {
			actionPackageOrganization = AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR
		}

		targetActionPackagePath = filepath.Join(
			AgentProjectActionsLocation(projectPath),
			actionPackageOrganization,
			packageFolderName,
		)
		actionRelPath = filepath.Join(actionPackage.Organization, packageFolderName)

		actionPackagesPaths = append(actionPackagesPaths, &ActionPackagePaths{
			Action:       &actionPackage,
			SourcePath:   filepath.Join(source),
			TargetPath:   targetActionPackagePath,
			RelativePath: actionRelPath,
		})
	}

	return actionPackagesPaths, nil
}
