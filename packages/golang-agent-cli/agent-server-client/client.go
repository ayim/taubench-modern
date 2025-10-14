package agent_server_client

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// Client is the main entrypoint for interacting with the Sema4.ai Agent Server API.
type Client struct {
	BaseURL string
}

// NewClient creates a new Sema4.ai Agent Server API client.
// baseUUR represents the API URL of the server with which to interact.
func NewClient(baseURL string) *Client {
	return &Client{BaseURL: baseURL}
}

func NewClientFromEnv() *Client {
	baseURL := os.Getenv("S4_AGENT_SERVER_BASE_URL")
	if baseURL == "" {
		panic("S4_AGENT_SERVER_BASE_URL environment variable must be set")
	}
	return NewClient(baseURL)
}

func (c *Client) CreateAgentViaPackage(req AgentPayloadPackage) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/agents/package", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to create agent: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to create agent: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
}

func (c *Client) UpdateAgentViaPackage(agentID string, req AgentPayloadPackage) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.put(fmt.Sprintf("/api/v2/agents/package/%s", agentID), bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to update agent: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to update agent: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
}

// CreateAgent creates a new agent given an AgentCreatePayload object.
func (c *Client) CreateAgent(req AgentPayload) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/agents/", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to create agent: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to create agent: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
}

// UpdateAgent updates an agent given an AgentUpdatePayload object.
func (c *Client) UpdateAgent(agentID string, req AgentPayload) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.put(fmt.Sprintf("/api/v2/agents/%s", agentID), bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to update agent: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to update agent: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
}

// DeleteAgent deletes an agent given an `agentID`.
func (c *Client) DeleteAgent(agentID string) error {
	resp, err := c.delete(fmt.Sprintf("/api/v2/agents/%s", agentID))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to delete agent: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return NewAgentError(fmt.Errorf("failed to delete agent: %s", string(body)), resp.StatusCode)
	}
	return nil
}

// GetAgentsWithFiles returns a set of agents along with attached files given a set of IDs.
func (c *Client) GetAgentsWithFiles(agentIDs []string, raw bool) ([]Agent, error) {
	var wg sync.WaitGroup
	agents := make([]Agent, len(agentIDs))
	errors := make([]error, len(agentIDs))

	for i, id := range agentIDs {
		wg.Add(1)
		go func(index int, agentID string) {
			defer wg.Done()
			agent, err := c.GetAgent(agentID, raw)
			if err != nil {
				errors[index] = NewAgentError(fmt.Errorf("failed to fetch agent %s: %w", agentID, err), http.StatusInternalServerError)
				return
			}
			files, err := c.fetchFiles(agentID)
			if err != nil {
				errors[index] = NewAgentError(fmt.Errorf("failed to fetch files for agent %s: %w", agentID, err), http.StatusInternalServerError)
				return
			}
			agent.Files = files
			agents[index] = *agent
		}(i, id)
	}

	wg.Wait()

	for _, err := range errors {
		if err != nil {
			// Return the first error encountered
			return nil, err
		}
	}

	return agents, nil
}

// GetAgent returns an agent given an `agentID`.
func (c *Client) GetAgent(agentID string, raw bool) (*Agent, error) {
	var url string
	if raw {
		url = fmt.Sprintf("%s/api/v2/agents/%s/raw", c.BaseURL, agentID)
	} else {
		url = fmt.Sprintf("%s/api/v2/agents/%s", c.BaseURL, agentID)
	}

	var agent Agent
	err := c.get(url, &agent)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to fetch agent %s: %w", agentID, err), http.StatusInternalServerError)
	}
	return &agent, nil
}

// GetAgents retrieves all agents.
func (c *Client) GetAgents(raw bool) (*[]Agent, error) {
	var url string
	if raw {
		url = fmt.Sprintf("%s/api/v2/agents/raw", c.BaseURL)
	} else {
		url = fmt.Sprintf("%s/api/v2/agents/", c.BaseURL)
	}
	var agents []Agent
	err := c.get(url, &agents)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to retrieve agents: %w", err), http.StatusInternalServerError)
	}
	return &agents, nil
}

// CreateThread creates a new Thread given a ThreadRequest object.
func (c *Client) CreateThread(req ThreadRequest) (*Thread, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/threads/", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to create thread: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to create thread: status code %d, body: %s", resp.StatusCode, string(body)), resp.StatusCode)
	}

	var thread Thread
	if err := json.Unmarshal(body, &thread); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}

	return &thread, nil
}

// DeleteThread deletes a thread given its ID.
func (c *Client) DeleteThread(id string) error {
	resp, err := c.delete(fmt.Sprintf("/api/v2/threads/%s", id))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to delete thread: %w", err), http.StatusInternalServerError)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		return NewAgentError(fmt.Errorf("failed to delete thread: status code %d", resp.StatusCode), resp.StatusCode)
	}

	return nil
}

