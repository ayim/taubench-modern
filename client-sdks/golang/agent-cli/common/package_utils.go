package common

import (
	"os"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
	"gopkg.in/yaml.v2"
)

// ReadConversationGuideYAML parses a conversation-guide.yaml file with a 'question-groups' root key.
func ReadConversationGuideYAML(path string) (AgentServer.QuestionGroups, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var guide AgentPackageConversationGuideContents
	if err := yaml.Unmarshal(content, &guide); err != nil {
		return nil, err
	}
	return guide.QuestionGroups, nil
}
