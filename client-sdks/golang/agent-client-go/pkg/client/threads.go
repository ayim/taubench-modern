package client

import (
	"fmt"
	"time"

	"github.com/google/uuid"
)

// ThreadMetadata represents the metadata for a thread.
// Currently, it only defines `agent_type`.
type ThreadMetadata struct {
	AgentType string `json:"agent_type"`
}

// Thread represents a saved thread.
// The ThreadID value can be used to create a new stream.
type Thread struct {
	ThreadID  string               `json:"thread_id"`
	UserID    string               `json:"user_id"`
	AgentID   string               `json:"agent_id"`
	Name      string               `json:"name"`
	UpdatedAt time.Time            `json:"updated_at"`
	CreatedAt time.Time            `json:"created_at"`
	Metadata  ThreadMetadata       `json:"metadata"`
	Messages  []ThreadStateMessage `json:"messages"`
}

// ThreadRequest represent an API request to create a new thread.
// All Thread objects are associated with an Agent via AgentID.
type ThreadRequest struct {
	AgentID         string `json:"agent_id"`
	Name            string `json:"name"`
	StartingMessage string `json:"starting_message"`
}

// ChatMessage represents a message in a Thread interaction.
type ChatMessage struct {
	// Content is the body of the message.
	Content string `json:"content"`
	// Type represents the role of the message, such as "human", "ai", "system", or "tool".
	Type string `json:"type"`

	// TODO: What does "example" actually mean at runtime?
	// Example is true if this is an example message.
	Example bool `json:"example"`

	// ID is a unique identifier for the message.
	// This is typically a random UUID.
	ID string `json:"id"`
}

func NewChatMessage(role string, content string) ChatMessage {
	// create a uuid for the message
	uuidString := uuid.New().String()
	id := fmt.Sprintf("%s-%s", role, uuidString)

	return ChatMessage{
		Content: content,
		Type:    role,
		Example: false,
		ID:      id,
	}
}

type ThreadState struct {
	Values ThreadStateValues `json:"values"`
	Next   []any             `json:"next"`
}

type ToolCall struct {
	Name string         `json:"name"`
	Args map[string]any `json:"args"`
	ID   string         `json:"id"`
}

type ThreadStateMessage struct {
	Content          string         `json:"content"`
	AdditionalKwargs map[string]any `json:"additional_kwargs"`
	ResponseMetadata map[string]any `json:"response_metadata"`
	Type             string         `json:"type"`
	Name             string         `json:"name"`
	ID               string         `json:"id"`
	Example          bool           `json:"example"`
	ToolCalls        []ToolCall     `json:"tool_calls"`
	InvalidToolCalls []ToolCall     `json:"invalid_tool_calls"`
	ToolCallID       string         `json:"tool_call_id,omitempty"`
}

type ThreadStateValues struct {
	Messages  []ThreadStateMessage `json:"messages"`
	Reasoning []ThreadStateMessage `json:"reasoning"`
	Combined  []ThreadStateMessage `json:"combined"`
}

// StreamRequest represents a request to stream a chat response from a given thread.
type StreamRequest struct {
	// ThreadID is the id of the thread to interact with.
	ThreadID string        `json:"thread_id"`
	Input    []ChatMessage `json:"input"`
}

// AsyncRunResponse represents the response for the /async_invoke route.
type AsyncRunResponse struct {
	RunID  string `json:"run_id"`
	Status string `json:"status"`
}

// CreateRunPayload represents the payload sent to the /async_invoke route.
type CreateRunPayload struct {
	ThreadID string        `json:"thread_id"`
	Input    []ChatMessage `json:"input"`
	AgentID  string        `json:"agent_id"`
}

// RunStatusResponse represents the response for the /{rid}/status route.
type RunStatusResponse struct {
	RunID  string `json:"run_id"`
	Status string `json:"status"`
}
