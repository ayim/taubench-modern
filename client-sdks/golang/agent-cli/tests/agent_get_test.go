package tests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
)

func TestReadConversationGuideYAML_Success(t *testing.T) {
	tmpDir := t.TempDir()
	yamlPath := filepath.Join(tmpDir, "conversation-guide.yaml")

	yamlContent := `
question-groups:
  - title: "Group 1"
    questions:
      - "What is your name?"
      - "How old are you?"
`
	err := os.WriteFile(yamlPath, []byte(yamlContent), 0644)
	assert.NoError(t, err)

	result, err := common.ReadConversationGuideYAML(yamlPath)
	assert.NoError(t, err)
	assert.Len(t, result, 1)
	assert.Equal(t, "Group 1", result[0].Title)
	assert.Equal(t, []string{"What is your name?", "How old are you?"}, result[0].Questions)
}

func TestReadConversationGuideYAML_FileNotFound(t *testing.T) {
	_, err := common.ReadConversationGuideYAML("nonexistent.yaml")
	assert.Error(t, err)
}

func TestReadConversationGuideYAML_InvalidYAML(t *testing.T) {
	tmpDir := t.TempDir()
	yamlPath := filepath.Join(tmpDir, "invalid.yaml")

	err := os.WriteFile(yamlPath, []byte("not: [valid"), 0644)
	assert.NoError(t, err)

	_, err = common.ReadConversationGuideYAML(yamlPath)
	assert.Error(t, err)
}
