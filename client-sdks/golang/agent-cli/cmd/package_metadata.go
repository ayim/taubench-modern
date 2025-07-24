package cmd

import (
	"archive/zip"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"mime"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/pretty"
	rccCommon "github.com/Sema4AI/rcc/common"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
)

var (
	outputFile string
)

// ===========================
// =========================== METADATA ==== ACTION PACKAGES
// ===========================

func generateAgentPackageActionPackageMetadata(
	// Raw (unprocessed) metadata for an action package
	// (from action-server package metadata command).
	rawMetadata map[string]interface{},
	actionPackage common.SpecAgentActionPackage,
	projectPath string,
) (*common.AgentPackageActionPackageMetadata, error) {
	nestedMetadata, err := json.Marshal(rawMetadata["metadata"])
	if err != nil {
		pretty.LogIfVerbose("[generateAgentPackageActionPackageMetadata] Failed to marshal metadata: %v", err)
		pretty.LogIfVerbose("[generateAgentPackageActionPackageMetadata] Failed to marshal metadata: %v", err)
		return nil, err
	}

	var actionPackageMetadata common.ActionPackageMetadata
	if err := json.Unmarshal(nestedMetadata, &actionPackageMetadata); err != nil {
		pretty.LogIfVerbose("[generateAgentPackageActionPackageMetadata] Failed to unmarshal metadata: %v", err)
		pretty.LogIfVerbose("[generateAgentPackageActionPackageMetadata] Failed to unmarshal metadata: %v", err)
		return nil, err
	}

	if openapiSpec, ok := rawMetadata["openapi.json"].(map[string]interface{}); ok {
		if paths, ok := openapiSpec["paths"].(map[string]interface{}); ok {
			var actions []common.ActionPackageMetadataAction
			for _, path := range paths {
				if post, ok := path.(map[string]interface{})["post"].(map[string]interface{}); ok {
					description := ""
					if desc, ok := post["description"].(string); ok {
						description = desc
					}
					// For backwards compatibility, if x-operation-kind is not set, default to "action".
					operationKind := "action"
					if kind, ok := post["x-operation-kind"].(string); ok {
						operationKind = kind
					}
					act := common.ActionPackageMetadataAction{
						Description:   description,
						Name:          post["operationId"].(string),
						Summary:       post["summary"].(string),
						OperationKind: operationKind,
					}
					actions = append(actions, act)
				}
			}
			actionPackageMetadata.Actions = actions
		}
	}

	packagePath := filepath.Join(common.AgentProjectActionsLocation(projectPath), actionPackage.Path)
	icon := ""
	iconPath := filepath.Join(packagePath, common.ACTION_PACKAGE_ICON_FILE)
	// if the icon file doesn't exist, continue
	if pathlib.Exists(iconPath) {
		icon, err = convertImageToBase64(
			filepath.Join(packagePath, common.ACTION_PACKAGE_ICON_FILE),
		)
		if err != nil {
			return nil, err
		}
	}

	return &common.AgentPackageActionPackageMetadata{
		ActionPackageMetadata: actionPackageMetadata,
		Whitelist:             actionPackage.Whitelist,
		Path:                  filepath.ToSlash(actionPackage.Path),
		Icon:                  icon,
	}, nil
}

func generateActionPackageMetadataForFolder(folderPath string) ([]byte, error) {
	// FOR SUPPORT: action-server package metadata --input-dir <folderPath> --output-file <metadataFilePath>
	metadataFilePath := filepath.Join(folderPath, common.ACTION_PACKAGE_METADATA_FILE)

	if _, err := os.Stat(metadataFilePath); os.IsNotExist(err) {
		// Execute the action-server command to generate metadata if the file doesn't exist
		cmd := exec.Command(
			common.GetActionServerBin(),
			"package",
			"metadata",
			"--input-dir",
			folderPath,
			"--output-file",
			metadataFilePath,
		)

		var stdout bytes.Buffer
		var stderr bytes.Buffer
		cmd.Dir = filepath.Dir(folderPath)
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr

		err := cmd.Run()
		pretty.LogIfVerbose("[action server cmd]: %+v", cmd)
		pretty.LogIfVerbose("[action server stdout]: %+v", stdout.String())

		if err != nil {
			// Just stderr should be enough for the error message.
			return nil, fmt.Errorf("[generateActionPackageMetadataForFolder] failed to generate metadata. err: %+v, stderr: %s", err, stderr.String())
		}
		// Just log stderr if there were no errors (otherwise it will be shown twice,
		// which is a bit too much).
		pretty.LogIfVerbose("[action server stderr]:\n%+v", stderr.String())
	} else if err != nil {
		pretty.LogIfVerbose("[generateActionPackageMetadataForFolder] error checking for metadata file: %s, err: %s", metadataFilePath, err)
		return nil, err
	} else {
		pretty.LogIfVerbose("[generateActionPackageMetadataForFolder] skipped generation. metadata file already exists: %s", metadataFilePath)
	}

	metadataBytes, err := os.ReadFile(metadataFilePath)
	if err != nil {
		pretty.LogIfVerbose("[generateActionPackageMetadataForFolder] failed to read metadata file: %s, err: %s", metadataFilePath, err)
		return nil, err
	}

	return metadataBytes, nil
}

