package common

import (
	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common/glob"
	"os"
	"path/filepath"
	"sync"
)

type AgentChanges []string
type ActionPackagesChanges []string

type AgentProject struct {
	Path                  string                `json:"path"`
	AgentID               string                `json:"agentId"`
	Agent                 Agent                 `json:"agent"`
	Synced                bool                  `json:"synced"`
	AgentChanges          AgentChanges          `json:"agentChanges"`
	ActionPackagesChanges ActionPackagesChanges `json:"actionPackagesChanges"`
	Exclude               []string              `json:"exclude"`
}

var PATTERNS_EXCLUDED_FROM_SYNCHRONIZATION = []string{"**/__action_server_metadata__.json", "**/devdata/**", "**/__pycache__/**"}

func (ap *AgentProject) GetUnbundledActionPackageForFile(filePath string) *AgentActionPackage {
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
	// First, we want to get the files that are not excluded by the Agent configuration itself.
	includedPathsMap, err := glob.Exclude(ap.Path, ap.Exclude)
	if err != nil {
		return nil, err
	}

	includedPaths := []string{}

	for path, isDir := range includedPathsMap {
		if !isDir {
			includedPaths = append(includedPaths, path)
		}
	}

	// For synchronization, we only care about MyActions organization.
	actionsPath := AgentProjectUnbundledActionsLocation(ap.Path)
	actionsPathPattern := actionsPath + "/**"

	pathsToCheckForSync := []string{}

	// For every included path, we check if it matches the pattern for MyActions.
	// If it does, we also check whether it should be included based on the hardcoded exclusion patterns.
	for _, path := range includedPaths {
		if !glob.IsMatch(actionsPathPattern, path) {
			continue
		}

		exclude := false

		for _, pattern := range PATTERNS_EXCLUDED_FROM_SYNCHRONIZATION {
			if glob.IsMatch(pattern, path) {
				exclude = true
				break
			}
		}

		if !exclude {
			pathsToCheckForSync = append(pathsToCheckForSync, path)
		}
	}

	return pathsToCheckForSync, nil
}

func (ap *AgentProject) GetNotSynchronizedActionPackages(deployedAgent *AgentServer.Agent) ([]string, error) {
	actionPackagesPathsToCheck, err := ap.GetActionPackagesFilesForSynchronization()
	if err != nil {
		return nil, err
	}

	actionPackagesToCheck := []*AgentActionPackage{}

	for _, actionPackage := range ap.Agent.ActionPackages {
		// Only getting MyActions packages.
		if actionPackage.Organization == AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR {
			actionPackagesToCheck = append(actionPackagesToCheck, &actionPackage)
		}
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
	isEqual, agentChanges := ap.Agent.IsEqual(deployedAgent)
	notSynchronizedActionPackages, err := ap.GetNotSynchronizedActionPackages(deployedAgent)
	if err != nil {
		return err
	}

	ap.AgentChanges = agentChanges
	ap.ActionPackagesChanges = notSynchronizedActionPackages

	ap.Synced = isEqual && len(notSynchronizedActionPackages) == 0

	return nil
}
