package cmd

import (
	"encoding/json"
	"fmt"

	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common"
	rccCommon "github.com/robocorp/rcc/common"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List the names of existing agents",
	Long:  `List the names of existing agents`,
	RunE: func(cmd *cobra.Command, args []string) error {
		client := AgentServer.NewClient(agentServerURL)
		agents, err := client.GetAgents(false)
		if err != nil {
			return fmt.Errorf("failed to fetch agents: %w", err)
		}

		agentNames := []string{}
		for _, agent := range *agents {
			agentNames = append(agentNames, agent.Name)
		}

		agentNamesJson, err := json.Marshal(agentNames)
		if err != nil {
			return fmt.Errorf("failed to marshal agent names: %w", err)
		}
		rccCommon.Stdout("%s\n", agentNamesJson)
		return nil
	},
}

func init() {
	projectCmd.AddCommand(listCmd)
	listCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
}
