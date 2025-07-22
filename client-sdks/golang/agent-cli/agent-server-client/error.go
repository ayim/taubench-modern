package agent_server_client

import (
	"fmt"
)

type AgentError struct {
	ErrorMsg   error
	StatusCode int
}

func (e *AgentError) Error() string {
	return fmt.Sprintf("error: %s, status Code: %d", e.ErrorMsg.Error(), e.StatusCode)
}

func (e *AgentError) GetStatusCode() int {
	return e.StatusCode
}

func NewAgentError(errorMsg error, statusCode int) error {
	return &AgentError{
		ErrorMsg:   errorMsg,
		StatusCode: statusCode,
	}
}
