package cmd

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common/glob"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
	"gopkg.in/yaml.v2"
)

func zipDir(sourceDir, targetZip string) error {
	// read the agent spec file to get the excluded files
	spec, err := ReadSpec(sourceDir)
	if err != nil {
		return err
	}

	// Get paths that aren't excluded (map of path -> isDir)
	includedPaths, err := glob.Exclude(sourceDir, spec.AgentPackage.Exclude)
	if err != nil {
		return err
	}

	zipFile, err := os.Create(targetZip)
	if err != nil {
		return err
	}
	defer zipFile.Close()

	zipWriter := zip.NewWriter(zipFile)
	defer zipWriter.Close()

	// Process all paths
	for path, isDir := range includedPaths {
		// Get relative path
		relPath, err := filepath.Rel(sourceDir, path)
		if err != nil {
			return err
		}

		// Convert to forward slashes for zip
		zipPath := filepath.ToSlash(relPath)

		if isDir {
			// Add directory entry (with trailing slash)
			if !strings.HasSuffix(zipPath, "/") {
				zipPath += "/"
			}

			dirHeader := &zip.FileHeader{
				Name:   zipPath,
				Method: zip.Deflate,
			}

			_, err = zipWriter.CreateHeader(dirHeader)
			if err != nil {
				return err
			}
		} else {
			// Add file entry
			info, err := os.Stat(path)
			if err != nil {
				return err
			}

			header, err := zip.FileInfoHeader(info)
			if err != nil {
				return err
			}

			header.Name = zipPath
			header.Method = zip.Deflate

			writer, err := zipWriter.CreateHeader(header)
			if err != nil {
				return err
			}

			file, err := os.Open(path)
			if err != nil {
				return err
			}

			_, err = io.Copy(writer, file)
			file.Close()

			if err != nil {
				return err
			}
		}
	}

	return nil
}

func buildActionPackage(sourceDir, targetZip string) error {
	// FOR SUPPORT: action-server package build --output-dir <dir>

	// We need to build the Action Package to a temp location as we need to cleart the sourceDir
	// in the end so that it will only contain the zip file
	tempDir, err := common.CreateTempDir("build-action-package")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tempDir)

	pretty.LogIfVerbose("[buildActionPackage] from: %s", sourceDir)
	pretty.LogIfVerbose("[buildActionPackage] target: %s", targetZip)

	args := []string{
		"package",
		"build",
		"--output-dir",
		tempDir,
	}

	// If agent-cli is ran with --verbose do the same for action-server
	if common.Verbose {
		args = append(args, "--verbose")
	}

	cmd := exec.Command(
		common.GetActionServerBin(),
		args...,
	)

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	cmd.Dir = sourceDir

	pretty.LogIfVerbose("[Action Server cmd]: %+v", cmd)
	err = cmd.Run()

	pretty.LogIfVerbose("[Action Server stdout]: %+v", stdout.String())

	if err != nil {
		return fmt.Errorf("[buildActionPackage] failed to build action package. err: %+v, stderr: %s", err, stderr.String())
	}

	// Just log stderr if there were no errors (otherwise it will be shown twice,
	// which is a bit too much).
	pretty.LogIfVerbose("[Action Server stderr]:\n%+v", stderr.String())

	zipFiles, err := filepath.Glob(filepath.Join(tempDir, "*.zip"))
	if err != nil || len(zipFiles) == 0 {
		return fmt.Errorf("[buildActionPackage] failed to find generated zip file: %w", err)
	}

	// Clear the sourceDir before placing the zip file in it
	if err := os.RemoveAll(sourceDir); err != nil {
		return fmt.Errorf("[buildActionPackage] unable to remove action package directory content: %w", err)
	}

	err = pathlib.CopyFile(zipFiles[0], targetZip, true)
	if err != nil {
		return fmt.Errorf("[buildActionPackage] failed to copy generated zip: %w", err)
	}

	pretty.Log("[buildActionPackages] action package is ready!")
	return nil
}

