//go:build integration
// +build integration

package integration

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"testing"

	acg "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
	"github.com/stretchr/testify/require"
)

var (
	baseURL      string
	skipCleanup  bool
	openAIAPIKey string
	agentCounter int
)

func init() {
	flag.StringVar(&baseURL, "base-url", "", "Base URL of the agent server")
	flag.BoolVar(&skipCleanup, "skip-cleanup", false, "Skip cleanup after tests.")
	flag.StringVar(&openAIAPIKey, "openai-api-key", "", "OpenAI API key")
}

func TestMain(m *testing.M) {
	flag.Parse()
	if baseURL == "" {
		// no flag provided, check the environment variable
		baseURL = os.Getenv("S4_AGENT_SERVER_BASE_URL")
		// if still empty, use the default
		if baseURL == "" {
			baseURL = "http://localhost:8000"
		}
	}

	if openAIAPIKey == "" {
		// no flag provided, check the environment variable
		openAIAPIKey = os.Getenv("OPENAI_API_KEY")
		if openAIAPIKey == "" {
			panic("OpenAI API key is not set. Please provide it using the --openai-api-key flag or the " +
				"OPENAI_API_KEY environment variable.")
		}
	}

	// Setup: Run before any test
	setup()

	// Run the tests
	code := m.Run()

	// Teardown: Run after all tests
	teardown()

	os.Exit(code)
}

var agentsToCleanUp []string
var threadsToCleanUp []string

func registerAgentForCleanup(agentID string) {
	agentsToCleanUp = append(agentsToCleanUp, agentID)
}

func registerThreadForCleanup(threadID string) {
	threadsToCleanUp = append(threadsToCleanUp, threadID)
}

func setup() {
	fmt.Println("Setup before tests")
	// Additional setup logic if needed
}

func teardown() {
	client := acg.NewClient(baseURL)
	fmt.Println("Teardown after tests")
	if !skipCleanup {
		fmt.Println("Cleaning up agents.")
		for _, agentID := range agentsToCleanUp {
			fmt.Printf("Deleting agent %s\n", agentID)
			if err := client.DeleteAgent(agentID); err != nil {
				fmt.Println("Error deleting agent: ", err)
			}
		}

		fmt.Println("Cleaning up threads.")
		for _, threadID := range threadsToCleanUp {
			fmt.Printf("Deleting thread %s\n", threadID)
			if err := client.DeleteThread(threadID); err != nil {
				fmt.Println("Error deleting thread: ", err)
			}
		}
	}
}

func createBasicAgent(t *testing.T) *acg.Agent {
	agentCounter++
	uniqueName := fmt.Sprintf("Integration Test Agent %d", agentCounter)
	actionPackages := []acg.AgentActionPackage{}
	mcpServers := []acg.McpServer{}
	payload := acg.AgentCreatePayload{
		Name:        uniqueName,
		Description: "This is an agent created by an integration test.",
		Runbook:     acg.DEFAULT_RUNBOOK,
		Version:     "0.0.1",
		Model: acg.AgentModel{
			Provider: acg.OpenAI,
			Name:     "gpt-4o",
			Config:   map[string]interface{}{"openai_api_key": openAIAPIKey},
		},
		AdvancedConfig: acg.AgentAdvancedConfig{
			Architecture: acg.AgentKind,
			Reasoning:    acg.ReasoningDisabled,
		},
		ActionPackages: actionPackages,
		McpServers:     mcpServers,
		Metadata: acg.AgentMetadata{
			Mode: acg.ConversationalMode,
		},
	}
	client := acg.NewClient(baseURL)
	agent, err := client.CreateAgent(payload)
	require.NoError(t, err)
	require.NotEmpty(t, agent.ID)

	registerAgentForCleanup(agent.ID)

	return agent
}

func createBasicThread(t *testing.T, agentID string) *acg.Thread {
	threadReq := acg.ThreadRequest{
		AgentID:         agentID,
		Name:            "Integration Test Welcome",
		StartingMessage: "Hello, how can I help you?",
	}
	client := acg.NewClient(baseURL)
	thread, err := client.CreateThread(threadReq)
	require.NoError(t, err)
	require.NotEmpty(t, thread.ThreadID)
	registerThreadForCleanup(thread.ThreadID)

	return thread
}

