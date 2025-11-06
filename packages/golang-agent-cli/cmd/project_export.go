package cmd

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
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
type SpecState struct {
	assistantKnowledge          map[string][]common.SpecAgentKnowledge
	assistantActionPackages     map[string][]common.SpecAgentActionPackage
	assistantMcpServer          map[string][]common.SpecMcpServer
	AssistantDockerMcpGateway   map[string]*common.SpecDockerMcpGateway
	assistantRunbooks           map[string]string
	AssistantConversationGuides map[string]string
	assistantSemanticDataModels map[string][]common.SpecSemanticDataModel
}

// safeAgentString returns a sanitized string representation of an Agent
// that is safe for logging without exposing sensitive information
func safeAgentString(agent *AgentServer.Agent) string {
	if agent == nil {
		return "<nil>"
	}
	return fmt.Sprintf("{ID: %s, Name: %s, Version: %s, NumFiles: %d, NumActions: %d, NumMcpServers: %d}",
		agent.ID,
		agent.Name,
		agent.Version,
		len(agent.Files),
		len(agent.ActionPackages),
		len(agent.McpServers),
	)
}

func (state *SpecState) MergeDockerMcpGateway(originalSpec *common.AgentSpec, assistantAgent AgentServer.Agent) *common.SpecDockerMcpGateway {
	var mergedGateway *common.SpecDockerMcpGateway

	// If the assistant's DockerMcpGateway is nil, return nil
	if state.AssistantDockerMcpGateway[assistantAgent.ID] == nil {
		return nil
	}

	// If the original spec is provided, use it to merge the DockerMcpGateway
	if originalSpec != nil {
		for _, originalAgent := range originalSpec.AgentPackage.Agents {
			if originalAgent.Name == assistantAgent.Name && originalAgent.DockerMcpGateway != nil {
				mergedGateway = originalAgent.DockerMcpGateway

				assistantDockerMcpGateway := state.AssistantDockerMcpGateway[assistantAgent.ID]
				if assistantDockerMcpGateway != nil {
					for name, assistantServer := range assistantDockerMcpGateway.Servers {
						if mergedGateway.Servers == nil {
							mergedGateway.Servers = make(map[string]common.SpecDockerMcpServer)
						}
						if _, ok := mergedGateway.Servers[name]; !ok {
							mergedGateway.Servers[name] = assistantServer
						}
					}
				}
			}
		}
	} else {
		return state.AssistantDockerMcpGateway[assistantAgent.ID]
	}

	// If we haven't set anything, use the assistant's DockerMcpGateway
	if mergedGateway == nil {
		return state.AssistantDockerMcpGateway[assistantAgent.ID]
	}
	return mergedGateway
}

func (state *SpecState) specForAgent(assistant AgentServer.Agent, projectPath string) common.SpecAgent {
	metadata := assistant.Metadata

	var originalSpec *common.AgentSpec
	// If the spec read fails, for whatever reason, we ignore the original spec
	originalSpec, _ = ReadSpec(projectPath)
	mergedDockerMcpGateway := state.MergeDockerMcpGateway(originalSpec, assistant)

	// Ensuring WorkerConfig is not included in the spec if the agent type is "conversational".
	if metadata.Mode == "conversational" {
		metadata.WorkerConfig = nil
	}
	if metadata.WelcomeMessage != "" {
		metadata.WelcomeMessage = ""
	}
	if metadata.QuestionGroups != nil {
		metadata.QuestionGroups = nil
	}

	// Convert selected_tools from agent to spec format
	var specSelectedTools common.SpecSelectedTools
	for _, toolConfig := range assistant.SelectedTools.ToolNames {
		specSelectedTools.Tools = append(specSelectedTools.Tools, common.SpecSelectedToolConfig{
			Name: toolConfig.ToolName,
		})
	}

	return common.SpecAgent{
		Name:        assistant.Name,
		Description: assistant.Description,
		Model: common.SpecAgentModel{
			Provider: assistant.Model.Provider,
			Name:     assistant.Model.Name,
		},
		Version:              assistant.Version,
		Architecture:         assistant.AdvancedConfig.Architecture,
		Reasoning:            assistant.AdvancedConfig.Reasoning,
		Runbook:              state.assistantRunbooks[assistant.ID],
		ConversationGuide:    state.AssistantConversationGuides[assistant.ID],
		ConversationStarter:  assistant.Extra.ConversationStarter,
		DocumentIntelligence: assistant.Extra.DocumentIntelligence,
		WelcomeMessage: func() string {
			// TODO: remove this once we have a proper welcome message field in the agent
			// - done for backwards compatibility
			if assistant.Extra.WelcomeMessage != "" {
				return assistant.Extra.WelcomeMessage
			}
			return assistant.Metadata.WelcomeMessage
		}(),
		AgentSettings:      common.NormalizeMap(assistant.Extra.AgentSettings),
		ActionPackages:     state.assistantActionPackages[assistant.ID],
		McpServers:         state.assistantMcpServer[assistant.ID],
		DockerMcpGateway:   mergedDockerMcpGateway,
		Knowledge:          state.assistantKnowledge[assistant.ID],
		SemanticDataModels: state.assistantSemanticDataModels[assistant.ID],
		Metadata:           metadata,
		SelectedTools:      specSelectedTools,
	}
}

