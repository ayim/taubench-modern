package common

import (
	"os"
	"path/filepath"
	"sync"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common/glob"
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
)

type AgentChanges []string
type ActionPackagesChanges []string

type AgentProject struct {
	Path                  string                `json:"path"`
	AgentID               string                `json:"agentId"`
	Agent                 SpecAgent             `json:"agent"`
	Synced                bool                  `json:"synced"`
	AgentChanges          AgentChanges          `json:"agentChanges"`
	ActionPackagesChanges ActionPackagesChanges `json:"actionPackagesChanges"`
	Exclude               []string              `json:"exclude"`
}

var PATTERNS_EXCLUDED_FROM_SYNCHRONIZATION = []string{"**/__action_server_metadata__.json", "**/devdata/**", "**/__pycache__/**"}

func excludeByHardcodedPatters(path string) bool {
	for _, pattern := range PATTERNS_EXCLUDED_FROM_SYNCHRONIZATION {
		if glob.IsMatch(pattern, path) {
			return true
		}
	}

	return false
}

func (ap *AgentProject) GetUnbundledActionPackageForFile(filePath string) *SpecAgentActionPackage {
	for _, actionPackage := range ap.Agent.ActionPackages {
		packagePath := filepath.Join(AgentProjectActionsLocation(ap.Path), actionPackage.Path)
		packagePathPattern := packagePath + "/**"

		if glob.IsMatch(packagePathPattern, filePath) {
			return &actionPackage
		}
	}

	return nil
}

func (ap *AgentProject) GetActionPackagesFilesForSynchronization() ([]string, error) {
	includedPaths := &ConcurrentSlice[string]{
		items: []string{},
	}

	var getFilesErrors []error

	wg := sync.WaitGroup{}

	var myActionsPackages []SpecAgentActionPackage

	for _, actionPackage := range ap.Agent.ActionPackages {
		if actionPackage.Organization == AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR {
			myActionsPackages = append(myActionsPackages, actionPackage)
		}
	}

	for _, actionPackage := range myActionsPackages {
		wg.Add(1)

		go func() {
			defer wg.Done()

			packagePath := filepath.Join(AgentProjectActionsLocation(ap.Path), actionPackage.Path)

			packageYaml, err := GetActionPackageYaml(filepath.Join(packagePath, ACTION_PACKAGE_SPEC_FILE))
			if err != nil {
				getFilesErrors = append(getFilesErrors, err)
				return
			}

			exclusionRules := packageYaml.Packaging.Exclude

			includedPathsMap, err := glob.Exclude(packagePath, exclusionRules)
			if err != nil {
				getFilesErrors = append(getFilesErrors, err)
				return
			}

			for path, isDir := range includedPathsMap {
				// For every included path, we want to filter out directory items and files that follow hardcoded
				// exclusion patterns.
				if !isDir && !excludeByHardcodedPatters(path) {
					includedPaths.AddIfNotExists(path)
				}
			}
		}()
	}

	wg.Wait()

	if len(getFilesErrors) > 0 {
		return nil, ConcatErrors(getFilesErrors)
	}

	return includedPaths.items, nil
}

func (ap *AgentProject) GetNotSynchronizedActionPackages(deployedAgent *AgentServer.Agent) ([]string, error) {
	actionPackagesPathsToCheck, err := ap.GetActionPackagesFilesForSynchronization()
	if err != nil {
		return nil, err
	}

	notSynchronizedActionPackages := &ConcurrentSlice[string]{
		items: []string{},
	}
	var filesCheckErrors []error

	wg := sync.WaitGroup{}

	// For every path that would require synchronization, we check if the last modified timestamp of the file
	// is after the timestamp of the last Agent deployment. If it is, we mark the Action Package as needing synchronization.
	for _, path := range actionPackagesPathsToCheck {
		wg.Add(1)

		go func() {
			defer wg.Done()

			stats, err := os.Stat(path)
			if err != nil {
				filesCheckErrors = append(filesCheckErrors, err)
			}

			if stats.ModTime().After(deployedAgent.UpdatedAt) {
				actionPackage := ap.GetUnbundledActionPackageForFile(path)

				if actionPackage != nil {
					notSynchronizedActionPackages.AddIfNotExists(actionPackage.Name)
				}
			}
		}()
	}

	wg.Wait()

	if len(filesCheckErrors) > 0 {
		return nil, ConcatErrors(filesCheckErrors)
	}

	return notSynchronizedActionPackages.items, nil
}

func (ap *AgentProject) ApplySynchronizationStatus(deployedAgent *AgentServer.Agent) error {
	isEqual, agentChanges := ap.Agent.IsEqual(ap, deployedAgent)
	notSynchronizedActionPackages, err := ap.GetNotSynchronizedActionPackages(deployedAgent)
	if err != nil {
		return err
	}

	ap.AgentChanges = agentChanges
	ap.ActionPackagesChanges = notSynchronizedActionPackages

	ap.Synced = isEqual && len(notSynchronizedActionPackages) == 0

	return nil
}
