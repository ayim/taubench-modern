package common

import (
	"os"
	"path/filepath"
)

const (
	AGENT_PROJECT_DEFAULT_NAME          = `agent-project`
	AGENT_PACKAGE_DEFAULT_NAME          = `agent-package.zip`
	AGENT_PACKAGE_METADATA_FILE         = `__agent_package_metadata__.json`
	AGENT_PROJECT_SPEC_FILE             = `agent-spec.yaml`
	HOME_VARIABLE                       = `SEMA4AI_HOME`
	S4S_DEV_MODE_EXE_PATH               = `S4S_DEV_MODE_EXE_PATH`
	S4S_ACTIONS_GALLERY_DIR             = `gallery`
	S4S_BUNDLED_ACTIONS_DIR             = `Sema4.ai`
	S4S_UNBUNDLED_ACTIONS_DIR           = `MyActions`
	S4S_BACKEND_DEFAULT_URL             = `http://localhost:8000`
	AGENT_PROJECT_KNOWLEDGE_DIR         = `knowledge`
	AGENT_PROJECT_RUNBOOKS_DIR          = `runbooks`
	AGENT_PROJECT_ACTIONS_DIR           = `actions`
	AGENT_PROJECT_BUNDLED_ACTIONS_DIR   = `Sema4.ai`
	AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR = `MyActions`
	AGENT_PROJECT_RUNBOOK_FILE          = `runbook.md`
	ACTION_PACKAGE_SPEC_FILE            = `package.yaml`
	ACTION_PACKAGE_METADATA_FILE        = `__action_server_metadata__.json`
	ACTION_PACKAGE_ICON_FILE            = `package.png`
	ACTION_SERVER_BIN_PATH_ENV_VARIABLE = `ACTION_SERVER_BIN_PATH`
	// Need at least 0.18.0, so that `action-server package metadata`
	// includes action package versions.
	MIN_ACTION_SERVER_VERSION = "2.3.0"
)

const DEFAULT_RUNBOOK = `You are a helpful assistant.`

func Home() string {
	home := os.Getenv(HOME_VARIABLE)
	if len(home) > 0 {
		return ExpandPath(home)
	}
	return ExpandPath(defaultHomeLocation)
}

func S4SLocation() string {
	devMode := os.Getenv(S4S_DEV_MODE_EXE_PATH)
	if len(devMode) > 0 {
		return ExpandPath(devMode)
	}
	return filepath.Join(Home(), "sema4ai-studio")
}

func S4SActionsGalleryLocation() string {
	return filepath.Join(S4SLocation(), S4S_ACTIONS_GALLERY_DIR)
}

func S4SBundledActionsLocation() string {
	return filepath.Join(S4SLocation(), S4S_ACTIONS_GALLERY_DIR, S4S_BUNDLED_ACTIONS_DIR)
}

func S4SUnbundledActionsLocation() string {
	return filepath.Join(S4SLocation(), S4S_ACTIONS_GALLERY_DIR, S4S_UNBUNDLED_ACTIONS_DIR)
}

func AgentProjectActionsLocation(projectPath string) string {
	return filepath.Join(projectPath, AGENT_PROJECT_ACTIONS_DIR)
}

func AgentProjectBundledActionsLocation(projectPath string) string {
	return filepath.Join(AgentProjectActionsLocation(projectPath), AGENT_PROJECT_BUNDLED_ACTIONS_DIR)
}

func AgentProjectUnbundledActionsLocation(projectPath string) string {
	return filepath.Join(AgentProjectActionsLocation(projectPath), AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR)
}

func AgentProjectKnowledgeLocation(projectPath string) string {
	return filepath.Join(projectPath, AGENT_PROJECT_KNOWLEDGE_DIR)
}

func AgentProjectRunbookFileLocation(projectPath string) string {
	return filepath.Join(projectPath, AGENT_PROJECT_RUNBOOK_FILE)
}

func AgentProjectSpecFileLocation(projectPath string) string {
	return filepath.Join(projectPath, AGENT_PROJECT_SPEC_FILE)
}

func AgentProjectBundledActionRelPath(actionDir string) string {
	return filepath.Join(AGENT_PROJECT_BUNDLED_ACTIONS_DIR, actionDir)
}

func AgentProjectUnbundledActionRelPath(actionDir string) string {
	return filepath.Join(AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR, actionDir)
}
