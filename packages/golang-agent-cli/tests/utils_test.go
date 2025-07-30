package tests

import (
	"testing"

	"github.com/stretchr/testify/assert"

	common "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
)

func TestSlugifyUnicodedValue(t *testing.T) {
	result := common.Slugify("ação")
	assert.Equal(t, "acao", result)
}

func TestSlugifyDash(t *testing.T) {
	result := common.Slugify("my package")
	assert.Equal(t, "my-package", result)

	result = common.Slugify("my-package")
	assert.Equal(t, "my-package", result)

	result = common.Slugify("my_package")
	assert.Equal(t, "my_package", result)
}