func convertImageToBase64(filePath string) (string, error) {
	imageData, err := os.ReadFile(filePath)
	if err != nil {
		return "", err
	}

	ext := filepath.Ext(filePath)
	mimeType := mime.TypeByExtension(ext)
	if mimeType == "" {
		return "", fmt.Errorf("[convertImageToBase64] unsupported file type: %s", ext)
	}

	base64String := base64.StdEncoding.EncodeToString(imageData)
	return fmt.Sprintf("data:%s;base64,%s", mimeType, base64String), nil
}

func readActionPackageMetadataFromZip(zipPath string) ([]byte, error) {
	// Logic to read ACTION_PACKAGE_METADATA_FILE from the zip
	zipFile, err := zip.OpenReader(zipPath)
	if err != nil {
		pretty.LogIfVerbose("[readActionPackageMetadataFromZip] failed to open the action package zip, err: %s", err)
		return nil, fmt.Errorf("failed to open the action package zip: %s, err: %w", zipPath, err)
	}

	defer zipFile.Close()

	var metadataFile *zip.File
	for _, file := range zipFile.File {
		if file.Name == common.ACTION_PACKAGE_METADATA_FILE {
			metadataFile = file
			break
		}
	}

	if metadataFile == nil {
		return nil, fmt.Errorf("action package metadata file not found in zip: %s", zipPath)
	}

	reader, err := metadataFile.Open()
	if err != nil {
		pretty.LogIfVerbose("[readActionPackageMetadataFromZip] failed to open the metadata file in the zip: %s, err: %+v", zipPath, err)
		return nil, err
	}
	defer reader.Close()

	metadataBytes, err := io.ReadAll(reader)
	if err != nil {
		pretty.LogIfVerbose("[readActionPackageMetadataFromZip] failed to read the metadata content file in the zip: %s, err: %+v", zipPath, err)
		return nil, err
	}

	return metadataBytes, nil
}

// Return a map of raw (unprocessed) action package metadata for each unique action package path.
// Key is the action package path, value is metadata.
func getRawMetadataFromActionPackages(
	spec *common.AgentSpec,
	projectPath string,
) (map[string]map[string]interface{}, error) {
	metadataForAllPacks := make(map[string]map[string]interface{})
	for _, agent := range spec.AgentPackage.Agents {
		for _, ap := range agent.ActionPackages {
			_, ok := metadataForAllPacks[ap.Path]
			if ok {
				continue
			}

			packagePath := filepath.Join(common.AgentProjectActionsLocation(projectPath), ap.Path)

			var metadataBytes []byte
			var err error

			if strings.HasSuffix(packagePath, ".zip") {
				// Logic to read the ACTION_PACKAGE_METADATA_FILE from the zip
				metadataBytes, err = readActionPackageMetadataFromZip(packagePath)
				if err != nil {
					return nil, err
				}
			} else {
				// Generate metadata using Action Server
				metadataBytes, err = generateActionPackageMetadataForFolder(packagePath)
				if err != nil {
					return nil, err
				}
			}

			var metadata map[string]interface{}
			if err := json.Unmarshal(metadataBytes, &metadata); err != nil {
				return nil, err
			}

			metadataForAllPacks[ap.Path] = metadata
		}
	}
	return metadataForAllPacks, nil
}

// ===========================
// =========================== METADATA ==== DATA SOURCES
// ===========================
// Extracts the datasources from the raw metadata.
func getRawDatasources(rawMetadata map[string]interface{}) ([]interface{}, error) {
	metadata, ok := rawMetadata["metadata"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("metadata not found")
	}

	data, ok := metadata["data"].(map[string]interface{})
	if !ok {
		return []interface{}{}, nil
	}

	datasources, ok := data["datasources"].([]interface{})
	if !ok {
		return []interface{}{}, nil
	}
	return datasources, nil
}

