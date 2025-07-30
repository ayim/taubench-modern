package cmd

import (
	"encoding/json"
	"fmt"
	"os"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/spf13/cobra"
)

func updateAgentProjectFiles(agent *AgentServer.Agent, path string) error {
	state := SpecState{
		assistantKnowledge:          map[string][]common.SpecAgentKnowledge{},
		assistantActionPackages:     map[string][]common.SpecAgentActionPackage{},
		assistantMcpServer:          map[string][]common.SpecMcpServer{},
		assistantRunbooks:           map[string]string{},
		AssistantConversationGuides: map[string]string{},
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

	err = state.CreateConversationGuideFile(agentArray, path)
	if err != nil {
		return err
	}

	err = state.createMcpServers(agentArray)
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
		return deployProjectFromAgent(agentServerURL, agent)
	}

	return nil
}

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update an Agent.",
	Long:  `Update an Agent by providing the agent as a payload.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if agentPayloadPathVar == "" && agentPayloadBase64Var == "" {
			return fmt.Errorf("either --payloadPath or --payloadBase64 is required")
		}
		if agentPayloadPathVar != "" && agentPayloadBase64Var != "" {
			return fmt.Errorf("only one of --payloadPath or --payloadBase64 can be provided, not both")
		}

		var data []byte
		var err error
		if agentPayloadPathVar != "" {
			// Read the payload file.
			data, err = os.ReadFile(agentPayloadPathVar)
			if err != nil {
				return fmt.Errorf("failed to read payload file: %w", err)
			}
		} else {
			// Decode base64 payload
			data, err = common.DecodeBase64(agentPayloadBase64Var)
			if err != nil {
				return fmt.Errorf("failed to decode base64 payload: %w", err)
			}
		}

		// Create a new instance and unmarshal into it
		payload := &AgentServer.Agent{}
		if err := json.Unmarshal(data, payload); err != nil {
			return fmt.Errorf("failed to parse agent payload: %w", err)
		}

		// Update the agent
		return updateAgent(payload)
	},
}

func init() {
	agentCmd.AddCommand(updateCmd)
	updateCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
	updateCmd.Flags().StringVar(&agentPayloadPathVar, "payloadPath", "", "Path to the payload file (JSON). Mutually exclusive with --payloadBase64.")
	updateCmd.Flags().StringVar(&agentPayloadBase64Var, "payloadBase64", "", "Base64-encoded payload string. Mutually exclusive with --payloadPath.")
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