func buildActionPackages(spec *common.AgentSpec, agentProjectActionsPath string) error {
	// Map of original action project's path within agent package and updated path
	// after building the action package. E.g.: Sema4.ai/greeter : Sema4.ai/greeter.zip.
	updatedPaths := make(map[string]string)

	pretty.LogIfVerbose("[buildActionPackages] building action packages...")
	for agentIndex, agent := range spec.AgentPackage.Agents {
		for actionIndex, act := range agent.ActionPackages {
			targetPath, ok := updatedPaths[act.Path]
			if !ok {
				pretty.LogIfVerbose("[buildActionPackages] - action Package Path: %s", act.Path)
				sourcePath := filepath.Join(agentProjectActionsPath, act.Path)
				targetPath = filepath.Join(act.Organization, common.Slugify(act.Name), act.Version+".zip")
				targetZipFile := filepath.Join(agentProjectActionsPath, targetPath)
				pretty.LogIfVerbose("Build action package from: %+v to: %s", sourcePath, targetZipFile)
				err := buildActionPackage(sourcePath, targetZipFile)
				if err != nil {
					return fmt.Errorf("[buildActionPackages] failed to build action package: %w", err)
				}

				targetPath = filepath.ToSlash(targetPath)
				updatedPaths[act.Path] = targetPath
				pretty.Log("[buildActionPackages]  - done with: %s", act.Path)
			}

			spec.AgentPackage.Agents[agentIndex].ActionPackages[actionIndex] = common.SpecAgentActionPackage{
				Path:         targetPath,
				Type:         common.ActionPackageZip,
				Name:         act.Name,
				Organization: act.Organization,
				Version:      act.Version,
				Whitelist:    act.Whitelist,
			}
		}
	}

	// Normalize agent settings for JSON marshaling validation
	for i := range spec.AgentPackage.Agents {
		spec.AgentPackage.Agents[i].AgentSettings = common.NormalizeMap(spec.AgentPackage.Agents[i].AgentSettings)
	}

	_, err := json.MarshalIndent(spec, "", "  ")
	if err != nil {
		pretty.Exit(1, "agent-spec json parsing failed on: %+v", err)
	}

	pretty.Log("[buildActionPackages] action packages are ready!")
	return nil
}

func ReadSpec(agentPackageDir string) (*common.AgentSpec, error) {
	specPath := filepath.Join(agentPackageDir, common.AGENT_PROJECT_SPEC_FILE)
	pretty.LogIfVerbose("[readSpec] agent spec YAML file path: %+v", specPath)

	data, err := os.ReadFile(specPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("[readSpec] spec YAML file @ [%s] not found", specPath)
		}
		return nil, fmt.Errorf("[readSpec] failed to read spec YAML file: %w", err)
	}

	var spec common.AgentSpec
	if err := yaml.Unmarshal(data, &spec); err != nil {
		return nil, fmt.Errorf("[readSpec] failed to unmarshal YAML: %v", err)
	}

	pretty.LogIfVerbose("[readSpec] spec validated!")
	return &spec, nil
}

// FilterMcpServerSecretValuesFromSpec returns a deep copy of the spec with all MCP Server variable Value fields removed.
func FilterMcpServerSecretValuesFromSpec(spec *common.AgentSpec) *common.AgentSpec {
	pretty.LogIfVerbose("[filterMcpServerValuesFromSpec] filtering mcp server values from agent spec...")
	if spec == nil {
		return spec
	}
	copySpec := *spec
	copySpec.AgentPackage = spec.AgentPackage
	copySpec.AgentPackage.Agents = make([]common.SpecAgent, len(spec.AgentPackage.Agents))
	for i, agent := range spec.AgentPackage.Agents {
		// Create a proper deep copy of the agent, preserving all fields
		agentCopy := agent

		// Deep copy MCP servers and filter secret values
		agentCopy.McpServers = make([]common.SpecMcpServer, len(agent.McpServers))
		for j, mcp := range agent.McpServers {
			mcpCopy := mcp
			// we need to remove the secret values from the headers and env
			mcpCopy.Headers = RemoveSecretValues(mcp.Headers)
			mcpCopy.Env = RemoveSecretValues(mcp.Env)
			// done
			agentCopy.McpServers[j] = mcpCopy
		}

		// Deep copy SelectedTools to ensure it's preserved
		agentCopy.SelectedTools = common.SpecSelectedTools{
			Tools: make([]common.SpecSelectedToolConfig, len(agent.SelectedTools.Tools)),
		}
		copy(agentCopy.SelectedTools.Tools, agent.SelectedTools.Tools)

		copySpec.AgentPackage.Agents[i] = agentCopy
	}
	return &copySpec
}

// FilterQuestionGroupsFromSpec returns a deep copy of the spec with all question groups removed.
func FilterQuestionGroupsFromSpec(spec *common.AgentSpec) *common.AgentSpec {
	pretty.LogIfVerbose("[filterQuestionGroupsFromSpec] filtering question groups from agent spec...")
	if spec == nil {
		return spec
	}
	copySpec := *spec
	copySpec.AgentPackage = spec.AgentPackage
	copySpec.AgentPackage.Agents = make([]common.SpecAgent, len(spec.AgentPackage.Agents))
	for i, agent := range spec.AgentPackage.Agents {
		agentCopy := agent
		agentCopy.Metadata.QuestionGroups = nil
		copySpec.AgentPackage.Agents[i] = agentCopy
	}
	return &copySpec
}