// Gets the name of the datasource depending on the engine.
func getDatasourceName(datasource map[string]interface{}, engine string) string {
	switch engine {
	case "files":
		return datasource["created_table"].(string)
	case "prediction:lightwood":
		return datasource["model_name"].(string)
	default:
		return datasource["name"].(string)
	}
}

func extractDatasources(
	// Raw (unprocessed) metadatas for each action package
	// (key is action package path, value is metadata).
	rawMetadatas map[string]map[string]interface{},
	projectPath string,
) ([]common.AgentPackageDatasource, error) {
	datasources := []common.AgentPackageDatasource{}

	// store datasource name to engine mapping to ensure uniqueness
	nameEngineMap := make(map[string]string)

	for actionPackagePath, rawMetadata := range rawMetadatas {
		rawDatasources, err := getRawDatasources(rawMetadata)
		if err != nil {
			return nil, err
		}
		for _, ds := range rawDatasources {
			dsMap := ds.(map[string]interface{})
			engine := dsMap["engine"].(string)
			name := getDatasourceName(dsMap, engine)

			// Ensure datasource uniqueness
			storedEngine, ok := nameEngineMap[name]
			if ok {
				if storedEngine == engine {
					pretty.LogIfVerbose("[extractDatasources] skipping duplicate datasource: %s, engine: %s", name, engine)
					continue
				}
				return nil, fmt.Errorf("multiple datasources with same name: %s, engine: %s", name, engine)
			}

			if engine == "files" {
				file := dsMap["file"].(string)
				actionsLocation := common.AgentProjectActionsLocation(projectPath)
				// Check if the file exists
				if _, err := os.Stat(filepath.Join(actionsLocation, actionPackagePath, file)); os.IsNotExist(err) {
					return nil, fmt.Errorf("file %s not found in: %s", file, actionPackagePath)
				}
				// File paths need to be relative to the agent project root.
				dsMap["file"] = filepath.ToSlash(filepath.Join(common.AGENT_PROJECT_ACTIONS_DIR, actionPackagePath, file))
			}

			datasource := common.AgentPackageDatasource{
				CustomerFacingName: name,
				Engine:             engine,
				Description:        dsMap["description"].(string),
				Configuration:      dsMap,
			}
			datasources = append(datasources, datasource)
			nameEngineMap[name] = engine
		}
	}

	return datasources, nil
}

// ===========================
// =========================== METADATA ==== MCP SERVERS
// ===========================

// generateMcpServersMetadata generates metadata for an MCP server.
func GenerateMcpServersMetadata(mcp common.SpecMcpServer) (*common.AgentPackageMcpServer, error) {
	// === TRANSPORT = Auto + SSE + HTTP
	// We calculate the transport type based on the url and command line.
	// If the transport is auto, we check if the url contains /sse or not.
	// If the transport is auto and the url is not set, we check if the command line is set.
	// If the transport is auto and the url and command line are not set, we use stdio.
	// If the transport is not auto, we use the transport type as is.
	isURLTransport := mcp.Transport == AgentServer.MCPTransportStreamableHTTP || mcp.Transport == AgentServer.MCPTransportSSE

	// Split the command line into command + arguments to make it easier in the Agent Server
	command := ""
	if len(mcp.CommandLine) > 0 {
		command = mcp.CommandLine[0]
	}
	if mcp.Transport == "auto" {
		if mcp.URL != "" {
			isURLTransport = true
		} else if command != "" {
			isURLTransport = false
		}
	}
	// Only error if both URL and command are set (ambiguous), or if URL is set but not a URL transport
	if mcp.URL != "" && command != "" {
		return nil, fmt.Errorf("cannot set both url and command for MCP server")
	}
	if mcp.URL != "" && !isURLTransport {
		return nil, fmt.Errorf("'url' transport requires transport=sse or transport=streamable-http or transport=auto")
	}
	if command != "" && isURLTransport {
		return nil, fmt.Errorf("'command' transport requires transport=stdio or transport=auto")
	}

	if isURLTransport {
		var headers map[string]common.AgentPackageMcpServerVariable
		if len(mcp.Headers) > 0 {
			headers = make(map[string]common.AgentPackageMcpServerVariable)
		}
		for key, values := range mcp.Headers {
			headers[key] = common.BuildAgentPackageMcpServerVariable(&values)
		}

		return &common.AgentPackageMcpServer{
			Name:                 mcp.Name,
			Description:          mcp.Description,
			Transport:            mcp.Transport,
			URL:                  mcp.URL,
			Headers:              headers,
			ForceSerialToolCalls: mcp.ForceSerialToolCalls,
		}, nil
	}

	// === TRANSPORT = STDIO
	var args []string
	if len(mcp.CommandLine) > 0 {
		args = mcp.CommandLine[1:]
	} else {
		args = make([]string, 0)
	}

	// Calculate environment variables (env)
	var env map[string]common.AgentPackageMcpServerVariable
	if len(mcp.Env) > 0 {
		env = make(map[string]common.AgentPackageMcpServerVariable)
	}
	for key, values := range mcp.Env {
		env[key] = common.BuildAgentPackageMcpServerVariable(&values)
	}

	return &common.AgentPackageMcpServer{
		Name:                 mcp.Name,
		Description:          mcp.Description,
		Transport:            mcp.Transport,
		Command:              command,
		Arguments:            args,
		Env:                  env,
		Cwd:                  mcp.Cwd,
		ForceSerialToolCalls: mcp.ForceSerialToolCalls,
	}, nil
}

