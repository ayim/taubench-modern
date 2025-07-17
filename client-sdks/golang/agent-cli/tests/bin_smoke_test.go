package tests

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

var binaryPath string

func init() {
	flag.StringVar(&binaryPath, "binary", "", "path to agent-cli binary")
}

// getBinaryPath returns the binary path from flag or default build location
func getBinaryPath() (string, error) {
	// If binary path not provided, use default build location
	binPath := binaryPath
	if binPath == "" {
		buildDir := filepath.Join("../dist")
		if runtime.GOOS == "windows" {
			binPath = filepath.Join(buildDir, "agent-cli.exe")
		} else {
			binPath = filepath.Join(buildDir, "agent-cli")
		}
	}

	// Convert to absolute path for clarity in logs
	absPath, err := filepath.Abs(binPath)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path: %v", err)
	}

	// Verify binary exists
	if _, err := os.Stat(absPath); os.IsNotExist(err) {
		return "", fmt.Errorf("binary not found at %s", absPath)
	}

	return absPath, nil
}

func TestMain(m *testing.M) {
	flag.Parse() // Parse the binary flag
	os.Exit(m.Run())
}

// runCommand is a helper function to run the binary with arguments
func runCommand(t *testing.T, args ...string) (string, error) {
	t.Helper()

	binPath, err := getBinaryPath()
	if err != nil {
		t.Fatal(err)
	}

	cmd := exec.Command(binPath, args...)
	t.Logf("Running: %s %s", filepath.Base(cmd.Path), strings.Join(args, " "))

	output, err := cmd.CombinedOutput()
	return string(output), err
}

func TestVersion(t *testing.T) {
	output, err := runCommand(t, "--version")
	if err != nil {
		t.Fatalf("version command failed: %v\nOutput: %s", err, output)
	}
	// Add version string validation if needed
	t.Logf("Version output: %s", output)
}
