package cmd

import (
	"fmt"
	"os"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/pretty"
	"github.com/spf13/cobra"
)

var (
	pathParam    string
	agentIdParam string
)

func deleteAgentFromAgentServer(agentID, serverURL string) error {
	pretty.LogIfVerbose("[deleteAgentFromAgentServer]: %s - %s", agentID, serverURL)

	client := AgentServer.NewClient(serverURL)

	err := client.DeleteAgent(agentID)
	if err != nil {
		return fmt.Errorf("failed to delete agent from server: %w", err)
	}

	return nil
}

func deleteAgentProject(path string) error {
	pretty.LogIfVerbose("[deleteAgentProject] locally from path: %s", path)

	if _, err := os.Stat(path); os.IsNotExist(err) {
		return fmt.Errorf("path does not exist: %s", path)
	}

	agent, err := getAgentProject(path)
	if err != nil {
		return err
	}

	if agent == nil {
		return fmt.Errorf("agent not found in path: %s", path)
	}

	err = os.RemoveAll(path)
	if err != nil {
		return fmt.Errorf("failed to delete agent project: %w", err)
	}

	return nil
}

func deleteAgent(path string, agentId string, serverURL string) error {
	pretty.LogIfVerbose("[deleteAgent] with project path: %s, agent ID: %s", path, agentId)

	if agentId != "" {
		err := deleteDeployedAgentByID(agentId, serverURL)
		if err != nil {
			return err
		}
	}

	if path != "" {
		err := deleteAgentProject(path)
		if err != nil {
			return err
		}
	}

	return nil
}

func deleteDeployedAgentByID(agentID string, serverURL string) error {
	pretty.LogIfVerbose("[deleteDeployedAgentByID] agent by ID: %s", agentID)

	return deleteAgentFromAgentServer(agentID, serverURL)
}

var deleteCmd = &cobra.Command{
	Use:   "delete",
	Short: "Delete Agent.",
	Long:  `Delete Agent.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		return deleteAgent(pathParam, agentIdParam, agentServerURL)
	},
}

func init() {
	agentCmd.AddCommand(deleteCmd)
	deleteCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
	deleteCmd.Flags().StringVar(&pathParam, "path", "", "Path to the local agent project.")
	deleteCmd.Flags().StringVar(&agentIdParam, "agent-id", "", "Deployed Agent ID.")
	deleteCmd.MarkFlagsOneRequired("path", "agent-id")
}
