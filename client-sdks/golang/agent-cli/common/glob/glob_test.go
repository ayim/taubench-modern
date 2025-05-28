package glob

import (
	"fmt"
	"github.com/stretchr/testify/assert"
	"strings"
	"testing"
)

func TestExclude(t *testing.T) {

	patterns := []string{"./go-glob", "./.idea/**", "./.git/**", "./.vscode/**", "./devdata/**", "./output/**", "./venv/**", "./.venv/**", "./**/.DS_Store/**", "./**/*.pyc", "./**/*.zip"}
	rootDir := "test-data"

	files, err := Exclude(rootDir, patterns)
	assert.NoError(t, err)
	assert.Equal(t, 5, len(files))

	fileKeys := ""

	for key, _ := range files {
		fileKeys += key
	}

	hasBar := strings.Contains(fileKeys, "test-data/go-files/bar.go")
	hasFoo := strings.Contains(fileKeys, "test-data/go-files/foo.go")
	hasPy := strings.Contains(fileKeys, "test-data/my_action.py")

	hasZip := strings.Contains(fileKeys, "test-data/zip-files/bar.zip")

	assert.True(t, hasBar)
	assert.True(t, hasFoo)
	assert.True(t, hasPy)

	assert.False(t, hasZip)

	fmt.Print()
}
