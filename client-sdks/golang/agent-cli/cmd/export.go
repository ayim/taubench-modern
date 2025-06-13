package cmd

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
	"golang.org/x/mod/semver"
	"gopkg.in/yaml.v2"
)

var (
	agentName      string
	agentServerURL string
	agentVersion   string
)

// Keys are agent ids.
type specState struct {
	assistantKnowledge      map[string][]common.AgentKnowledge
	assistantActionPackages map[string][]common.AgentActionPackage
	assistantRunbooks       map[string]string
}

type ActionPackageCompositeKey struct {
	ActionPackageName string
	version           string
	Organization      string
}

// safeAgentString returns a sanitized string representation of an Agent
// that is safe for logging without exposing sensitive information
func safeAgentString(agent *AgentServer.Agent) string {
	if agent == nil {
		return "<nil>"
	}
	return fmt.Sprintf("{ID: %s, Name: %s, Version: %s, NumFiles: %d, NumActions: %d}",
		agent.ID,
		agent.Name,
		agent.Version,
		len(agent.Files),
		len(agent.ActionPackages))
}

func (state *specState) specForAgent(assistant AgentServer.Agent) common.Agent {
	metadata := assistant.Metadata

	// Ensuring WorkerConfig is not included in the spec if the agent type is "conversational".
	if metadata.Mode == "conversational" {
		metadata.WorkerConfig = nil
	}

	return common.Agent{
		Name:        assistant.Name,
		Description: assistant.Description,
		Model: common.AgentModel{
			Provider: assistant.Model.Provider,
			Name:     assistant.Model.Name,
		},
		Version:        assistant.Version,
		Architecture:   assistant.AdvancedConfig.Architecture,
		Reasoning:      assistant.AdvancedConfig.Reasoning,
		Runbook:        state.assistantRunbooks[assistant.ID],
		ActionPackages: state.assistantActionPackages[assistant.ID],
		Knowledge:      state.assistantKnowledge[assistant.ID],
		Metadata:       metadata,
	}
}

func (state *specState) createSpecFile(assistants []AgentServer.Agent, projectPath string) error {
	agents := []common.Agent{}
	for _, assistant := range assistants {
		agents = append(agents, state.specForAgent(assistant))
	}

	agentPackage := common.AgentPackage{
		SpecVersion: "v2",
		Agents:      agents,
		Exclude: []string{
			"./.git/**",
			"./.vscode/**",
			"./devdata/**",
			"./output/**",
			"./venv/**",
			"./.venv/**",
			"./**/.env",
			"./**/.DS_Store",
			"./**/*.pyc",
			"./*.zip",
		},
	}

	agentSpec := common.AgentSpec{
		AgentPackage: agentPackage,
	}

	specData, err := yaml.Marshal(agentSpec)
	if err != nil {
		return fmt.Errorf("[createSpecFile] failed to marshal YAML: %w", err)
	}

	specPath := common.AgentProjectSpecFileLocation(projectPath)
	err = pathlib.WriteFile(specPath, specData, 0o644)
	if err != nil {
		return fmt.Errorf("[createSpecFile] failed to write spec YAML file: %w", err)
	}
	logVerbose("Created Spec file @: %s", specPath)
	return nil
}

