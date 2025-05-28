package cmd

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"fmt"
	"io"

	"github.com/robocorp/rcc/pathlib"
	"github.com/spf13/cobra"

	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v2"
)

type ActionPackageInFilesystem struct {
	// The path of the action package relative to the actions directory
	RelativePath string
	// The path to the package.yaml file (can be empty if the action package is a zip file)
	PackageYAMLPath string
	// The path to the zip file if the action package is a zip file (i.e.: it's not extracted in the filesystem)
	ZipPath string
	// The contents of the package.yaml file
	PackageYAMLContents     string
	loadedYAML              map[string]interface{}
	loadedYAMLError         string
	ReferencedFromAgentSpec bool
}

// Note that it's can be actually inside a zip file when dealing with a zipped agent.
func NewActionPackageInFilesystem(relativePath, packageYAMLPath, zipPath string, packageYAMLContents string) *ActionPackageInFilesystem {
	ap := &ActionPackageInFilesystem{
		RelativePath:        relativePath,
		PackageYAMLPath:     packageYAMLPath,
		ZipPath:             zipPath,
		PackageYAMLContents: packageYAMLContents,
	}

	if ap.ZipPath == "" {
		if ap.PackageYAMLPath == "" {
			log("When the zip path is not provided, package_yaml_path is expected to be provided.")
		}
	} else {
		if ap.PackageYAMLPath != "" {
			log("When zip path is provided, package_yaml_path is not expected.")
		}
	}

	return ap
}

func (ap *ActionPackageInFilesystem) IsZip() bool {
	return ap.ZipPath != ""
}

func (ap *ActionPackageInFilesystem) GetAsDict() (map[string]interface{}, error) {
	if ap.loadedYAML != nil {
		return ap.loadedYAML, nil
	}

	if ap.loadedYAMLError != "" {
		return nil, fmt.Errorf(ap.loadedYAMLError)
	}

	var contents map[string]interface{}
	var err error

	if ap.PackageYAMLContents == "" {
		if ap.IsZip() {
			return nil, fmt.Errorf("it was not possible to load the package.yaml from %s", ap.ZipPath)
		} else {
			return nil, fmt.Errorf("it was not possible to load the package.yaml from %s", ap.PackageYAMLPath)
		}
	}

	err = yaml.Unmarshal([]byte(ap.PackageYAMLContents), &contents)

	if err != nil {
		if ap.IsZip() {
			log("Error getting package.yaml from %s as yaml.", ap.ZipPath)
		} else {
			log("Error getting %s as yaml.", ap.PackageYAMLPath)
		}
		ap.loadedYAMLError = err.Error()
		return nil, err
	}

	ap.loadedYAML = contents
	return ap.loadedYAML, nil
}

func (ap *ActionPackageInFilesystem) GetVersion() string {
	contents, err := ap.GetAsDict()
	if err != nil {
		return err.Error()
	}

	version, ok := contents["version"].(string)
	if !ok {
		return ""
	}
	return version
}

func (ap *ActionPackageInFilesystem) GetName() string {
	contents, err := ap.GetAsDict()
	if err != nil {
		return err.Error()
	}

	name, ok := contents["name"].(string)
	if !ok {
		return ""
	}
	return name
}

func ListActionPackagesFromAgent(agentRootDirOrZip string) map[string]*ActionPackageInFilesystem {
	found := make(map[string]*ActionPackageInFilesystem)

	if pathlib.IsDir(agentRootDirOrZip) {
		actionsDir := filepath.Join(agentRootDirOrZip, "actions")
		if !pathlib.IsDir(actionsDir) {
			// i.e.: the actions directory isn't really there, so, no action packages are present.
			return found
		}
		err := filepath.Walk(actionsDir, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if info.IsDir() {
				return nil
			}

			var packageYAMLContents string

			if strings.HasSuffix(path, "package.yaml") {
				relativePath, _ := filepath.Rel(actionsDir, filepath.Dir(path))
				// Now we have to convert the relative path to be posix
				relativePath = filepath.ToSlash(relativePath)

				bytesContents, error := os.ReadFile(path)
				if error != nil {
					packageYAMLContents = ""
				} else {
					packageYAMLContents = string(bytesContents)
				}

				found[path] = NewActionPackageInFilesystem(relativePath, path, "", packageYAMLContents)
			} else if strings.HasSuffix(path, ".zip") {
				packageYAMLContents, err := GetPackageYAMLFromZip(path)
				if err != nil {
					log("Error getting package.yaml from %s.", path)
					return err
				}
				relativePath, _ := filepath.Rel(actionsDir, path)
				// Now we have to convert the relative path to be posix
				relativePath = filepath.ToSlash(relativePath)
				found[path] = NewActionPackageInFilesystem(relativePath, "", path, packageYAMLContents)
			}

			return nil
		})

		if err != nil {
			log("Error walking through actions directory: %v", err)
		}
	} else {
		// Deal with zip files (mostly the same thing as the block above but accessing the zip contents).
		zipReader, err := zip.OpenReader(agentRootDirOrZip)
		if err != nil {
			log("Error opening agent zip file: %v", err)
			return found
		}
		defer zipReader.Close()

		for _, file := range zipReader.File {
			if strings.HasPrefix(file.Name, "actions/") && (strings.HasSuffix(file.Name, "package.yaml") || strings.HasSuffix(file.Name, ".zip")) {
				relativePath := strings.TrimPrefix(file.Name, "actions/")
				relativePath = filepath.ToSlash(relativePath)

				var packageYAMLContents string
				var innerZipPath string

				packageYAMLPath := ""
				if strings.HasSuffix(file.Name, "package.yaml") {
					packageYAMLContents = GetFileContentsFromZip(file)
					packageYAMLPath = file.Name
					innerZipPath = ""
				} else { // .zip file
					innerZipPath = file.Name
					packageYAMLContents = GetPackageYAMLFromInnerZip(file)
				}

				if packageYAMLContents != "" {
					found[file.Name] = NewActionPackageInFilesystem(
						relativePath,
						packageYAMLPath,
						innerZipPath,
						packageYAMLContents,
					)
				}
			}
		}

	}

	return found
}

