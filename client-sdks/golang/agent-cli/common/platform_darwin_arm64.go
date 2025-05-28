//go:build arm64 && darwin
// +build arm64,darwin

package common

import (
	"os"
	"path/filepath"
)

const (
	defaultHomeLocation = "$HOME/.sema4ai"
)

func ExpandPath(entry string) string {
	intermediate := os.ExpandEnv(entry)
	result, err := filepath.Abs(intermediate)
	if err != nil {
		return intermediate
	}
	return result
}