// ===========================
// =========================== METADATA ==== AGENT PROJECT
// ===========================

func GenerateAgentMetadataFromPackage(agentPackagePath string) ([]*common.AgentPackageMetadata, error) {
	tempDir, err := common.CreateTempDir("metadata")
	if err != nil {
		return nil, fmt.Errorf("[metadataCmd] failed to create temporary directory: %w", err)
	}
	defer os.RemoveAll(tempDir)
	pretty.LogIfVerbose("[GenerateAgentMetadataFromPackage] will use the temp dir as destination @: %+v", tempDir)

	if err := extractAgentPackage(agentPackagePath, tempDir, false); err != nil {
		return nil, err
	}
	pretty.LogIfVerbose("[GenerateAgentMetadataFromPackage] agent extracted @: %+v", tempDir)

	metadata, err := GenerateAgentMetadataFromProject(tempDir)
	if err != nil {
		return nil, err
	}

	pretty.LogIfVerbose("[GenerateAgentMetadataFromPackage] generating metadata succeeded!")
	return metadata, nil
}

func GenerateAgentMetadataFromPackageTo(agentPackagePath string, destDir string) ([]*common.AgentPackageMetadata, error) {
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return nil, err
	}
	pretty.LogIfVerbose("[metadataCmd] will use the destination dir @: %+v", destDir)
	if err := extractAgentPackage(agentPackagePath, destDir, false); err != nil {
		return nil, err
	}
	metadata, err := GenerateAgentMetadataFromProject(destDir)
	if err != nil {
		return nil, err
	}
	return metadata, nil
}

