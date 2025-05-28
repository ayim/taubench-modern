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

	"github.com/Sema4AI/agents-spec/cli/common/glob"

	"github.com/Sema4AI/agents-spec/cli/common"
	"github.com/robocorp/rcc/pathlib"
	"github.com/spf13/cobra"
	"gopkg.in/yaml.v2"
)

func zipDir(sourceDir, targetZip string) error {
	// read the agent spec file to get the excluded files
	spec, err := readSpec(sourceDir)
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

	logVerbose("buildActionPackage:")
	logVerbose("- sourceDir: %+v", sourceDir)
	logVerbose("- tempDir: %+v", tempDir)
	logVerbose("- targetZip: %+v", targetZip)

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

	logVerbose("[Action Server cmd]: %+v", cmd)
	err = cmd.Run()

	logVerbose("[Action Server stdout]: %+v", stdout.String())
	logVerbose("[Action Server stderr]:\n%+v", stderr.String())
	if err != nil {
		return fmt.Errorf("[buildActionPackage] failed to build action package: %w", err)
	}

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

	logVerbose("Action Package built")
	return nil
}

func buildActionPackages(spec *common.AgentSpec, agentProjectActionsPath string) error {
	// Map of original action project's path within agent package and updated path
	// after building the action package. E.g.: Sema4.ai/greeter : Sema4.ai/greeter.zip.
	updatedPaths := make(map[string]string)

	log("Building Action Packages...")
	for agentIndex, agent := range spec.AgentPackage.Agents {
		for actionIndex, act := range agent.ActionPackages {
			targetPath, ok := updatedPaths[act.Path]
			if !ok {
				log("- Action Package Path: %s", act.Path)
				sourcePath := filepath.Join(agentProjectActionsPath, act.Path)
				targetPath = filepath.Join(act.Organization, common.KebabCase(act.Name), act.Version+".zip")
				targetZipFile := filepath.Join(agentProjectActionsPath, targetPath)
				logVerbose("Build action package from: %+v to: %s", sourcePath, targetZipFile)
				err := buildActionPackage(sourcePath, targetZipFile)
				if err != nil {
					return fmt.Errorf("[buildActionPackages] failed to build action package: %w", err)
				}

				targetPath = filepath.ToSlash(targetPath)
				updatedPaths[act.Path] = targetPath
				log("  - Done with: %s", act.Path)
			}

			spec.AgentPackage.Agents[agentIndex].ActionPackages[actionIndex] = common.AgentActionPackage{
				Path:         targetPath,
				Type:         common.ActionPackageZip,
				Name:         act.Name,
				Organization: act.Organization,
				Version:      act.Version,
				Whitelist:    act.Whitelist,
			}
		}
	}
	log("Action Packages built")

	prettySpec, err := json.MarshalIndent(spec, "", "  ")
	if err != nil {
		logVerbose("agent-spec json parsing failed on: %w", err)
	}
	logVerbose("agent-spec:\n%s", string(prettySpec))
	return nil
}

func readSpec(agentPackageDir string) (*common.AgentSpec, error) {
	var spec common.AgentSpec
	specPath := filepath.Join(agentPackageDir, common.AGENT_PROJECT_SPEC_FILE)
	data, err := os.ReadFile(specPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("%s not found", specPath)
		}
		return nil, fmt.Errorf("[readSpec] failed to read spec YAML file: %w", err)
	}
	if err := yaml.Unmarshal(data, &spec); err != nil {
		return nil, fmt.Errorf("[readSpec] failed to unmarshal YAML: %v", err)
	}
	return &spec, nil
}

func writeSpec(spec *common.AgentSpec, agentPackageDir string) error {
	data, err := yaml.Marshal(spec)
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

func buildAgentPackage(inputDir, outputDir, name string, overwriteAgentPackage bool) error {
	packagePath := filepath.Join(outputDir, name)
	if pathlib.Exists(packagePath) {
		if overwriteAgentPackage {
			if err := os.Remove(packagePath); err != nil {
				return fmt.Errorf("[buildAgentPackage] failed to remove existing package: %w", err)
			}
		} else {
			return fmt.Errorf("[buildAgentPackage] package %s already exists", packagePath)
		}
	}

	spec, err := readSpec(inputDir)
	if err != nil {
		return err
	}

	tempDir, err := common.CreateTempDir("build")
	if err != nil {
		return fmt.Errorf("[buildAgentPackage] failed to create temporary directory: %w", err)
	}
	if err := common.CopyDir(inputDir, tempDir, false); err != nil {
		return fmt.Errorf("[buildAgentPackage] failed to copy directory %s to %s: %w", filepath.Dir(""), tempDir, err)
	}
	defer os.RemoveAll(tempDir)

	log("Creating agent package metadata file")
	err = createAgentPackageMetadataFile(tempDir)
	if err != nil {
		return fmt.Errorf("[buildAgentPackage] failed to create agent package metadata file: %w", err)
	}
	log("Agent package metadata file created")

	err = buildActionPackages(spec, common.AgentProjectActionsLocation(tempDir))
	if err != nil {
		return err
	}

	err = writeSpec(spec, tempDir)
	if err != nil {
		return err
	}

	err = os.MkdirAll(outputDir, 0o755)
	if err != nil {
		return fmt.Errorf("[buildAgentPackage] failed to create output directory: %w", err)
	}

	err = zipDir(tempDir, packagePath)
	if err != nil {
		return err
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
		err = buildAgentPackage(inputDir, outputDir, agentPackageName, overwriteAgentPackage)
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