// GetThread gets the details of a given thread ID.
func (c *Client) GetThread(threadID string) (*Thread, error) {
	url := fmt.Sprintf("%s/api/v2/threads/%s", c.BaseURL, threadID)
	var thread Thread

	err := c.get(url, &thread)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to get thread %s: %w", threadID, err), http.StatusInternalServerError)
	}

	return &thread, nil
}

// GetThreads returns all known threads.
func (c *Client) GetThreads() (*[]Thread, error) {
	url := fmt.Sprintf("%s/api/v2/threads/", c.BaseURL)
	var threads []Thread

	err := c.get(url, &threads)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to retrieve threads: %w", err), http.StatusInternalServerError)
	}

	return &threads, nil
}

// GetThreadState retrieves the state (history) of a given thread.
func (c *Client) GetThreadState(threadID string) (*ThreadState, error) {
	url := fmt.Sprintf("%s/api/v2/threads/%s/state", c.BaseURL, threadID)
	var state ThreadState

	err := c.get(url, &state)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to retrieve state for thread %s: %w", threadID, err), http.StatusInternalServerError)
	}

	return &state, nil
}

// Invoke sends a request to start a new run and returns the resulting ThreadState.
func (c *Client) Invoke(req StreamRequest) (*ThreadState, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/runs/invoke", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to invoke: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to invoke: body: %s", string(body)), resp.StatusCode)
	}

	var state ThreadState
	if err := json.Unmarshal(body, &state); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}

	return &state, nil
}

func (c *Client) InvokeAsyncV2(agentID string, payload CreateRunPayload) (*AsyncRunResponse, error) {
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal payload: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post(fmt.Sprintf("/api/v2/runs/%s/async", agentID), bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to invoke async: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return nil, NewAgentError(fmt.Errorf("failed to invoke async: status code %d, body: %s", resp.StatusCode, string(body)), resp.StatusCode)
	}

	var asyncResp AsyncRunResponse
	if err := json.Unmarshal(body, &asyncResp); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}

	return &asyncResp, nil
}

// InvokeAsync invokes the /async_invoke route to start an async run.
func (c *Client) InvokeAsync(payload CreateRunPayload) (*AsyncRunResponse, error) {
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal payload: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/runs/async_invoke", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to invoke async: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return nil, NewAgentError(fmt.Errorf("failed to invoke async: status code %d, body: %s", resp.StatusCode, string(body)), resp.StatusCode)
	}

	var asyncResp AsyncRunResponse
	if err := json.Unmarshal(body, &asyncResp); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}

	return &asyncResp, nil
}

// GetRunStatus fetches the status of a run by its ID.
func (c *Client) GetRunStatus(rid string) (*RunStatusResponse, error) {
	url := fmt.Sprintf("%s/api/v2/runs/%s/status", c.BaseURL, rid)

	var statusResp RunStatusResponse
	if err := c.get(url, &statusResp); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to fetch status for run %s: %w", rid, err), http.StatusInternalServerError)
	}

	return &statusResp, nil
}

// Stream initiates a stream of SSE events from a given thread.
// The listener function is invoked for each event received.
func (c *Client) Stream(req StreamRequest, listener func(message string)) error {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/runs/stream", bytes.NewBuffer(jsonData))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to initiate stream: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body) // Read the body even if there is an error to provide more context
		return NewAgentError(fmt.Errorf("failed to stream: status code %d, body: %s", resp.StatusCode, string(body)), resp.StatusCode)
	}

	// Process the response line by line
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "data: ") {
			// invoke the listener with the event data
			eventData := strings.TrimPrefix(line, "data: ")
			listener(eventData)
		}
	}

	if err := scanner.Err(); err != nil {
		return NewAgentError(fmt.Errorf("error reading response: %w", err), http.StatusInternalServerError)
	}

	return nil
}

// fetchFiles retrieves files associated with a specific agent.
func (c *Client) fetchFiles(agentID string) ([]AgentFile, error) {
	url := fmt.Sprintf("%s/api/v2/agents/%s/files", c.BaseURL, agentID)

	var files []AgentFile
	if err := c.get(url, &files); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to fetch files for agent %s: %w", agentID, err), http.StatusInternalServerError)
	}

	return files, nil
}

// GetAgentSemanticDataModels fetches semantic data models for an agent
// Server returns: [{sdm_id1: model1}, {sdm_id2: model2}, ...]
func (c *Client) GetAgentSemanticDataModels(agentID string) ([]SemanticDataModel, error) {
	url := fmt.Sprintf("%s/api/v2/agents/%s/semantic-data-models", c.BaseURL, agentID)

	// Server returns a list of maps, where each map has one key (the SDM ID) and the value is the model
	var rawSDMs []map[string]interface{}
	if err := c.get(url, &rawSDMs); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to fetch semantic data models for agent %s: %w", agentID, err), http.StatusInternalServerError)
	}

	// Convert to our struct format
	sdms := make([]SemanticDataModel, 0, len(rawSDMs))
	for _, rawSDM := range rawSDMs {
		// Each rawSDM is {id: model}
		for id, modelData := range rawSDM {
			// modelData should be a map[string]interface{} representing the semantic model
			var semanticModel map[string]interface{}
			if modelMap, ok := modelData.(map[string]interface{}); ok {
				semanticModel = modelMap
			} else {
				// If it's null or unexpected type, use empty map
				semanticModel = map[string]interface{}{}
			}
			
			sdms = append(sdms, SemanticDataModel{
				ID:            id,
				SemanticModel: semanticModel,
			})
			break // Each map should only have one entry
		}
	}

	return sdms, nil
}