func GetFileContentsFromZip(file *zip.File) string {
	fileReader, err := file.Open()
	if err != nil {
		log("Error opening file in zip: %v", err)
		return ""
	}
	defer fileReader.Close()

	content, err := io.ReadAll(fileReader)
	if err != nil {
		log("Error reading file in zip: %v", err)
		return ""
	}

	return string(content)
}

/**
 * We're dealing with a zip file inside another zip file
 * (this means that we're dealing with an agent that is zipped
 * and the action package inside it is zipped too and we want the
 * package.yaml from the inner zip file).
 */
func GetPackageYAMLFromInnerZip(file *zip.File) string {
	innerZipReader, err := file.Open()
	if err != nil {
		log("Error opening inner zip file: %v", err)
		return ""
	}
	defer innerZipReader.Close()

	innerZipBytes, err := io.ReadAll(innerZipReader)
	if err != nil {
		log("Error reading inner zip file: %v", err)
		return ""
	}

	innerZip, err := zip.NewReader(bytes.NewReader(innerZipBytes), int64(len(innerZipBytes)))
	if err != nil {
		log("Error creating reader for inner zip: %v", err)
		return ""
	}

	innerZipFile, err := innerZip.Open("package.yaml")
	if err != nil {
		log("Error opening package.yaml in inner zip: %v", err)
		return ""
	}
	defer innerZipFile.Close()

	content, err := io.ReadAll(innerZipFile)
	if err != nil {
		log("Error reading package.yaml in inner zip: %v", err)
		return ""
	}

	return string(content)
}

func GetFileFromZip(zipPath string, fileName string) (string, error) {
	zipReader, err := zip.OpenReader(zipPath)
	if err != nil {
		return "", fmt.Errorf("error opening zip file: %w", err)
	}
	defer zipReader.Close()

	fileHandle, err := zipReader.Open(fileName)
	if err != nil {
		return "", fmt.Errorf("error opening file %s in zip: %w", fileName, err)
	}
	defer fileHandle.Close()

	content, err := io.ReadAll(fileHandle)
	if err != nil {
		return "", fmt.Errorf("error reading file %s in zip: %w", fileName, err)
	}

	return string(content), nil
}

func GetPackageYAMLFromZip(zipPath string) (string, error) {
	return GetFileFromZip(zipPath, "package.yaml")
}

var listActionPackagesFromAgentCmd = &cobra.Command{
	Use:   "list-action-packages",
	Short: "List action packages from agent.",
	Long:  `List action packages from agent and print them to stdout.`,
	Run:   runListActionPackagesFromAgentCmd,
}

func runListActionPackagesFromAgentCmd(cmd *cobra.Command, args []string) {
	// At least one argument is required, the agent root directory
	if len(args) < 1 {
		log("Error: agent root directory is required.")
		os.Exit(1)
	}
	agentRootDir := args[0]
	actions := ListActionPackagesFromAgent(agentRootDir)
	for _, action := range actions {
		// Instead of printing the name, print a json with the name, version and path
		actionJson, err := json.Marshal(map[string]string{
			"name":    action.GetName(),
			"version": action.GetVersion(),
			"path":    action.RelativePath,
		})
		if err != nil {
			log("Error marshalling action: %v", err)
			os.Exit(1)
		}
		fmt.Println(string(actionJson))
	}
}

func init() {
	rootCmd.AddCommand(listActionPackagesFromAgentCmd)
}
