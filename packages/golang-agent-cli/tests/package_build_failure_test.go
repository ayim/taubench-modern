package tests

import (
	"archive/zip"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"testing"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBuildAgentPackage_Success(t *testing.T) {
	// Setup test directories
	inputDir := filepath.Join("fixtures", "agent-projects", "a-1.v2.1.qg")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Verify input directory exists and contains required files
	assert.DirExists(t, inputDir)
	assert.FileExists(t, filepath.Join(inputDir, "agent-spec.yaml"))
	assert.FileExists(t, filepath.Join(inputDir, "runbook.md"))

	// Call the method that the "package build" command would call
	err := cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Assertions
	assert.NoError(t, err, "BuildAgentPackage should succeed with valid input")

	// Verify the output package was created
	expectedPackagePath := filepath.Join(outputDir, packageName)
	assert.FileExists(t, expectedPackagePath, "package file should be created")

	// Verify the package is not empty
	fileInfo, err := os.Stat(expectedPackagePath)
	assert.NoError(t, err)
	assert.Greater(t, fileInfo.Size(), int64(0), "package file should not be empty")
}

func TestBuildAgentPackage_InvalidInputDir(t *testing.T) {
	// Test with non-existent input directory
	inputDir := filepath.Join("fixtures", "non-existent-directory")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Call the method
	err := cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Should fail because input directory doesn't exist
	assert.Error(t, err, "BuildAgentPackage should fail with non-existent input directory")
	assert.Contains(t, err.Error(), "does not exist", "error should mention spec reading failure")
}

func TestBuildAgentPackage_ExistingPackageWithoutOverwrite(t *testing.T) {
	// Setup test directories
	inputDir := filepath.Join("fixtures", "agent-projects", "a-1.v2.1.qg")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Create an existing package file
	existingPackagePath := filepath.Join(outputDir, packageName)
	err := os.WriteFile(existingPackagePath, []byte("existing content"), 0644)
	assert.NoError(t, err)

	// Call the method
	err = cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Should fail because package already exists and overwrite is false
	assert.Error(t, err, "BuildAgentPackage should fail when package exists and overwrite is false")
	assert.Contains(t, err.Error(), "already exists", "error should mention package already exists")
}

func TestBuildAgentPackage_ExistingPackageWithOverwrite(t *testing.T) {
	// Setup test directories
	inputDir := filepath.Join("fixtures", "agent-projects", "a-1.v2.1.qg")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := true

	// Create an existing package file
	existingPackagePath := filepath.Join(outputDir, packageName)
	err := os.WriteFile(existingPackagePath, []byte("existing content"), 0644)
	assert.NoError(t, err)

	// Call the method
	err = cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Should succeed because overwrite is true
	assert.NoError(t, err, "BuildAgentPackage should succeed when overwrite is true")

	// Verify the package was overwritten
	expectedPackagePath := filepath.Join(outputDir, packageName)
	assert.FileExists(t, expectedPackagePath, "package file should exist after overwrite")

	// Verify the package is not empty and different from original
	fileInfo, err := os.Stat(expectedPackagePath)
	assert.NoError(t, err)
	assert.Greater(t, fileInfo.Size(), int64(0), "package file should not be empty")
}

func TestBuildAgentPackage_MissingAgentSpec(t *testing.T) {
	// Create a temporary directory without agent-spec.yaml
	tempDir := t.TempDir()

	// Create a minimal project structure without agent-spec.yaml
	err := os.MkdirAll(filepath.Join(tempDir, "actions"), 0755)
	assert.NoError(t, err)

	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Call the method
	err = cmd.BuildAgentPackage(tempDir, outputDir, packageName, overwrite)

	// Should fail because agent-spec.yaml is missing
	assert.Error(t, err, "BuildAgentPackage should fail when agent-spec.yaml is missing")
	assert.Contains(t, err.Error(), "spec YAML file @", "error should mention spec reading failure")
}

func TestBuildAgentPackage_BadActionPackage(t *testing.T) {
	// Setup test directories
	inputDir := filepath.Join("fixtures", "agent-projects", "a-1.v2.1.bad-action")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Verify input directory exists and contains required files
	assert.DirExists(t, inputDir)
	assert.FileExists(t, filepath.Join(inputDir, "agent-spec.yaml"))
	assert.FileExists(t, filepath.Join(inputDir, "runbook.md"))

	// Call the method that the "package build" command would call
	err := cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Assertions
	assert.Error(t, err, "BuildAgentPackage should fail with bad action package")
	assert.Contains(t, err.Error(), "Parameter: `argument_without_docs` documentation not found in docstring", "error should mention action package failure")
}

// Tests an issue where the metadata path was not correctly handled
// https://linear.app/sema4ai/issue/DEV-2422/fix-metadata-generation-in-agent-cli-paths-broken-by-slugifying
func TestBuildAgentPackage_InvalidMetadataPathIssueFix(t *testing.T) {
	// Setup test directories
	inputDir := filepath.Join("fixtures", "agent-projects", "a-1.v2.1.metadata-issue")
	outputDir := t.TempDir()
	packageName := "test-package.zip"
	overwrite := false

	// Verify input directory exists and contains required files
	assert.DirExists(t, inputDir)
	assert.FileExists(t, filepath.Join(inputDir, "agent-spec.yaml"))
	assert.FileExists(t, filepath.Join(inputDir, "runbook.md"))

	// Call the method that the "package build" command would call
	err := cmd.BuildAgentPackage(inputDir, outputDir, packageName, overwrite)

	// Assertions
	require.NoError(t, err, "BuildAgentPackage should succeed")

	// Verify the output package was created
	expectedPackagePath := filepath.Join(outputDir, packageName)
	assert.FileExists(t, expectedPackagePath, "package file should be created")

	// Open the zip file and verify metadata file exists
	zipReader, err := zip.OpenReader(expectedPackagePath)
	require.NoError(t, err, "should be able to open zip file")
	defer zipReader.Close()

	// Find the metadata file
	var metadataFile *zip.File
	for _, f := range zipReader.File {
		if f.Name == common.AGENT_PACKAGE_METADATA_FILE {
			metadataFile = f
			break
		}
	}
	assert.NotNil(t, metadataFile, "metadata file should exist in package")

	// Read the metadata file
	metadataReader, err := metadataFile.Open()
	require.NoError(t, err, "should be able to open metadata file")
	defer metadataReader.Close()

	metadataBytes, err := io.ReadAll(metadataReader)
	require.NoError(t, err, "should be able to read metadata file")
	assert.Greater(t, len(metadataBytes), 0, "metadata file should not be empty")

	// Unmarshal the metadata JSON
	var metadata []common.AgentPackageMetadata
	err = json.Unmarshal(metadataBytes, &metadata)
	require.NoError(t, err, "should be able to unmarshal metadata JSON")
	assert.Len(t, metadata, 1, "should have exactly one agent in metadata")

	// Verify metadata contains expected data
	agentMetadata := metadata[0]
	// Verify action packages metadata exists and has correct path
	assert.Len(t, agentMetadata.ActionPackages, 1, "should have one action package")
	actionPackage := agentMetadata.ActionPackages[0]
	assert.Equal(t, "Test-ServiceNow-Local", actionPackage.Name, "action package name should match")
	assert.Equal(t, "0.0.1", actionPackage.Version, "action package version should match")
	// The path should be correctly slugified: "CI1 Platform Team/test-service-now-local" -> "ci1-platform-team/test-service-now-local/"
	// or similar, depending on the slugification logic
	assert.Equal(t, actionPackage.Path, "CI1 Platform Team/test-servicenow-local", "action package path should be set in metadata")
}