func (state *SpecState) createSpecFile(assistants []AgentServer.Agent, projectPath string) error {
	agents := []common.SpecAgent{}
	for _, assistant := range assistants {
		agents = append(agents, state.specForAgent(assistant, projectPath))
	}

	agentPackage := common.SpecAgentPackage{
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

	if err := WriteSpec(&agentSpec, projectPath); err != nil {
		return fmt.Errorf("[createSpecFile] failed to write spec YAML file: %w", err)
	}
	pretty.LogIfVerbose("[createSpecFile] created agent spec file @: %s", projectPath)
	return nil
}

func processOrganization(orgPath string, availableActions map[common.ActionPackageCompositeKey]string) error {
	// Get the organization name from the file, because it is not in the metadata
	// TODO: The metadata needs some fixing
	_, orgName := filepath.Split(orgPath)

	entries, err := os.ReadDir(orgPath)
	if err != nil {
		return fmt.Errorf("[processOrganization] failed to read directory %s: %w", orgPath, err)
	}

	pretty.LogIfVerbose("[processOrganization] @: %s", orgPath)

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
				availableActions[common.ActionPackageCompositeKey{ActionPackageName: actionPackageName, Version: version.Name(), Organization: orgName}] = filepath.Join(actionPackageVersionPath, version.Name())
			}
		}
	}
	return nil
}

// Returns a map of available action packages, where the key is the action package name
// and the value is the path to the action package directory.
func createAvailableActionPackagesMap() (map[common.ActionPackageCompositeKey]string, error) {
	availableActions := make(map[common.ActionPackageCompositeKey]string)

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

func (state *SpecState) createKnowledgeDir(assistants []AgentServer.Agent, projectPath string) error {
	filesPath := common.AgentProjectKnowledgeLocation(projectPath)
	err := os.MkdirAll(filesPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createKnowledgeDir] failed to create files directory: %w", err)
	}

	for _, assistant := range assistants {
		Files, err := copyFilesFor(assistant, filesPath)
		if err != nil {
			return err
		}
		state.assistantKnowledge[assistant.ID] = Files
	}
	pretty.LogIfVerbose("[createKnowledgeDir] @: %s", filesPath)
	return nil
}

