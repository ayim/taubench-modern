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

	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common"
	rccCommon "github.com/Sema4AI/rcc/common"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
)

var (
	outputFile string
)

type agentPackageMetadataKnowledge struct {
	Embedded bool   `json:"embedded"`
	Name     string `json:"name"`
	Digest   string `json:"digest"`
}

type agentPackageMetadata struct {
	ReleaseNote    string                              `json:"release_note"`
	Version        string                              `json:"version"`
	Icon           string                              `json:"icon"`
	Name           string                              `json:"name"`
	Description    string                              `json:"description"`
	Model          common.AgentModel                   `json:"model"`
	Architecture   AgentServer.AgentArchitecture       `json:"architecture"`
	Reasoning      AgentServer.AgentReasoning          `json:"reasoning"`
	Knowledge      []agentPackageMetadataKnowledge     `json:"knowledge"`
	Datasources    []agentPackageDatasource            `json:"datasources"`
	ActionPackages []agentPackageActionPackageMetadata `json:"action_packages"`
	Metadata       AgentServer.AgentMetadata           `json:"metadata"`
}

type agentPackageActionPackageMetadata struct {
	actionPackageMetadata
	Whitelist string `json:"whitelist"`
	Icon      string `json:"icon"`
	Path      string `json:"path"`
}

type externalEndpointRule struct {
	Host string `json:"host"`
	Port int    `json:"port"`
}

type externalEndpoint struct {
	Name           string                 `json:"name"`
	Description    string                 `json:"description"`
	AdditionalInfo string                 `json:"additional-info-link"`
	Rules          []externalEndpointRule `json:"rules"`
}

type actionPackageMetadata struct {
	Name              string                        `json:"name"`
	Description       string                        `json:"description"`
	Secrets           map[string]interface{}        `json:"secrets"`
	Version           string                        `json:"action_package_version"`
	Actions           []actionPackageMetadataAction `json:"actions"`
	ExternalEndpoints []externalEndpoint            `json:"external-endpoints,omitempty"`
}

type actionPackageMetadataAction struct {
	Description   string `json:"description"`
	Name          string `json:"name"`
	Summary       string `json:"summary"`
	OperationKind string `json:"operation_kind"`
}

