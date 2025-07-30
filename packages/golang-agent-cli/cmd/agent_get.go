package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	rccCommon "github.com/Sema4AI/rcc/common"
	"github.com/Sema4AI/rcc/pathlib"
	"github.com/spf13/cobra"
)

var pathsParam []string

type AgentsOutput struct {
	Project  []*common.AgentProject `json:"project"`
	Deployed []*AgentServer.Agent   `json:"deployed"`
}

var (
	ignoreMissingParam       bool
	agentProjectSettingsPath string
)

// ReadRunbook reads the contents of a runbook file.
func ReadRunbook(runbookPath string) (string, error) {
	if !pathlib.Exists(runbookPath) {
		return "", errors.New("runbook does not exist")
	}
	runbookContent, err := os.ReadFile(runbookPath)
	if err != nil {
		return "", fmt.Errorf("failed to read runbook: %w", err)
	}
	return string(runbookContent), nil
}

// getAgentProjectSpec reads the agent spec from a given path.
func getAgentProjectSpec(path string) (*common.AgentSpec, error) {
	// Check if path exists
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return nil, fmt.Errorf("project directory path does not exist: %s", path)
	}

	spec, err := ReadSpec(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read agent spec from path %s: %w", path, err)
	}

	for i := range spec.AgentPackage.Agents {
		agent := &spec.AgentPackage.Agents[i]

		// We need to read the Runbook file as the file contents can be passed to Agent Server
		runbookContent, err := ReadRunbook(filepath.Join(path, agent.Runbook))
		if err != nil {
			pretty.Error("Error: failed to read runbook %s: %s", agent.Runbook, err)
			return nil, fmt.Errorf("failed to read runbook %s: %w", agent.Runbook, err)
		} else {
			agent.Runbook = runbookContent
		}

		// We need to read the Conversation Guide file as the file contents can be passed to Agent Server
		if agent.ConversationGuide != "" {
			conversationGuideContent, err := common.ReadConversationGuideYAML(filepath.Join(path, agent.ConversationGuide))
			if err == nil {
				// We can ignore the error here as the conversation guide is optional
				agent.Metadata.QuestionGroups = conversationGuideContent
			}
		}
	}
	return spec, nil
}

// getAgentProject reads the agent project from a given path.
func getAgentProject(path string) (*common.AgentProject, error) {
	if path == "" {
		return nil, nil
	}

	spec, err := getAgentProjectSpec(path)

	// We check if spec was returned instead of checking the error, so we are able to ignore the error in case
	// --ignore-missing flag was passed.
	if spec == nil {
		if ignoreMissingParam {
			pretty.Log("ignoring missing agent spec for path: %s, error: %s", path, err)
			return nil, nil
		} else {
			return nil, fmt.Errorf("agent spec from path: %s does not exist, err: %s", path, err)
		}
	}

	if len(spec.AgentPackage.Agents) == 0 {
		return nil, fmt.Errorf("agent spec from path: %s does not contain any agents", path)
	}

	// For now, we only support one Agent per Agent spec.
	agent := spec.AgentPackage.Agents[0]
	agentProject := &common.AgentProject{Path: path, Agent: agent, Exclude: spec.AgentPackage.Exclude}

	return agentProject, nil
}

// getAgentProjects reads the agent projects from a given paths.
func getAgentProjects(paths []string) ([]*common.AgentProject, error) {
	if len(paths) == 0 {
		return nil, nil
	}

	projectSettings, err := common.ReadAgentProjectSettings(agentProjectSettingsPath)
	if err != nil {
		return nil, err
	}

	var allAgentProjects []*common.AgentProject

	for _, path := range paths {
		settingsEntry := projectSettings.GetEntryByProjectPath(path)

		// If the settings entry could not be found, we skip it.
		// This should never happen though, as --paths are passed based on this file in Studio.
		if settingsEntry == nil {
			continue
		}

		agentProject, err := getAgentProject(path)
		if err != nil {
			return nil, err
		}

		// If --ignore-missing was set, we simply skip the missing Agent Project.
		if agentProject == nil {
			continue
		}

		agentProject.AgentID = settingsEntry.AgentId
		allAgentProjects = append(allAgentProjects, agentProject)
	}

	return allAgentProjects, nil
}

// getDeployedAgents reads the deployed agents from a given server URL.
func getDeployedAgents(serverURL string) ([]*AgentServer.Agent, error) {
	client := AgentServer.NewClient(serverURL)
	agents, err := client.GetAgents(true)
	if err != nil {
		return nil, err
	}

	result := make([]*AgentServer.Agent, len(*agents))
	for i := range *agents {
		result[i] = &(*agents)[i]
	}
	return result, nil
}

// CheckAgentsSynchronization checks the synchronization status of the agent projects and the deployed agents.
func CheckAgentsSynchronization(agentProjects []*common.AgentProject, deployedAgents []*AgentServer.Agent) error {
	wg := sync.WaitGroup{}
	var synchronizationErrors []error

	for _, agentProject := range agentProjects {
		wg.Add(1)

		agentProject.Synced = false

		go func() {
			defer wg.Done()

			deployedAgent := common.FindDeployedAgentById(deployedAgents, agentProject.AgentID)

			if deployedAgent == nil {
				return
			}

			err := agentProject.ApplySynchronizationStatus(deployedAgent)
			if err != nil {
				synchronizationErrors = append(synchronizationErrors, err)
			}
		}()
	}

	if len(synchronizationErrors) > 0 {
		return common.ConcatErrors(synchronizationErrors)
	}

	wg.Wait()

	return nil
}

// getAgents reads the agents from the agent server.
func getAgents() error {
	output := AgentsOutput{
		// The local agent uses type from common package which is different from the types used by deployed agent that uses type from client package.
		// The local agent in the file system do not contain the model config values which may include sensitive data.
		// Also advanced config values are missing from the local agent (may contain sensitive data?).
		Project:  []*common.AgentProject{},
		Deployed: []*AgentServer.Agent{},
	}

	deployedAgents, err := getDeployedAgents(agentServerURL)
	if err != nil {
		return err
	}
	if deployedAgents != nil {
		output.Deployed = deployedAgents
	}

	agentProjects, err := getAgentProjects(pathsParam)
	if err != nil {
		return err
	}

	output.Project = append(output.Project, agentProjects...)

	err = CheckAgentsSynchronization(agentProjects, deployedAgents)
	if err != nil {
		return fmt.Errorf("failed to check agents synchronization: %w", err)
	}

	outputJSON, err := json.Marshal(output)
	if err != nil {
		return fmt.Errorf("failed to marshal agents: %w", err)
	}

	rccCommon.Stdout("%s\n", outputJSON)

	return nil
}

var getCmd = &cobra.Command{
	Use:   "get",
	Short: "Get deployed Agents and Agent Projects.",
	Long:  `Get deployed Agents and Agent Projects.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		return getAgents()
	},
}

func init() {
	agentCmd.AddCommand(getCmd)
	getCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
	getCmd.Flags().StringSliceVar(&pathsParam, "paths", []string{}, "Path to local agent projects.")
	getCmd.Flags().BoolVar(&ignoreMissingParam, "ignore-missing", false, "Ignore missing agent projects.")
	getCmd.Flags().StringVar(&agentProjectSettingsPath, "agent-project-settings-path", "", "Path to agent project settings.")
	if err := getCmd.MarkFlagRequired("agent-project-settings-path"); err != nil {
		fmt.Printf("failed to mark flag as required: %+v", err)
	}

}
