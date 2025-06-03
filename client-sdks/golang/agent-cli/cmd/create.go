package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common"
	rccCommon "github.com/Sema4AI/rcc/common"
	"github.com/spf13/cobra"
)

var (
	deployAgentToServer bool
	agentPayloadPathVar string
)

func validateAgentPayload(payload *AgentServer.AgentCreatePayload) error {
	// Do minimal validation here, as long as the payload can be parsed
	// we can just create the agent to file system which will make it configurable
	// later in the studio side.
	//
	// The server can run the validation on it's own.
	if payload.Name == "" {
		return errors.New("name is required")
	}

	if payload.Version == "" {
		return errors.New("version is required")
	}

	if payload.Runbook == "" {
		return errors.New("runbook is required")
	}

	if payload.Model.Name == "" {
		return errors.New("model name is required")
	}

	// TODO: enumerate provider values from the agent-server client
	if payload.Model.Provider == "" {
		return errors.New("invalid model provider")
	}

	if payload.Model.Config == nil {
		return errors.New("model config is required")
	}

	// TODO: enumerate reason values from the agent-server client
	if payload.AdvancedConfig.Reasoning == "" {
		return errors.New("reasoning is required")
	}

	if payload.ActionPackages == nil {
		return errors.New("action packages list is required")
	}

	if payload.McpServers == nil {
		return errors.New("mcp servers list is required")
	}

	if payload.Metadata.Mode == "" {
		return errors.New("mode is required")
	}

	return nil
}

func deployAgent(agent *AgentServer.Agent, serverURL string) (*AgentServer.Agent, error) {
	client := AgentServer.NewClient(serverURL)
	payload := AgentServer.AgentCreatePayload{
		Name:           agent.Name,
		Description:    agent.Description,
		Version:        agent.Version,
		Runbook:        agent.Runbook,
		Model:          agent.Model,
		ActionPackages: agent.ActionPackages,
		McpServers:     agent.McpServers,
		AdvancedConfig: agent.AdvancedConfig,
		Metadata:       agent.Metadata,
	}

	return client.CreateAgent(payload)
}

func defineAgent(payload *AgentServer.AgentCreatePayload) (*AgentServer.Agent, error) {
	// Make sure McpServers is not nil when defining the Agent.
	if payload.McpServers == nil {
		payload.McpServers = []AgentServer.McpServer{}
	}

	// Validate provided payload
	err := validateAgentPayload(payload)
	if err != nil {
		return nil, err
	}

	// Return agent from payload
	return &AgentServer.Agent{
		ID:             "",
		UserID:         "",
		Name:           payload.Name,
		Description:    payload.Description,
		Version:        payload.Version,
		Runbook:        payload.Runbook,
		Model:          payload.Model,
		ActionPackages: payload.ActionPackages,
		McpServers:     payload.McpServers,
		AdvancedConfig: payload.AdvancedConfig,
		Metadata:       payload.Metadata,
		Files:          nil,
	}, nil
}

func createAgent(projectPath string, payload *AgentServer.AgentCreatePayload, serverURL string, deployToServer bool) error {
	// Make sure the output directory does not exist or is clean
	outputDir := filepath.Clean(projectPath)
	if _, err := os.Stat(outputDir); os.IsExist(err) {
		return errors.New("output directory already exists")
	}

	agent, err := defineAgent(payload)
	if err != nil {
		return err
	}

	err = createAgentProject([]AgentServer.Agent{*agent}, outputDir)
	if err != nil {
		return err
	}

	if deployToServer {
		deployedAgent, err := deployAgent(agent, serverURL)
		if err != nil {
			// Clean up the local agent project if the deploy fails as the caller could not know
			// if the agent was created locally or not.
			deleteErr := deleteAgentProject(outputDir)
			if deleteErr != nil {
				logVerbose("failed to clean up local agent project")
			}
			return err
		}

		outputJSON, err := json.Marshal(deployedAgent)
		if err != nil {
			return fmt.Errorf("failed to marshal agent: %w", err)
		}

		rccCommon.Stdout("%s\n", outputJSON)
	}

	return nil
}

var createCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new Agent.",
	Long:  `Create a new Agent by providing the Agent as a payload.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		var payload *AgentServer.AgentCreatePayload

		if agentPayloadPathVar == "" {
			return fmt.Errorf("payload path is required")
		}

		// Read the payload file.
		data, err := os.ReadFile(agentPayloadPathVar)
		if err != nil {
			return fmt.Errorf("failed to read payload file: %w", err)
		}

		// Create a new instance and unmarshal into it
		payload = &AgentServer.AgentCreatePayload{}
		if err := json.Unmarshal(data, payload); err != nil {
			return fmt.Errorf("failed to parse JSON: %w", err)
		}

		return createAgent(agentProjectPath, payload, agentServerURL, deployAgentToServer)
	},
}

func init() {
	agentCmd.AddCommand(createCmd)
	createCmd.Flags().StringVar(&agentProjectPath, "path", common.AGENT_PROJECT_DEFAULT_NAME, "Set the project path.")
	createCmd.Flags().StringVar(&agentPayloadPathVar, "payloadPath", "", "Path to the payload file (JSON).")
	createCmd.MarkFlagRequired("payloadPath")
	createCmd.Flags().BoolVar(
		&deployAgentToServer,
		"deploy",
		false,
		"Deploy directly to the agent server",
	)
	createCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
}