func processOrganization(orgPath string, availableActions map[ActionPackageCompositeKey]string) error {
	// Get the organization name from the file, because it is not in the metadata
	// TODO: The metadata needs some fixing
	_, orgName := filepath.Split(orgPath)

	entries, err := os.ReadDir(orgPath)
	if err != nil {
		return fmt.Errorf("[processOrganization] failed to read directory %s: %w", orgPath, err)
	}

	logVerbose("Processing Organization @: %s", orgPath)

	for _, entry := range entries {
		// Skip non-directory entries like .DS_Store
		if !entry.IsDir() {
			continue
		}

		// entry is the Action Package - which is an umbrella directory
		// the umbrella dir contains folders that are versions
		actionPackageVersionPath := filepath.Join(
			orgPath,
			entry.Name(),
		)
		versions, err := os.ReadDir(actionPackageVersionPath)
		if err != nil {
			return fmt.Errorf("[processOrganization] failed to read package version directory %s: %w", actionPackageVersionPath, err)
		}

		for _, version := range versions {
			if version.IsDir() {
				actionPackageSpecPath := filepath.Join(
					actionPackageVersionPath, version.Name(), common.ACTION_PACKAGE_SPEC_FILE,
				)

				// package.yaml file must exist, or the folder is not an action package
				if _, err := os.Stat(actionPackageSpecPath); os.IsNotExist(err) {
					continue
				}
				rawActionPackageSpec, err := os.ReadFile(actionPackageSpecPath)
				if err != nil {
					// package.yaml exists, but cannot be read
					return fmt.Errorf("[processOrganization] failed to read package.yaml. err: %w at: %s", err, actionPackageSpecPath)
				}
				var actionPackageSpec map[string]interface{}
				if err := yaml.Unmarshal(rawActionPackageSpec, &actionPackageSpec); err != nil {
					// package.yaml read, but invalid YAML
					return fmt.Errorf("[processOrganization] invalid package.yaml. err: %w at: %s", err, actionPackageSpecPath)
				}

				actionPackageName := actionPackageSpec["name"].(string)
				availableActions[ActionPackageCompositeKey{ActionPackageName: actionPackageName, version: version.Name(), Organization: orgName}] = filepath.Join(actionPackageVersionPath, version.Name())
			}
		}
	}
	return nil
}

// Returns a map of available action packages, where the key is the action package name
// and the value is the path to the action package directory.
func createAvailableActionPackagesMap() (map[ActionPackageCompositeKey]string, error) {
	availableActions := make(map[ActionPackageCompositeKey]string)

	galleryRootDir := common.S4SActionsGalleryLocation()

	if _, err := os.Stat(galleryRootDir); err == nil {
		organizations, err := os.ReadDir(galleryRootDir)
		if err != nil {
			return nil, err
		}

		for _, org := range organizations {
			// Skip non-directory entries like .DS_Store
			if !org.IsDir() {
				continue
			}

			orgFolderPath := filepath.ToSlash(filepath.Join(
				galleryRootDir,
				org.Name(),
			))
			if err := processOrganization(orgFolderPath, availableActions); err != nil {
				return nil, err
			}
		}
	}

	return availableActions, nil
}

func (state *specState) createKnowledgeDir(assistants []AgentServer.Agent, projectPath string) error {
	filesPath := common.AgentProjectKnowledgeLocation(projectPath)
	err := os.MkdirAll(filesPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createKnowledgeDir] failed to create files directory: %w", err)
	}

	logVerbose("Creating Knowledge directory @: %s", filesPath)
	for _, assistant := range assistants {
		Files, err := copyFilesFor(assistant, filesPath)
		if err != nil {
			return err
		}
		state.assistantKnowledge[assistant.ID] = Files
	}
	return nil
}

func copyFilesFor(assistant AgentServer.Agent, filesPath string) ([]common.AgentKnowledge, error) {
	ret := []common.AgentKnowledge{}
	for _, file := range assistant.Files {
		sourcePath := file.FilePath
		if strings.HasPrefix(sourcePath, "file://") {
			sourcePath = strings.TrimPrefix(sourcePath, "file://")
		}
		target := filepath.Join(filesPath, filepath.Base(sourcePath))
		actualTarget, err := common.CopyFileWithUniqueName(sourcePath, target)
		if err != nil {
			return nil, fmt.Errorf("[copyFilesFor] failed to copy file %s: %w", sourcePath, err)
		}
		digest, err := generateDigest(actualTarget)
		if err != nil {
			return nil, fmt.Errorf("[copyFilesFor] failed to generate digest for file %s: %w", actualTarget, err)
		}
		ret = append(ret, common.AgentKnowledge{
			Name:     filepath.Base(actualTarget),
			Embedded: file.Embedded,
			Digest:   digest,
		})
	}
	return ret, nil
}

