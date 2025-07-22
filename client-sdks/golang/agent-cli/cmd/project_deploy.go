package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/pretty"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
)

func deployProjectFromPath(serverURL, projectPath string) error {
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

	// Important: When we deploy the Agent to the Agent Server, because we do it through the package endpoint,
	// we don't need to filter out the values from the Spec as those values will become the ones passed along to
	// the Agent Server internal tools
	pretty.LogIfVerbose("[deployProject] building agent package @: %+v", tempPackageDir)
	err = buildAgentPackage(projectPath, tempPackageDir, tempPackageFile, true)
	if err != nil {
		return fmt.Errorf("failed to build Agent Package: %w", err)
	}

	pretty.LogIfVerbose("[deployProject] import agent package to server @: %+v", serverURL)
	pretty.LogIfVerbose("[deployProject] import agent package dest @: %+v", agentPackageDestPath)
	err = importAgentPackageToAgentServer(agentPackageDestPath, tempPackagePath, serverURL, "", "", "", false)
	if err != nil {
		return err
	}

	return nil
}

func deployProjectFromAgent(serverURL string, agent *AgentServer.Agent) error {
	client := AgentServer.NewClient(serverURL)
	agentPayload := AgentServer.BuildAgentPayload(agent)

	_, err := createOrUpdateAgent(agentPayload, client)
	if err != nil {
		return fmt.Errorf("failed to create or update agent: %w", err)
	}
	return nil
}

var deployCmd = &cobra.Command{
	Use:   "deploy",
	Short: "Deploy Agent Project.",
	Long:  "Deploy Agent Project to Agent Server.",
	RunE: func(cmd *cobra.Command, args []string) error {
		return deployProjectFromPath(agentServerURL, agentProjectPath)
	},
}

func init() {
	projectCmd.AddCommand(deployCmd)

	deployCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
	deployCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
	if err := deployCmd.MarkFlagRequired("path"); err != nil {
		fmt.Printf("failed to mark flag as required: %+v", err)
	}
}