// UploadFile uploads a file and associates it with a given agentID.
func (c *Client) UploadFile(agentID, filePath string) error {
	if agentID == "" || filePath == "" {
		return NewAgentError(fmt.Errorf("agentID and filePath must be non-empty"), http.StatusBadRequest)
	}

	file, err := os.Open(filePath)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to open file: %w", err), http.StatusInternalServerError)
	}
	defer file.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("files", filepath.Base(filePath))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to create form file: %w", err), http.StatusInternalServerError)
	}
	_, err = io.Copy(part, file)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to copy file content: %w", err), http.StatusInternalServerError)
	}

	config := map[string]interface{}{
		"configurable": map[string]string{
			"agent_id": agentID,
		},
	}
	configJSON, err := json.Marshal(config)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to marshal config: %w", err), http.StatusInternalServerError)
	}

	err = writer.WriteField("config", string(configJSON))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to write config field: %w", err), http.StatusInternalServerError)
	}

	err = writer.Close()
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to close multipart writer: %w", err), http.StatusInternalServerError)
	}

	req, err := http.NewRequest("POST", fmt.Sprintf("%s/api/v2/agents/%s/files", c.BaseURL, agentID), body)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to create request: %w", err), http.StatusInternalServerError)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to send request: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body) // Read the body even if there's an error to provide more context
		return NewAgentError(fmt.Errorf("failed to upload file: status code %d, body: %s", resp.StatusCode, string(bodyBytes)), resp.StatusCode)
	}

	return nil
}

// UpdateAgentRunbooks updates system and retrieval prompts for an agent given file paths.
func (c *Client) UpdateAgentRunbooks(agentID, systemPromptPath, retrievalPromptPath string) error {
	if agentID == "" || systemPromptPath == "" || retrievalPromptPath == "" {
		return NewAgentError(fmt.Errorf("agentID, systemPromptPath, and retrievalPromptPath must be non-empty"), http.StatusBadRequest)
	}

	systemPrompt, err := os.ReadFile(systemPromptPath)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to read system prompt file: %w", err), http.StatusInternalServerError)
	}

	retrievalPrompt, err := os.ReadFile(retrievalPromptPath)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to read retrieval prompt file: %w", err), http.StatusInternalServerError)
	}

	updateData := map[string]interface{}{
		"config": map[string]interface{}{
			"configurable": map[string]interface{}{
				"system_message":        string(systemPrompt),
				"retrieval_description": string(retrievalPrompt),
			},
		},
	}

	jsonData, err := json.Marshal(updateData)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to marshal update data: %w", err), http.StatusInternalServerError)
	}

	resp, err := c.put(fmt.Sprintf("/api/v2/agents/%s", agentID), bytes.NewBuffer(jsonData))
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to update agent runbooks: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body) // Read the body even if there's an error to provide more context
		return NewAgentError(fmt.Errorf("failed to update agent runbooks: status code %d, body: %s", resp.StatusCode, string(bodyBytes)), resp.StatusCode)
	}

	return nil
}

//**********************************
// Private Helper Methods for dealing with HTTP requests.
// TODO: Consider moving the following methods to an independent library, or using a third-party library.
//**********************************

func (c *Client) get(url string, v interface{}) error {
	resp, err := http.Get(url)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to fetch data: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return NewAgentError(fmt.Errorf("failed to fetch data: received status code %d", resp.StatusCode), resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to read response body: %w", err), resp.StatusCode)
	}

	err = json.Unmarshal(body, v)
	if err != nil {
		return NewAgentError(fmt.Errorf("failed to unmarshal response body: %w", err), http.StatusInternalServerError)
	}
	return nil
}

func (c *Client) post(path string, body io.Reader) (*http.Response, error) {
	return c.do("POST", path, body)
}

func (c *Client) put(path string, body io.Reader) (*http.Response, error) {
	return c.do("PUT", path, body)
}

func (c *Client) delete(path string) (*http.Response, error) {
	return c.do("DELETE", path, nil)
}

func (c *Client) do(method, path string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequest(method, c.BaseURL+path, body)
	if err != nil {
		return nil, err
	}
	// TODO: This may not be applicable for all requests. It should be configurable on a per-request basis.
	req.Header.Set("Content-Type", "application/json")
	return http.DefaultClient.Do(req)
}