func generateDigest(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}

	hashInBytes := hash.Sum(nil)
	hashString := hex.EncodeToString(hashInBytes)

	return hashString, nil
}

func copyActionPackagesFor(
	assistant AgentServer.Agent,
	availableActions map[ActionPackageCompositeKey]string,
	projectPath string,
) ([]common.AgentActionPackage, error) {
	var actionPackages []common.AgentActionPackage

	for _, actionPackage := range assistant.ActionPackages {
		source, ok := availableActions[ActionPackageCompositeKey{ActionPackageName: actionPackage.Name, version: actionPackage.Version, Organization: actionPackage.Organization}]
		if !ok {
			return nil, fmt.Errorf("[copyActionPackagesFor] failed to find Action Package for %s > %s > %s", actionPackage.Organization, actionPackage.Name, actionPackage.Version)
		}

		packageFolderName := filepath.Base(filepath.Dir(source))
		logVerbose("[copyActionPackagesFor] Processing source: %s", source)
		logVerbose("[copyActionPackagesFor] Package folder: %s", packageFolderName)

		var targetActionPackagePath string
		var actionRelPath string
		var actionPackageOrganization string = actionPackage.Organization

		// Added a fail safe in case the organization is empty for some reason
		if actionPackageOrganization == "" {
			actionPackageOrganization = common.AGENT_PROJECT_UNBUNDLED_ACTIONS_DIR
		}

		targetActionPackagePath = filepath.Join(
			common.AgentProjectActionsLocation(projectPath),
			actionPackageOrganization,
			packageFolderName,
		)
		actionRelPath = filepath.Join(actionPackage.Organization, packageFolderName)

		logVerbose("[copyActionPackagesFor] Target Action Package Path: %s", targetActionPackagePath)
		logVerbose("[copyActionPackagesFor] Relative Path: %s", actionRelPath)

		actionPackages = append(actionPackages, common.AgentActionPackage{
			Name:         actionPackage.Name,
			Organization: actionPackage.Organization,
			Path:         filepath.ToSlash(actionRelPath),
			Type:         common.ActionPackageFolder,
			Version:      actionPackage.Version,
			Whitelist:    actionPackage.Whitelist,
		})

		if err := common.CopyDir(source, targetActionPackagePath, true); err != nil {
			return nil, fmt.Errorf("[copyActionPackagesFor] failed to copy directory %s to %s: %w", source, targetActionPackagePath, err)
		}
		logVerbose("[copyActionPackagesFor] [DONE] Action Package was copied successfully!")
	}

	return actionPackages, nil
}

func (state *specState) createActionsDir(assistants []AgentServer.Agent, projectPath string) error {
	bundledActionsPath := common.AgentProjectBundledActionsLocation(projectPath)
	err := os.MkdirAll(bundledActionsPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createActionsDir] failed to create bundled actions directory: %w", err)
	}
	logVerbose("Created Sema4.ai Actions directory @: %s", bundledActionsPath)

	unbundledActionsPath := common.AgentProjectUnbundledActionsLocation(projectPath)
	err = os.MkdirAll(unbundledActionsPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createActionsDir] failed to create unbundled actions directory: %w", err)
	}
	logVerbose("Created MyActions directory @: %s", unbundledActionsPath)

	availableActions, err := createAvailableActionPackagesMap()
	if err != nil {
		return err
	}
	logVerbose("Available local actions: %+v", availableActions)

	for _, assistant := range assistants {
		logVerbose("Copying actions for agent: %s", safeAgentString(&assistant))
		actions, err := copyActionPackagesFor(
			assistant,
			availableActions,
			projectPath,
		)
		if err != nil {
			return err
		}
		state.assistantActionPackages[assistant.ID] = actions
	}

	return nil
}