func GenerateAgentMetadataFromProject(agentProjectPath string) ([]*common.AgentPackageMetadata, error) {
	pretty.LogIfVerbose("[generateAgentMetadataFromProject] reading spec...")
	spec, err := ReadSpec(agentProjectPath)
	if err != nil {
		return nil, err
	}

	pretty.LogIfVerbose("[generateAgentMetadataFromProject] gathering action packages metadata...")
	rawMetadataFromActionPackages, err := getRawMetadataFromActionPackages(spec, agentProjectPath)
	if err != nil {
		return nil, err
	}

	pretty.LogIfVerbose("[generateAgentMetadataFromProject] gathering agents metadata...")
	metadataForAllAgents := make([]*common.AgentPackageMetadata, 0)
	for _, agent := range spec.AgentPackage.Agents {
		pretty.LogIfVerbose("[generateAgentMetadataFromProject] dealing with agent: %+v", agent.Name)
		metadata := common.AgentPackageMetadata{
			Name:                agent.Name,
			Description:         agent.Description,
			Model:               agent.Model,
			Architecture:        agent.Architecture,
			Reasoning:           agent.Reasoning,
			Version:             agent.Version,
			WelcomeMessage:      agent.WelcomeMessage,
			ConversationStarter: agent.ConversationStarter,
			Knowledge:           []common.AgentPackageMetadataKnowledge{},
			Datasources:         []common.AgentPackageDatasource{},
			ActionPackages:      []common.AgentPackageActionPackageMetadata{},
			McpServers:          []common.AgentPackageMcpServer{},
			Metadata:            agent.Metadata,
		}

		// Extract Welcome Message if present
		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting welcome message...")
		if metadata.WelcomeMessage == "" {
			metadata.WelcomeMessage = agent.Metadata.WelcomeMessage
		}

		// Extract Conversation Guide (QuestionGroups) if present
		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting question groups...")
		conversationGuidePath := common.AgentProjectConversationGuideFileLocation(agentProjectPath)

		questionGroups, err := common.ReadConversationGuideYAML(conversationGuidePath)
		if err != nil {
			pretty.LogIfVerbose("[generateAgentMetadataFromProject] skipping conversation guide: %+v", err)
		} else {
			metadata.QuestionGroups = questionGroups
			metadata.Metadata.QuestionGroups = questionGroups
		}

		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting data sources...")
		datasources, err := extractDatasources(rawMetadataFromActionPackages, agentProjectPath)
		if err != nil {
			return nil, err
		}
		metadata.Datasources = datasources

		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting action packages metadata...")
		for _, ap := range agent.ActionPackages {
			pretty.LogIfVerbose("[generateAgentMetadataFromProject] dealing with action package: %+v", ap.Name)
			actionPackageMetadata, err := generateAgentPackageActionPackageMetadata(
				rawMetadataFromActionPackages[ap.Path],
				ap,
				agentProjectPath,
			)
			if err != nil {
				return nil, err
			}
			metadata.ActionPackages = append(metadata.ActionPackages, *actionPackageMetadata)
		}

		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting mcp servers...")
		for _, mcp := range agent.McpServers {
			pretty.LogIfVerbose("[generateAgentMetadataFromProject] dealing with mcp server: %+v", mcp.Name)
			mcpServerMeta, err := GenerateMcpServersMetadata(mcp)
			if err != nil {
				return nil, err
			}
			metadata.McpServers = append(metadata.McpServers, *mcpServerMeta)
		}

		pretty.LogIfVerbose("[generateAgentMetadataFromProject] extracting knowledge files...")
		for _, knowledgeFile := range agent.Knowledge {
			metadata.Knowledge = append(metadata.Knowledge, common.AgentPackageMetadataKnowledge{
				Embedded: knowledgeFile.Embedded,
				Name:     knowledgeFile.Name,
				Digest:   knowledgeFile.Digest,
			})
		}
		metadataForAllAgents = append(metadataForAllAgents, &metadata)
	}

	pretty.LogIfVerbose("[generateAgentMetadataFromProject] metadata for all agents is ready!")
	return metadataForAllAgents, nil
}

func createAgentPackageMetadataFile(agentProjectPath string) error {
	metadata, err := GenerateAgentMetadataFromProject(agentProjectPath)
	if err != nil {
		return fmt.Errorf(
			"[createAgentPackageMetadataFile] failed to generate agent metadata from project: %w",
			err,
		)
	}

	metadataJson, err := json.Marshal(metadata)
	if err != nil {
		return fmt.Errorf(
			"[createAgentPackageMetadataFile] failed to marshal agent metadata to JSON: %w",
			err,
		)
	}

	err = pathlib.WriteFile(
		filepath.Join(agentProjectPath, common.AGENT_PACKAGE_METADATA_FILE),
		metadataJson,
		0o644,
	)
	if err != nil {
		return fmt.Errorf(
			"[createAgentPackageMetadataFile] failed to write agent metadata to file: %w",
			err,
		)
	}

	return nil
}

// ===========================
// =========================== METADATA ==== CMD
// ===========================
var metadataCmd = &cobra.Command{
	Use:   "metadata",
	Short: "Generate metadata for an agent package.",
	Long:  `Generate metadata for an agent package.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		pretty.LogIfVerbose("[metadataCmd] validating action server version...")
		err := common.ValidateActionServerVersion()
		if err != nil {
			return err
		}

		pretty.LogIfVerbose("[metadataCmd] generating metadata...")
		metadata, err := GenerateAgentMetadataFromPackage(agentPackagePath)
		if err != nil {
			return err
		}

		metadataJson, err := json.Marshal(metadata)
		if err != nil {
			return err
		}

		if outputFile != "" {
			pretty.LogIfVerbose("[metadataCmd] package metadata available at: %+v", outputFile)
			err = pathlib.WriteFile(outputFile, metadataJson, 0o644)
			if err != nil {
				return err
			}
		} else {
			rccCommon.Stdout("%s\n", metadataJson)
		}

		return nil
	},
}

func init() {
	packageCmd.AddCommand(metadataCmd)
	metadataCmd.Flags().StringVar(
		&outputFile,
		"output-file",
		"",
		"The output file for saving the metadata (default is writing to stdout)",
	)
	metadataCmd.Flags().StringVar(
		&agentPackagePath,
		"package",
		common.AGENT_PACKAGE_DEFAULT_NAME,
		"The path to the .zip file that needs inspecting and metadata generating",
	)
}
