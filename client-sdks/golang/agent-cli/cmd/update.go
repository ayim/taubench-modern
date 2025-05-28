package cmd

import (
	"encoding/json"
	"fmt"
	"os"

	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common"
	"github.com/spf13/cobra"
)

func updateAgentProjectFiles(agent *AgentServer.Agent, path string) error {
	state := specState{
		assistantKnowledge:      map[string][]common.AgentKnowledge{},
		assistantActionPackages: map[string][]common.AgentActionPackage{},
		assistantRunbooks:       map[string]string{},
	}

	agentArray := []AgentServer.Agent{*agent}

	err := state.createKnowledgeDir(agentArray, path)
	if err != nil {
		return err
	}

	err = state.createActionsDir(agentArray, path)
	if err != nil {
		return err
	}

	err = state.createRunbookFile(agentArray, path)
	if err != nil {
		return err
	}

	err = state.createSpecFile(agentArray, path)
	if err != nil {
		return err
	}

	return nil
}

func updateAgent(agent *AgentServer.Agent) error {
	err := updateAgentProjectFiles(agent, agentProjectPath)
	if err != nil {
		return err
	}

	if deployAgentToServer {
		return deployProject(agentServerURL, agentProjectPath)
	}

	return nil
}

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update an Agent.",
	Long:  `Update an Agent by providing the agent as a payload.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		var payload AgentServer.Agent
		if agentPayloadPathVar != "" {
			// Read the payload file.
			data, err := os.ReadFile(agentPayloadPathVar)
			if err != nil {
				return fmt.Errorf("failed to read payload file: %w", err)
			}

			// Unmarshal the JSON payload.

			if err := json.Unmarshal(data, &payload); err != nil {
				return fmt.Errorf("failed to parse JSON: %w", err)
			}
		}

		return updateAgent(&payload)
	},
}

func init() {
	agentCmd.AddCommand(updateCmd)
	updateCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
	updateCmd.Flags().StringVar(&agentPayloadPathVar, "payloadPath", "", "Path to the payload file (JSON).")
	updateCmd.MarkFlagRequired("payload")
	updateCmd.Flags().BoolVar(
		&deployAgentToServer,
		"deploy",
		false,
		"Deploy directly to the agent server",
	)
	updateCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
}
