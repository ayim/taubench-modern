package common

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type AgentProjectSettings struct {
	AgentId     string `json:"agentId"`
	ProjectPath string `json:"projectPath"`
	UpdatedAt   string `json:"updatedAt"`
}

type AgentProjectSettingsMap map[string]*AgentProjectSettings

func (a AgentProjectSettingsMap) GetEntryByProjectPath(path string) *AgentProjectSettings {
	cleanTargetPath := filepath.Clean(path)

	for _, entry := range a {
		if filepath.Clean(entry.ProjectPath) == cleanTargetPath {
			return entry
		}
	}

	return nil
}

func ReadAgentProjectSettings(path string) (AgentProjectSettingsMap, error) {
	contents, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read agent project settings: %w", err)
	}

	var settingsMap AgentProjectSettingsMap

	err = json.Unmarshal(contents, &settingsMap)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal agent project settings: %w", err)
	}

	return settingsMap, nil
}