func (state *specState) createRunbookFile(assistants []AgentServer.Agent, projectPath string) error {
	runbookPath := common.AgentProjectRunbookFileLocation(projectPath)
	for _, assistant := range assistants {
		logVerbose("Extracting runbook for: %s", safeAgentString(&assistant))
		err := pathlib.WriteFile(
			runbookPath, []byte(assistant.Runbook), 0o644,
		)
		if err != nil {
			return err
		}
		state.assistantRunbooks[assistant.ID] = filepath.Base(runbookPath)
	}
	return nil
}

func createAgentProject(assistants []AgentServer.Agent, projectPath string) error {
	if projectPath == "" {
		return fmt.Errorf("[createAgentProject] project path cannot be empty")
	}

	logVerbose("Creating Agent Project to path: %s", projectPath)
	if pathlib.Exists(projectPath) && !pathlib.IsEmptyDir(projectPath) {
		return fmt.Errorf("[createAgentProject] project directory %s already exists and is not empty", projectPath)
	}

	err := os.MkdirAll(projectPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createAgentProject] failed to create agent project directory: %w", err)
	}

	state := specState{
		assistantKnowledge:      map[string][]common.AgentKnowledge{},
		assistantActionPackages: map[string][]common.AgentActionPackage{},
		assistantRunbooks:       map[string]string{},
	}

	err = state.createKnowledgeDir(assistants, projectPath)
	if err != nil {
		return err
	}

	err = state.createActionsDir(assistants, projectPath)
	if err != nil {
		return err
	}

	err = state.createRunbookFile(assistants, projectPath)
	if err != nil {
		return err
	}

	err = state.createSpecFile(assistants, projectPath)
	if err != nil {
		return err
	}

	return nil
}

func getAgent(agentName string, client *AgentServer.Client) (*AgentServer.Agent, error) {
	agents, err := client.GetAgents(false)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch agents: %w", err)
	}
	for _, a := range *agents {
		if a.Name == agentName {
			return &a, nil
		}
	}
	return nil, nil
}

var exportCmd = &cobra.Command{
	Use:   "export",
	Short: "Create a new project by exporting an existing agent from Sema4.ai Studio.",
	Long:  "Create a new project by exporting an existing agent from Sema4.ai Studio.",
	RunE: func(cmd *cobra.Command, args []string) error {
		// semver package expects that all versions have a "v" prefix.
		if agentVersion != "" && !semver.IsValid("v"+agentVersion) {
			return fmt.Errorf("[exportCmd] agent version %s is not a valid semver", agentVersion)
		}

		client := AgentServer.NewClient(agentServerURL)
		agent, err := getAgent(agentName, client)
		if err != nil {
			return err
		}
		if agent == nil {
			return fmt.Errorf("[exportCmd] agent '%s' not found", agentName)
		}
		assistants, err := client.GetAgentsWithFiles([]string{agent.ID}, true)
		if err != nil {
			return err
		}

		// This is a workaround solution for 1.0 release.
		for i := range assistants {
			if agentVersion != "" {
				logVerbose(
					"Overwriting version %s for agent '%s' with %s",
					assistants[i].Version,
					assistants[i].Name,
					agentVersion,
				)
				assistants[i].Version = agentVersion
			}
		}

		err = createAgentProject(assistants, agentProjectPath)
		if err != nil {
			return err
		}

		return nil
	},
}

func init() {
	projectCmd.AddCommand(exportCmd)
	exportCmd.Flags().StringVar(&agentName, "agent", "", "The name of the agent to export.")
	exportCmd.MarkFlagRequired("agent")
	exportCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path")
	exportCmd.Flags().StringVar(&agentVersion, "overwrite-version", "", "Overwrite the agent version")
	exportCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
}
