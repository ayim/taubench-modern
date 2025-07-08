package cmd

import (
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
	"github.com/spf13/cobra"
)

var newCmd = &cobra.Command{
	Use:   "new",
	Short: "Create a new Agent Project from scratch.",
	Long:  "Create a new Agent Project from scratch.",
	RunE: func(cmd *cobra.Command, args []string) error {
		agent := &AgentServer.Agent{
			ID:          "id",
			UserID:      "user_id",
			Name:        "New Agent",
			Description: "New Agent Description",
			Runbook:     common.DEFAULT_RUNBOOK,
			Version:     "0.0.1",
			Model:       AgentServer.AgentModel{Provider: AgentServer.OpenAI, Name: "gpt-4o", Config: map[string]interface{}{}},
			AdvancedConfig: AgentServer.AgentAdvancedConfig{
				Architecture: AgentServer.AgentKind,
				Reasoning:    AgentServer.ReasoningDisabled,
			},
			ActionPackages: []AgentServer.AgentActionPackage{},
			Files:          []AgentServer.AgentFile{},
			Metadata:       AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode},
		}

		return createAgentProject([]AgentServer.Agent{*agent}, agentProjectPath)
	},
}

func init() {
	projectCmd.AddCommand(newCmd)
	newCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
}
