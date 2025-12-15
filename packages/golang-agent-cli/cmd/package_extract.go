package cmd

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
)

func extractActionPackage(packagePath, targetDir string) error {
	// FOR SUPPORT: action-server extract build --output-dir <targetDir> <packagePath>
	cmd := exec.Command(
		common.GetActionServerBin(),
		"package",
		"extract",
		"--override",
		"--output-dir",
		targetDir,
		filepath.Base(packagePath),
	)
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Dir = filepath.Dir(packagePath)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	pretty.LogIfVerbose("[Action Server cmd]: %+v", cmd)
	err := cmd.Run()
	pretty.LogIfVerbose("[Action Server stdout]: %+v", stdout.String())
	pretty.LogIfVerbose("[Action Server stderr]:\n%+v", stderr.String())
	if err != nil {
		return fmt.Errorf("[extractActionPackage] failed to extract action package: %w", err)
	}

	return nil
}

func extractActionPackages(spec *common.AgentSpec, agentProjectActionsPath string) error {
	// Map of action package's path within agent package and updated path
	// after extracting the action package. E.g.: Sema4.ai/greeter.zip : Sema4.ai/greeter.
	updatedPaths := make(map[string]string)

	for agentIndex, agent := range spec.AgentPackage.Agents {
		pretty.LogIfVerbose("[extractActionPackages] dealing with agent: %+v", agent.Name)
		pretty.LogIfVerbose("[extractActionPackages] agent has %+v action packages", len(agent.ActionPackages))
		for actionIndex, act := range agent.ActionPackages {
			pretty.LogIfVerbose("[extractActionPackages] handling action package: %+v", act.Name)
			newPath, ok := updatedPaths[act.Path]
			if !ok {
				zipPath := filepath.Join(agentProjectActionsPath, act.Path)
				targetPath := filepath.Join(agentProjectActionsPath, act.Organization, common.Slugify(act.Name))

				pretty.LogIfVerbose("[extractActionPackages] extracting from [%+v] to [%+v]", zipPath, targetPath)
				err := extractActionPackage(zipPath, targetPath)
				if err != nil {
					return fmt.Errorf("[extractActionPackages] failed from:%s to: %s error: %w", zipPath, targetPath, err)
				}

				pretty.LogIfVerbose("[extractActionPackages] cleaning up zip...")
				if err := os.RemoveAll(zipPath); err != nil {
					return fmt.Errorf("[extractActionPackages] failed to remove action package zip: %s error: %w", zipPath, err)
				}
				newPath = filepath.ToSlash(filepath.Join(act.Organization, common.Slugify(act.Name)))
				updatedPaths[act.Path] = newPath
				pretty.LogIfVerbose("[extractActionPackages] action package new path: %+v", newPath)
			}

			spec.AgentPackage.Agents[agentIndex].ActionPackages[actionIndex] = common.SpecAgentActionPackage{
				Name:         act.Name,
				Organization: act.Organization,
				Version:      act.Version,
				Whitelist:    act.Whitelist,
				Path:         newPath,
				Type:         common.ActionPackageFolder,
			}
		}
	}
	return nil
}

func extractAgentPackage(agentPackagePath, outputDir string, overwriteAgentProject bool) error {
	if common.FileExists(outputDir) && !pathlib.IsEmptyDir(outputDir) && !overwriteAgentProject {
		return fmt.Errorf("[extractAgentPackage] directory already exists and is not empty")
	}

	tempDir, err := common.CreateTempDir("extract")
	if err != nil {
		return fmt.Errorf("[extractAgentPackage] failed to create temporary directory: %w", err)
	}
	defer os.RemoveAll(tempDir)
	pretty.LogIfVerbose("[extractAgentPackage] will use the temp dir @: %+v", tempDir)
	if err = common.UnzipFile(agentPackagePath, tempDir); err != nil {
		return err
	}

	pretty.LogIfVerbose("[extractAgentPackage] unzipped successfully... reading spec...")
	spec, err := ReadSpec(tempDir)
	if err != nil {
		return err
	}

	pretty.LogIfVerbose("[extractAgentPackage] extracting action packages...")
	err = extractActionPackages(spec, common.AgentProjectActionsLocation(tempDir))
	if err != nil {
		return err
	}

	pretty.LogIfVerbose("[extractAgentPackage] writing spec...")
	err = WriteSpec(spec, tempDir)
	if err != nil {
		return err
	}

	err = common.CopyDir(tempDir, outputDir, true)
	if err != nil {
		return fmt.Errorf("[extractAgentPackage] failed to copy directory %s to %s: %w", tempDir, outputDir, err)
	}

	pretty.LogIfVerbose("[extractAgentPackage] extraction succeeded!")
	return nil
}

var extractCmd = &cobra.Command{
	Use:   "extract",
	Short: "Extract an agent package into an agent project.",
	Long:  `Extract an agent package into an agent project.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		err := common.ValidateActionServerVersion()
		if err != nil {
			return err
		}
		err = extractAgentPackage(agentPackagePath, outputDir, overwriteAgentProject)
		if err != nil {
			return err
		}
		return nil
	},
}

func init() {
	packageCmd.AddCommand(extractCmd)
	extractCmd.Flags().StringVar(&agentPackagePath, "package", common.AGENT_PACKAGE_DEFAULT_NAME, "The .zip file that should be extracted.")
	if err := extractCmd.MarkFlagRequired("package"); err != nil {
		fmt.Printf("failed to mark flag as required: %+v", err)
	}
	extractCmd.Flags().StringVar(&outputDir, "output-dir", ".", "Set the output directory.")
	extractCmd.Flags().BoolVar(&overwriteAgentProject, "overwrite", false, "The contents will be extracted to a non-empty directory")
}
