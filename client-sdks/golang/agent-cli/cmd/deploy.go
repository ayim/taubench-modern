package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
)

func deployProject(serverURL, projectPath string) error {
	tempPackageDir, err := common.CreateTempDir(fmt.Sprintf("deploy-%s", uuid.New().String()))
	if err != nil {
		return fmt.Errorf("failed to create temp directory: %w", err)
	}

	defer os.RemoveAll(tempPackageDir)

	agentPackageDestPath, err := common.CreateTempDir(fmt.Sprintf("agent-package-%s", uuid.New().String()))
	if err != nil {
		return fmt.Errorf("failed to create temp directory: %w", err)
	}

	defer os.RemoveAll(agentPackageDestPath)

	// To update the project to the agent-server we need to use the updateAgentViaPackage API from the
	// agent-client-go package. This API requires a package file to be uploaded to the agent-server.
	// The temporary package file is created by the buildAgentPackage function.
	// @TODO: we already have a payload available that the agent-server /agents/{agentId} PUT API would accept.
	// Look into adding a new update via payload API to the agent-client-go.
	tempPackageFile := "package.zip"
	tempPackagePath := filepath.Join(tempPackageDir, tempPackageFile)

	err = buildAgentPackage(projectPath, tempPackageDir, tempPackageFile, true)
	if err != nil {
		return fmt.Errorf("failed to build Agent Package: %w", err)
	}

	err = importAgentPackageToAgentServer(agentPackageDestPath, tempPackagePath, serverURL, "", "", "", false)
	if err != nil {
		return err
	}

	return nil
}

var deployCmd = &cobra.Command{
	Use:   "deploy",
	Short: "Deploy Agent Project.",
	Long:  "Deploy Agent Project to Agent Server.",
	RunE: func(cmd *cobra.Command, args []string) error {
		return deployProject(agentServerURL, agentProjectPath)
	},
}

func init() {
	projectCmd.AddCommand(deployCmd)

	deployCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
	deployCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
	deployCmd.MarkFlagRequired("path")
}