type agentPackageDatasource struct {
	CustomerFacingName string                 `json:"customer_facing_name"`
	Engine             string                 `json:"engine"`
	Description        string                 `json:"description"`
	Configuration      map[string]interface{} `json:"configuration"`
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

func generateAgentPackageActionPackageMetadata(
	// Raw (unprocessed) metadata for an action package
	// (from action-server package metadata command).
	rawMetadata map[string]interface{},
	actionPackage common.AgentActionPackage,
	projectPath string,
) (*agentPackageActionPackageMetadata, error) {
	nestedMetadata, err := json.Marshal(rawMetadata["metadata"])
	if err != nil {
		logVerbose("[generateAgentPackageActionPackageMetadata] Failed to marshal metadata: %v", err)
		logVerbose("[generateAgentPackageActionPackageMetadata] Failed to marshal metadata: %v", err)
		return nil, err
	}

	var actionPackageMetadata actionPackageMetadata
	if err := json.Unmarshal(nestedMetadata, &actionPackageMetadata); err != nil {
		logVerbose("[generateAgentPackageActionPackageMetadata] Failed to unmarshal metadata: %v", err)
		logVerbose("[generateAgentPackageActionPackageMetadata] Failed to unmarshal metadata: %v", err)
		return nil, err
	}

	if openapiSpec, ok := rawMetadata["openapi.json"].(map[string]interface{}); ok {
		if paths, ok := openapiSpec["paths"].(map[string]interface{}); ok {
			var actions []actionPackageMetadataAction
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
					act := actionPackageMetadataAction{
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

	return &agentPackageActionPackageMetadata{
		actionPackageMetadata: actionPackageMetadata,
		Whitelist:             actionPackage.Whitelist,
		Path:                  filepath.ToSlash(actionPackage.Path),
		Icon:                  icon,
	}, nil
}

func readActionPackageMetadataFromZip(zipPath string) ([]byte, error) {
	// Logic to read ACTION_PACKAGE_METADATA_FILE from the zip
	zipFile, err := zip.OpenReader(zipPath)
	if err != nil {
		logVerbose("[readActionPackageMetadataFromZip] failed to open the action package zip, err: %s", err)
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
		logVerbose("[readActionPackageMetadataFromZip] failed to open the metadata file in the zip: %s, err: %w", zipPath, err)
		return nil, err
	}
	defer reader.Close()

	metadataBytes, err := io.ReadAll(reader)
	if err != nil {
		logVerbose("[readActionPackageMetadataFromZip] failed to read the metadata content file in the zip: %s, err: %w", zipPath, err)
		return nil, err
	}

	return metadataBytes, nil
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

		logVerbose("[Action Server cmd]: %+v", cmd)
		err := cmd.Run()
		logVerbose("[Action Server stdout]: %+v", stdout.String())
		logVerbose("[Action Server stderr]:\n%+v", stderr.String())
		if err != nil {
			return nil, fmt.Errorf("[generateActionPackageMetadataForFolder] failed to generate metadata: %w", err)
		}
	} else if err != nil {
		logVerbose("[generateActionPackageMetadataForFolder] error checking for metadata file: %s, err: %s", metadataFilePath, err)
		return nil, err
	} else {
		logVerbose("[generateActionPackageMetadataForFolder] metadata file already exists: %s", metadataFilePath)
	}

	metadataBytes, err := os.ReadFile(metadataFilePath)
	if err != nil {
		logVerbose("[generateActionPackageMetadataForFolder] failed to read metadata file: %s, err: %s", metadataFilePath, err)
		return nil, err
	}

	return metadataBytes, nil
}

// Return a map of raw (unprocessed) action package metadata for each unique action package path.
// Key is the action package path, value is metadata.
func getRawActionPackageMetadatas(
	spec *common.AgentSpec,
	projectPath string,
) (map[string]map[string]interface{}, error) {
	metadatas := make(map[string]map[string]interface{})
	for _, agent := range spec.AgentPackage.Agents {
		for _, ap := range agent.ActionPackages {
			_, ok := metadatas[ap.Path]
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

			metadatas[ap.Path] = metadata
		}
	}
	return metadatas, nil
}

func generateAgentMetadataFromPackage(agentPackagePath string) ([]*agentPackageMetadata, error) {
	tempDir, err := common.CreateTempDir("metadata")
	if err != nil {
		return nil, fmt.Errorf("[metadataCmd] failed to create temporary directory: %w", err)
	}
	defer os.RemoveAll(tempDir)

	if err := extractAgentPackage(agentPackagePath, tempDir, false); err != nil {
		return nil, err
	}

	metadata, err := generateAgentMetadataFromProject(tempDir)
	if err != nil {
		return nil, err
	}

	return metadata, nil
}

func generateAgentMetadataFromPackageTo(agentPackagePath string, destDir string) ([]*agentPackageMetadata, error) {
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return nil, err
	}
	if err := extractAgentPackage(agentPackagePath, destDir, false); err != nil {
		return nil, err
	}
	metadata, err := generateAgentMetadataFromProject(destDir)
	if err != nil {
		return nil, err
	}
	return metadata, nil
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

func extractDatasources(
	// Raw (unprocessed) metadatas for each action package
	// (key is action package path, value is metadata).
	rawMetadatas map[string]map[string]interface{},
	projectPath string,
) ([]agentPackageDatasource, error) {
	datasources := []agentPackageDatasource{}

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
					logVerbose("[extractDatasources] skipping duplicate datasource: %s, engine: %s", name, engine)
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

			datasource := agentPackageDatasource{
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

func generateAgentMetadataFromProject(agentProjectPath string) ([]*agentPackageMetadata, error) {
	spec, err := readSpec(agentProjectPath)
	if err != nil {
		return nil, err
	}

	rawActionPackageMetadatas, err := getRawActionPackageMetadatas(spec, agentProjectPath)
	if err != nil {
		return nil, err
	}

	metadatas := make([]*agentPackageMetadata, 0)
	for _, agent := range spec.AgentPackage.Agents {
		metadata := agentPackageMetadata{
			Name:           agent.Name,
			Description:    agent.Description,
			Model:          agent.Model,
			Architecture:   agent.Architecture,
			Reasoning:      agent.Reasoning,
			Version:        agent.Version,
			Knowledge:      []agentPackageMetadataKnowledge{},
			Datasources:    []agentPackageDatasource{},
			ActionPackages: []agentPackageActionPackageMetadata{},
			Metadata:       agent.Metadata,
		}

		datasources, err := extractDatasources(rawActionPackageMetadatas, agentProjectPath)
		if err != nil {
			return nil, err
		}
		metadata.Datasources = datasources

		for _, ap := range agent.ActionPackages {
			actionPackageMetadata, err := generateAgentPackageActionPackageMetadata(
				rawActionPackageMetadatas[ap.Path],
				ap,
				agentProjectPath,
			)
			if err != nil {
				return nil, err
			}
			metadata.ActionPackages = append(metadata.ActionPackages, *actionPackageMetadata)
		}

		for _, knowledgeFile := range agent.Knowledge {
			metadata.Knowledge = append(metadata.Knowledge, agentPackageMetadataKnowledge{
				Embedded: knowledgeFile.Embedded,
				Name:     knowledgeFile.Name,
				Digest:   knowledgeFile.Digest,
			})
		}
		metadatas = append(metadatas, &metadata)
	}

	return metadatas, nil
}

func createAgentPackageMetadataFile(agentProjectPath string) error {
	metadata, err := generateAgentMetadataFromProject(agentProjectPath)
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

var metadataCmd = &cobra.Command{
	Use:   "metadata",
	Short: "Generate metadata for an agent package.",
	Long:  `Generate metadata for an agent package.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		err := common.ValidateActionServerVersion()
		if err != nil {
			return err
		}

		metadata, err := generateAgentMetadataFromPackage(agentPackagePath)
		if err != nil {
			return err
		}

		metadataJson, err := json.Marshal(metadata)
		if err != nil {
			return err
		}

		if outputFile != "" {
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
		"The .zip file whose metadata should be generated.",
	)
}
