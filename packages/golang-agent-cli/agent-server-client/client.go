package agent_server_client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
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

// CreateAgentFromPackage creates a new agent from an agent package
func (c *Client) CreateAgentFromPackage(req AgentPackagePayload) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.post("/api/v2/agents/package", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to create agent from package: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to create agent from package: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
}

// UpdateAgentFromPackage updates an existing agent from an agent package
func (c *Client) UpdateAgentFromPackage(agentID string, req AgentPackagePayload) (*Agent, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to marshal request: %w", err), http.StatusBadRequest)
	}

	resp, err := c.put(fmt.Sprintf("/api/v2/agents/package/%s", agentID), bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to update agent from package: %w", err), http.StatusInternalServerError)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to read response: %w", err), resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, NewAgentError(fmt.Errorf("failed to update agent from package: %s", string(body)), resp.StatusCode)
	}

	var agent Agent
	if err := json.Unmarshal(body, &agent); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to decode response: %w", err), http.StatusInternalServerError)
	}
	return &agent, nil
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

func (c *Client) GetDataConnection(connectionID string) (*DataConnection, error) {
	url := fmt.Sprintf("%s/api/v2/data-connections/%s", c.BaseURL, connectionID)

	var dataConnection DataConnection
	if err := c.get(url, &dataConnection); err != nil {
		return nil, NewAgentError(fmt.Errorf("failed to fetch data connection %s: %w", connectionID, err), http.StatusInternalServerError)
	}

	return &dataConnection, nil
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