func TestCreateDeleteAgent(t *testing.T) {
	client := acg.NewClient(baseURL)
	agent := createBasicAgent(t)

	// delete the agent
	err := client.DeleteAgent(agent.ID)
	require.NoError(t, err)
}

func TestFetchAgents(t *testing.T) {
	client := acg.NewClient(baseURL)
	agents, err := client.GetAgents(true)
	require.NoError(t, err)

	jsonStr, err := json.MarshalIndent(agents, "", "  ")
	require.NoError(t, err)
	t.Log(string(jsonStr))
}

func TestFetchThreadState(t *testing.T) {
	client := acg.NewClient(baseURL)
	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	threadState, err := client.GetThreadState(thread.ThreadID)
	require.NoError(t, err)

	jsonStr, err := json.MarshalIndent(threadState, "", "  ")
	require.NoError(t, err)
	t.Log(string(jsonStr))
}

func TestStream(t *testing.T) {
	client := acg.NewClient(baseURL)
	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	var input []acg.ChatMessage
	msg := acg.NewChatMessage("human", "Tell me something I don't know.")
	input = append(input, msg)
	req := acg.StreamRequest{
		ThreadID: thread.ThreadID,
		Input:    input,
	}

	msgCount := 0
	err := client.Stream(req, func(message string) {
		msgCount++
	})
	require.NoError(t, err)
	require.Greater(t, msgCount, 0)
}

func TestAsyncInvoke(t *testing.T) {
	client := acg.NewClient(baseURL)
	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	var input []acg.ChatMessage
	msg := acg.NewChatMessage("human", "Tell me something I don't know.")
	input = append(input, msg)
	req := acg.CreateRunPayload{
		ThreadID: thread.ThreadID,
		Input:    input,
	}

	resp, err := client.InvokeAsync(req)
	require.NoError(t, err)
	require.NotEmpty(t, resp.RunID)
}

func TestGetRunStatus(t *testing.T) {
	// Create a InvokeAsync and then get the run status
	client := acg.NewClient(baseURL)
	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	var input []acg.ChatMessage
	msg := acg.NewChatMessage("human", "Tell me something I don't know.")
	input = append(input, msg)
	req := acg.CreateRunPayload{
		ThreadID: thread.ThreadID,
		Input:    input,
	}

	resp, err := client.InvokeAsync(req)

	require.NoError(t, err)
	require.NotEmpty(t, resp.RunID)

	runStatusResp, err := client.GetRunStatus(resp.RunID)
	require.NoError(t, err)
	require.NotEmpty(t, runStatusResp.Status)
}

func TestSimulateStudio(t *testing.T) {
	client := acg.NewClient(baseURL)
	_, err := client.GetAgents(true)
	require.NoError(t, err)

	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	_, err = client.GetThreadState(thread.ThreadID)
	require.NoError(t, err)

	var input []acg.ChatMessage
	msg := acg.NewChatMessage("human", "Tell me something I don't know.")
	input = append(input, msg)
	req := acg.StreamRequest{
		ThreadID: thread.ThreadID,
		Input:    input,
	}

	msgCount := 0
	err = client.Stream(req, func(message string) {
		msgCount++
	})
	require.NoError(t, err)
	require.Greater(t, msgCount, 0)

	_, err = client.GetThreadState(thread.ThreadID)
	require.NoError(t, err)

	_, err = client.GetThreads()
	require.NoError(t, err)
}

func TestSimulateStudioWithInvoke(t *testing.T) {
	client := acg.NewClient(baseURL)
	_, err := client.GetAgents(true)
	require.NoError(t, err)

	agent := createBasicAgent(t)
	thread := createBasicThread(t, agent.ID)

	_, err = client.GetThreadState(thread.ThreadID)
	require.NoError(t, err)

	var input []acg.ChatMessage
	msg := acg.NewChatMessage("human", "Tell me something I don't know.")
	input = append(input, msg)
	req := acg.StreamRequest{
		ThreadID: thread.ThreadID,
		Input:    input,
	}

	_, err = client.Invoke(req)
	require.NoError(t, err)

	_, err = client.GetThreadState(thread.ThreadID)
	require.NoError(t, err)

	_, err = client.GetThreads()
	require.NoError(t, err)
}