func copyFilesFor(assistant AgentServer.Agent, filesPath string) ([]common.SpecAgentKnowledge, error) {
	ret := []common.SpecAgentKnowledge{}
	for _, file := range assistant.Files {
		sourcePath := file.FilePath
		if after, ok := strings.CutPrefix(sourcePath, "file://"); ok {
			sourcePath = after
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
		ret = append(ret, common.SpecAgentKnowledge{
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
	availableActions map[common.ActionPackageCompositeKey]string,
	projectPath string,
	agentProjectSpec *common.AgentSpec,
) ([]common.SpecAgentActionPackage, error) {
	var actionPackages []common.SpecAgentActionPackage

	actionPackagesPaths, err := common.MapActionPackagesPathsFromAgentSpec(assistant, availableActions, projectPath, agentProjectSpec)
	if err != nil {
		return nil, err
	}

	for _, actionPackagePaths := range actionPackagesPaths {
		pretty.LogIfVerbose("[copyActionPackagesFor] target Action Package Path: %s", actionPackagePaths.TargetPath)
		pretty.LogIfVerbose("[copyActionPackagesFor] relative Path: %s", actionPackagePaths.RelativePath)

		actionPackages = append(actionPackages, common.SpecAgentActionPackage{
			Name:         actionPackagePaths.Action.Name,
			Organization: actionPackagePaths.Action.Organization,
			Path:         filepath.ToSlash(actionPackagePaths.RelativePath),
			Type:         common.ActionPackageFolder,
			Version:      actionPackagePaths.Action.Version,
			Whitelist:    actionPackagePaths.Action.Whitelist,
		})

		if err := common.CopyDir(actionPackagePaths.SourcePath, actionPackagePaths.TargetPath, true); err != nil {
			return nil, fmt.Errorf("[copyActionPackagesFor] failed to copy directory %s to %s: %w", actionPackagePaths.SourcePath, actionPackagePaths.TargetPath, err)
		}
		pretty.LogIfVerbose("[copyActionPackagesFor] [DONE] action Package was copied successfully!")
	}

	return actionPackages, nil
}

func (state *SpecState) createActionsDir(assistants []AgentServer.Agent, projectPath string) error {
	bundledActionsPath := common.AgentProjectBundledActionsLocation(projectPath)
	err := os.MkdirAll(bundledActionsPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createActionsDir] failed to create bundled actions directory: %w", err)
	}
	pretty.LogIfVerbose("[createActionsDir] created Sema4.ai Actions directory @: %s", bundledActionsPath)

	unbundledActionsPath := common.AgentProjectUnbundledActionsLocation(projectPath)
	err = os.MkdirAll(unbundledActionsPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createActionsDir] failed to create unbundled actions directory: %w", err)
	}
	pretty.LogIfVerbose("[createActionsDir] created MyActions directory @: %s", unbundledActionsPath)

	availableActions, err := createAvailableActionPackagesMap()
	if err != nil {
		return err
	}
	pretty.LogIfVerbose("[createActionsDir] available local actions: %+v", availableActions)

	// Use agent-spec for action package naming if available
	agentProjectSpec, err := getAgentProjectSpec(projectPath)
	if err != nil {
		pretty.LogIfVerbose("[createActionsDir] agent spec not available %s: %s", projectPath, err)
	}

	for _, assistant := range assistants {
		pretty.LogIfVerbose("[createActionsDir] copying actions for agent: %s", safeAgentString(&assistant))
		actions, err := copyActionPackagesFor(
			assistant,
			availableActions,
			projectPath,
			agentProjectSpec,
		)
		if err != nil {
			return err
		}
		state.assistantActionPackages[assistant.ID] = actions
	}

	pretty.LogIfVerbose("[createActionsDir] actions are ready!")
	return nil
}

func (state *SpecState) createRunbookFile(assistants []AgentServer.Agent, projectPath string) error {
	runbookPath := common.AgentProjectRunbookFileLocation(projectPath)
	for _, assistant := range assistants {
		pretty.LogIfVerbose("[createActionsDir] extracting runbook for: %s", safeAgentString(&assistant))
		err := pathlib.WriteFile(
			runbookPath, []byte(assistant.Runbook), 0o644,
		)
		if err != nil {
			return err
		}
		state.assistantRunbooks[assistant.ID] = filepath.Base(runbookPath)
	}
	pretty.LogIfVerbose("[createActionsDir] runbooks are ready!")
	return nil
}

func (state *SpecState) CreateConversationGuideFile(assistants []AgentServer.Agent, projectPath string) error {
	conversationGuidePath := common.AgentProjectConversationGuideFileLocation(projectPath)
	for _, assistant := range assistants {
		if len(assistant.QuestionGroups) <= 0 && len(assistant.Metadata.QuestionGroups) <= 0 {
			pretty.LogIfVerbose("[createConversationGuideFile] no question groups found for agent %s", assistant.ID)
			_ = state.removeConversationGuide(projectPath)
			continue
		}
		questionGroups := assistant.QuestionGroups
		if len(questionGroups) == 0 && len(assistant.Metadata.QuestionGroups) > 0 {
			questionGroups = assistant.Metadata.QuestionGroups
		}

		pretty.LogIfVerbose("[createConversationGuideFile] extracting conversation guide for: %s", safeAgentString(&assistant))
		data, err := yaml.Marshal(&common.AgentPackageConversationGuideContents{
			QuestionGroups: questionGroups,
		})
		if err != nil {
			return fmt.Errorf("failed to marshal QuestionGroups for agent %s: %w", assistant.ID, err)
		}
		if err = pathlib.WriteFile(conversationGuidePath, data, 0o644); err != nil {
			return err
		}
		state.AssistantConversationGuides = make(map[string]string)
		state.AssistantConversationGuides[assistant.ID] = filepath.Base(conversationGuidePath)
	}
	return nil
}

func (state *SpecState) removeConversationGuide(projectPath string) error {
	conversationGuidePath := common.AgentProjectConversationGuideFileLocation(projectPath)
	if pathlib.Exists(conversationGuidePath) {
		if err := os.Remove(conversationGuidePath); err != nil {
			return fmt.Errorf("failed to remove conversation guide file: %w", err)
		}
		pretty.LogIfVerbose("[removeConversationGuide] conversation guide file removed")
	}
	return nil
}

func (state *SpecState) createMcpServers(assistants []AgentServer.Agent) error {
	var mcpServers []common.SpecMcpServer

	for _, assistant := range assistants {
		pretty.LogIfVerbose("[createMcpServers] extracting mcpServers for: %s", safeAgentString(&assistant))
		for _, mcpServer := range assistant.McpServers {
			pretty.LogIfVerbose("[createMcpServers] dealing with: %s", mcpServer.Name)
			headers := make(common.SpecMcpServerVariables)
			for key, value := range mcpServer.Headers {
				headers[key] = common.BuildSpecMcpServerVariable(&value)
			}
			env := make(common.SpecMcpServerVariables)
			for key, value := range mcpServer.Env {
				env[key] = common.BuildSpecMcpServerVariable(&value)
			}

			var url string
			if mcpServer.URL != nil {
				url = *mcpServer.URL
			}

			var commandLine []string
			if mcpServer.Command != nil {
				commandLine = append([]string{*mcpServer.Command}, mcpServer.Args...)
			}

			var cwd string
			if mcpServer.Cwd != nil {
				cwd = *mcpServer.Cwd
			}

			// make sure that the command line is not empty and that the transport is stdio : prealbe for docker mcp gateway
			if len(commandLine) > 2 && mcpServer.Transport == AgentServer.MCPTransportStdio {
				isDockerMcpGateway := common.IsDockerMcpGateway(&common.AgentPackageMcpServer{Command: commandLine[0], Arguments: commandLine[1:]})
				pretty.LogIfVerbose("[createMcpServers] is docker mcp gateway: %+v", isDockerMcpGateway)
				if isDockerMcpGateway {
					// There is no catalog path for the Agent payload, so we use nil
					dockerMcpGatewaySpec, err := common.ExtractDockerMcpGatewayToSpec(nil)
					if err != nil {
						return fmt.Errorf("[createMcpServers] failed to extract docker mcp gateway: %w", err)
					}
					state.AssistantDockerMcpGateway = make(map[string]*common.SpecDockerMcpGateway)
					state.AssistantDockerMcpGateway[assistant.ID] = dockerMcpGatewaySpec
					continue
				}
			}

			mcpServers = append(mcpServers, common.SpecMcpServer{
				Name:                 mcpServer.Name,
				Transport:            mcpServer.Transport,
				Description:          mcpServer.Description,
				URL:                  url,
				CommandLine:          commandLine,
				Headers:              headers,
				Env:                  env,
				Cwd:                  cwd,
				ForceSerialToolCalls: mcpServer.ForceSerialToolCalls,
			})
		}

		pretty.LogIfVerbose("[createMcpServers] mcp servers are ready!")
		state.assistantMcpServer[assistant.ID] = mcpServers
	}
	return nil
}

func (state *SpecState) createSemanticDataModelsDir(assistants []AgentServer.Agent, projectPath string, client *AgentServer.Client) error {
	sdmPath := filepath.Join(projectPath, "semantic-data-models")

	// Cache for data connections to avoid redundant API calls
	connectionCache := make(map[string]*AgentServer.DataConnection)

	for _, assistant := range assistants {
		pretty.LogIfVerbose("[createSemanticDataModelsDir] fetching SDMs for agent: %s", assistant.ID)

		// Fetch SDMs from agent server
		sdms, err := client.GetAgentSemanticDataModels(assistant.ID)
		if err != nil {
			pretty.LogIfVerbose("[createSemanticDataModelsDir] failed to fetch SDMs for agent %s: %s", assistant.ID, err)
			continue // Continue with other agents if one fails
		}

		if len(sdms) == 0 {
			pretty.LogIfVerbose("[createSemanticDataModelsDir] no SDMs found for agent: %s", assistant.ID)
			continue
		}

		// Create semantic-data-models directory only if we have SDMs
		err = os.MkdirAll(sdmPath, 0o755)
		if err != nil {
			return fmt.Errorf("[createSemanticDataModelsDir] failed to create semantic-data-models directory: %w", err)
		}

		sdmRefs := []common.SpecSemanticDataModel{}
		usedFilenames := make(map[string]bool)

		for _, sdm := range sdms {
			// Generate filename from SDM name or ID
			var filename string
			if nameVal, ok := sdm.SemanticModel["name"]; ok {
				if nameStr, ok := nameVal.(string); ok && nameStr != "" {
					// Sanitize filename using slugify for consistent naming
					slugified := common.Slugify(nameStr)
					filename = fmt.Sprintf("%s.yaml", slugified)

					// Handle filename collision: append short ID (first 8 chars) if name already exists
					if usedFilenames[filename] {
						pretty.LogIfVerbose("[createSemanticDataModelsDir] filename collision detected for '%s', appending short ID", filename)
						shortID := sdm.ID
						if len(sdm.ID) > 8 {
							shortID = sdm.ID[:8]
						}
						filename = fmt.Sprintf("%s-%s.yaml", slugified, shortID)
					}
				}
			}
			if filename == "" {
				// Use SDM ID as fallback
				filename = fmt.Sprintf("sdm-%s.yaml", sdm.ID)
			}

			// Mark filename as used
			usedFilenames[filename] = true

			// Replace data_connection_id with data_connection_name for portability
			if tables, ok := sdm.SemanticModel["tables"].([]interface{}); ok {
				for _, tableInterface := range tables {
					if table, ok := tableInterface.(map[string]interface{}); ok {
						if baseTable, ok := table["base_table"].(map[string]interface{}); ok {
							if dcIDInterface, ok := baseTable["data_connection_id"]; ok {
								if dcID, ok := dcIDInterface.(string); ok && dcID != "" {
									// Check cache first
									dc, found := connectionCache[dcID]
									if !found {
										// Fetch data connection to get name
										var err error
										dc, err = client.GetDataConnection(dcID)
										if err != nil {
											pretty.LogIfVerbose("[createSemanticDataModelsDir] warning: failed to fetch data connection %s: %s", dcID, err)
											// Continue without replacing
											dc = nil
										} else {
											// Cache for future use
											connectionCache[dcID] = dc
										}
									}

									if dc != nil {
										// Replace ID with name
										baseTable["data_connection_name"] = dc.Name
										delete(baseTable, "data_connection_id")
										pretty.LogIfVerbose("[createSemanticDataModelsDir] replaced data_connection_id with name: %s", dc.Name)
									}
								}
							}
						}
					}
				}
			}

			// Write SDM to file
			sdmFilePath := filepath.Join(sdmPath, filename)

			// Export as YAML
			sdmYAML, err := yaml.Marshal(sdm.SemanticModel)
			if err != nil {
				return fmt.Errorf("[createSemanticDataModelsDir] failed to marshal SDM: %w", err)
			}

			if err := os.WriteFile(sdmFilePath, sdmYAML, 0o644); err != nil {
				return fmt.Errorf("[createSemanticDataModelsDir] failed to write SDM file: %w", err)
			}

			sdmRefs = append(sdmRefs, common.SpecSemanticDataModel{
				Name: filename,
			})

			pretty.LogIfVerbose("[createSemanticDataModelsDir] exported SDM: %s", filename)
		}

		state.assistantSemanticDataModels[assistant.ID] = sdmRefs
	}

	pretty.LogIfVerbose("[createSemanticDataModelsDir] semantic data models are ready!")
	return nil
}

func createAgentProject(assistants []AgentServer.Agent, projectPath string) error {
	if projectPath == "" {
		return fmt.Errorf("[createAgentProject] project path cannot be empty")
	}

	pretty.LogIfVerbose("[createAgentProject] creating agent project to path: %s", projectPath)
	if pathlib.Exists(projectPath) && !pathlib.IsEmptyDir(projectPath) {
		return fmt.Errorf("[createAgentProject] project directory %s already exists and is not empty", projectPath)
	}

	err := os.MkdirAll(projectPath, 0o755)
	if err != nil {
		return fmt.Errorf("[createAgentProject] failed to create agent project directory: %w", err)
	}

	state := SpecState{
		assistantKnowledge:          map[string][]common.SpecAgentKnowledge{},
		assistantActionPackages:     map[string][]common.SpecAgentActionPackage{},
		assistantMcpServer:          map[string][]common.SpecMcpServer{},
		AssistantDockerMcpGateway:   map[string]*common.SpecDockerMcpGateway{},
		assistantRunbooks:           map[string]string{},
		AssistantConversationGuides: map[string]string{},
		assistantSemanticDataModels: map[string][]common.SpecSemanticDataModel{},
	}

	// Create the knowledge directory and copy agent files
	err = state.createKnowledgeDir(assistants, projectPath)
	if err != nil {
		return err
	}

	// Create the semantic data models directory
	client := AgentServer.NewClient(agentServerURL)
	err = state.createSemanticDataModelsDir(assistants, projectPath, client)
	if err != nil {
		// Log error but don't fail the entire export
		pretty.LogIfVerbose("[createAgentProject] warning: failed to export SDMs: %s", err)
	}

	// Create the actions directory and copy action packages
	err = state.createActionsDir(assistants, projectPath)
	if err != nil {
		return err
	}

	// Extract and store MCP server configurations
	err = state.createMcpServers(assistants)
	if err != nil {
		return err
	}

	// Create the runbook file for the agent(s)
	err = state.createRunbookFile(assistants, projectPath)
	if err != nil {
		return err
	}

	// Optionally create the conversation guide file (ignore error if missing)
	_ = state.CreateConversationGuideFile(assistants, projectPath)

	// Create the agent spec YAML file
	err = state.createSpecFile(assistants, projectPath)
	if err != nil {
		return err
	}

	pretty.LogIfVerbose("[createAgentProject] agent project is ready")
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
				pretty.LogIfVerbose(
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
	if err := exportCmd.MarkFlagRequired("agent"); err != nil {
		fmt.Printf("failed to mark flag as required: %+v", err)
	}
	exportCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path")
	exportCmd.Flags().StringVar(&agentVersion, "overwrite-version", "", "Overwrite the agent version")
	exportCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
}