// RemoveSecretValues returns a copy of the input map with secret values removed
func RemoveSecretValues(vars common.SpecMcpServerVariables) common.SpecMcpServerVariables {
	if vars == nil {
		return nil
	}
	copyVars := make(common.SpecMcpServerVariables, len(vars))
	for k, v := range vars {
		// Only remove value for secret and oauth2-secret types
		if !v.HasRawValue() && (v.Type == common.SpecMcpTypeSecret || v.Type == common.SpecMcpTypeOAuth2Secret) {
			v.Value = nil
		}
		// All other types (including data-server-info, string) are preserved
		copyVars[k] = v
	}
	return copyVars
}

// WriteSpec writes the agent specification to a YAML file in the specified agent package directory.
// The function returns an error if marshalling or writing fails.
func WriteSpec(spec *common.AgentSpec, agentPackageDir string) error {
	// Question groups shouldn't be included in the Agent Spec - they should be part of the conversation guide file.
	newSpec := spec
	newSpec = FilterQuestionGroupsFromSpec(newSpec)
	newSpec = FilterMcpServerSecretValuesFromSpec(newSpec)

	data, err := yaml.Marshal(newSpec)
	if err != nil {
		return fmt.Errorf("[writeSpec] failed to marshal YAML: %w", err)
	}

	err = pathlib.WriteFile(
		filepath.Join(agentPackageDir, common.AGENT_PROJECT_SPEC_FILE),
		data,
		0o644,
	)
	if err != nil {
		return fmt.Errorf("[writeSpec] failed to write spec YAML file: %w", err)
	}
	return nil
}

func BuildAgentPackage(inputDir, outputDir, name string, overwriteAgentPackage bool) error {
	// if the input dir does not exist, return an error
	if !common.FileExists(inputDir) {
		return fmt.Errorf("[BuildAgentPackage] unable to build agent package because input directory %s does not exist", inputDir)
	}

	packagePath := filepath.Join(outputDir, name)
	if common.FileExists(packagePath) {
		if overwriteAgentPackage {
			if err := os.Remove(packagePath); err != nil {
				return fmt.Errorf("[BuildAgentPackage] failed to remove existing package: %w", err)
			}
		} else {
			return fmt.Errorf("[BuildAgentPackage] package %s already exists", packagePath)
		}
	}

	spec, err := ReadSpec(inputDir)
	if err != nil {
		return err
	}

	tempDir, err := common.CreateTempDir("build")
	if err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to create temporary directory: %w", err)
	}
	if err := common.CopyDir(inputDir, tempDir, false); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to copy directory %s to %s: %w", filepath.Dir(""), tempDir, err)
	}
	defer os.RemoveAll(tempDir)

	pretty.Log("[BuildAgentPackage] destination temp directory for package: %+v", tempDir)

	if err = buildActionPackages(spec, common.AgentProjectActionsLocation(tempDir)); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to build action packages: %w", err)
	}

	if err := WriteSpec(spec, tempDir); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to create write spec: %w", err)
	}

	// Always build the metadata file after the agent spec has been finalized.
	// This was previously done before building action packages, which meant that
	// the metadata file could be out of date if action packages modified the spec.
	pretty.Log("[BuildAgentPackage] creating agent package metadata file...")
	if err := createAgentPackageMetadataFile(tempDir); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to create agent package metadata file: %w", err)
	}
	pretty.Log("[BuildAgentPackage] agent package metadata file created")

	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to create output directory: %w", err)
	}

	if err := zipDir(tempDir, packagePath); err != nil {
		return fmt.Errorf("[BuildAgentPackage] failed to create zip the directory: %w", err)
	}

	return nil
}

var buildCmd = &cobra.Command{
	Use:   "build",
	Short: "Build an agent package from an agent project.",
	Long:  `Build an agent package from an agent project.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		err := common.ValidateActionServerVersion()
		if err != nil {
			return err
		}
		err = BuildAgentPackage(inputDir, outputDir, agentPackageName, overwriteAgentPackage)
		if err != nil {
			return err
		}
		return nil
	},
}

func init() {
	packageCmd.AddCommand(buildCmd)
	buildCmd.Flags().StringVar(&inputDir, "input-dir", ".", "Set the input directory.")
	buildCmd.Flags().StringVar(&outputDir, "output-dir", ".", "Set the output directory.")
	buildCmd.Flags().StringVar(&agentPackageName, "name", common.AGENT_PACKAGE_DEFAULT_NAME, "Set the package name.")
	buildCmd.Flags().BoolVar(
		&overwriteAgentPackage,
		"overwrite",
		false,
		"If the target .zip is already present it'll be overridden.",
	)
}
