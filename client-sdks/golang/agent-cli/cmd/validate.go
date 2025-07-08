package cmd

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"

	"github.com/spf13/cobra"
	"gopkg.in/yaml.v3"
)

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate agent.",
	Long:  `Validate agent.`,
	Run:   runValidateCmd,
}

var (
	showSpecFlag      bool
	nestedFlag        bool
	jsonSpecFlag      bool
	ignoreActionsFlag bool
)

// (use 0-based coordinates -- remember that yaml.Node.Line/Column is 1-based)
func reportErrorAndExit(message string, startLine int, startColumn int, endLine int, endColumn int) {
	if jsonSpecFlag {
		error := NewError(message, startLine, startColumn, endLine, endColumn, Critical)
		// Convert error to diagnostic
		diagnostic := error.AsDiagnostic(nil)

		diagnostics := []map[string]interface{}{diagnostic}
		// Convert diagnostics to json
		json, err := json.MarshalIndent(diagnostics, "", "  ")
		if err != nil {
			log("Error: %s", err)
			os.Exit(1)
		}
		// Print the diagnostics to stdout (as json: coordinates are 0-indexed).
		fmt.Println(string(json))
		os.Exit(1)
	} else {
		// Print the error to stdout (1-indexed)
		fmt.Printf("Error at line: %d: %s\n", startLine+1, message)
		os.Exit(1)
	}
}

func findNode(rootNode yaml.Node, key string) *yaml.Node {
	for i := 0; i < len(rootNode.Content)-1; i += 2 {
		keyNode := rootNode.Content[i]
		valueNode := rootNode.Content[i+1]
		if keyNode.Value == key {
			return valueNode
		}
	}
	return nil
}

func runValidateCmd(cmd *cobra.Command, args []string) {
	// We'll load the spec after determining the version from the YAML file
	var specEntries map[string]*Entry
	var err error

	if showSpecFlag {
		// For show-spec, we'll use SpecV3 as default
		var spec map[string]interface{}
		err = json.Unmarshal([]byte(SpecV3), &spec)
		if err != nil {
			log("Error: %s", err)
			os.Exit(1)
		}
		// Get the entries from the spec
		specEntries, err = LoadSpec(spec)
		if err != nil {
			log("Error: %s", err)
			os.Exit(1)
		}

		// Convert Spec to a map[string]*Entry
		if nestedFlag {
			tree := ConvertFlattenedToNested(specEntries)
			fmt.Println(Pretty(tree, 0))
		} else {
			// Now print the specEntries in a json format
			json, err := json.MarshalIndent(specEntries, "", "  ")
			if err != nil {
				log("Error: %s", err)
				os.Exit(1)
			}
			fmt.Println(string(json))
		}

		os.Exit(0)
	}
	// At least one argument is required, the agent root directory
	if len(args) < 1 {
		log("Error: agent root directory is required.")
		os.Exit(1)
	}

	var yamlFile []byte

	agentRootDirOrZip := args[0]
	if filepath.Ext(agentRootDirOrZip) == ".zip" {
		// Get the `agent-spec.yaml` from the zip
		zipReader, err := zip.OpenReader(agentRootDirOrZip)
		if err != nil {
			reportErrorAndExit(fmt.Sprintf("Error opening zip file: %s", err), 0, 0, 1, 0)
		}
		defer zipReader.Close()

		agentSpecFile, err := zipReader.Open("agent-spec.yaml")
		if err != nil {
			reportErrorAndExit(fmt.Sprintf("Error opening agent-spec.yaml in zip: %s", err), 0, 0, 1, 0)
		}
		defer agentSpecFile.Close()

		// Read the contents of the file
		yamlFile, err = io.ReadAll(agentSpecFile)
		if err != nil {
			reportErrorAndExit(fmt.Sprintf("Error reading agent-spec.yaml: %s", err), 0, 0, 1, 0)
		}

	} else {
		// Load the agent-spec.yaml file as yaml node
		yamlFile, err = os.ReadFile(filepath.Join(agentRootDirOrZip, "agent-spec.yaml"))
		if err != nil {
			reportErrorAndExit(fmt.Sprintf("Error reading YAML file: %s", err), 0, 0, 1, 0)
		}
	}

	var rootNode yaml.Node
	err = yaml.Unmarshal(yamlFile, &rootNode)
	if err != nil {
		reportErrorAndExit(fmt.Sprintf("Error unmarshalling YAML: %s", err), 0, 0, 1, 0)
	}

	if len(rootNode.Content) == 0 {
		reportErrorAndExit("Error: no root node found.", 0, 0, 1, 0)
	}

	// Find "agent-package"
	agentPackageNode := findNode(*rootNode.Content[0], "agent-package")

	if agentPackageNode == nil {
		reportErrorAndExit("Error: 'agent-package' is required.", 0, 0, 1, 0)
	}

	// Ensure "agent-package" is a map
	if agentPackageNode.Kind != yaml.MappingNode {
		reportErrorAndExit("Error: 'agent-package' should be a map.", agentPackageNode.Line-1, agentPackageNode.Column-1, agentPackageNode.Line, 0)
	}

	// Find "spec-version" in the agent-package
	specVersionNode := findNode(*agentPackageNode, "spec-version")

	if specVersionNode == nil {
		reportErrorAndExit("Error: 'spec-version' is required in 'agent-package'.", agentPackageNode.Line-1, agentPackageNode.Column-1, agentPackageNode.Line, 0)
	}

	// Ensure "spec-version" is a scalar string
	if specVersionNode.Kind != yaml.ScalarNode || specVersionNode.Tag != "!!str" {
		reportErrorAndExit("Error: 'spec-version' should be a string.", specVersionNode.Line-1, specVersionNode.Column-1, specVersionNode.Line, 0)
	}

	// Check that the specVersion is "v2" or "v3"
	if specVersionNode.Value != "v2" && specVersionNode.Value != "v3" {
		reportErrorAndExit(fmt.Sprintf("Error: 'spec-version' must be 'v2' or 'v3'. Found: %s", specVersionNode.Value), specVersionNode.Line-1, specVersionNode.Column-1, specVersionNode.Line, 0)
	}

	// Load the appropriate spec based on the version
	var spec map[string]interface{}
	if specVersionNode.Value == "v2" {
		err = json.Unmarshal([]byte(SpecV2), &spec)
	} else {
		err = json.Unmarshal([]byte(SpecV3), &spec)
	}
	if err != nil {
		log("Error: %s", err)
		os.Exit(1)
	}
	// Get the entries from the spec
	specEntries, err = LoadSpec(spec)
	if err != nil {
		log("Error: %s", err)
		os.Exit(1)
	}

	validator := NewValidator(specEntries, agentRootDirOrZip)
	errors := make(chan Error)
	go validator.Validate(&rootNode, errors, ignoreActionsFlag)

	diagnostics := []map[string]interface{}{}
	for error := range errors {
		diagnostics = append(diagnostics, error.AsDiagnostic(nil))
	}
	if len(diagnostics) == 0 {
		if jsonSpecFlag {
			fmt.Println("[]")
		} else {
			fmt.Println("No errors!")
		}
		os.Exit(0)
	}

	// If we have more than one diagnostic, sort them by line number (so that tests are deterministic)
	if len(diagnostics) > 1 {
		sort.Slice(diagnostics, func(i, j int) bool {
			return diagnostics[i]["range"].(map[string]map[string]int)["start"]["line"] < diagnostics[j]["range"].(map[string]map[string]int)["start"]["line"]
		})
	}

	if jsonSpecFlag {
		json, err := json.MarshalIndent(diagnostics, "", "  ")
		if err != nil {
			log("Error: %s", err)
		}
		fmt.Println(string(json))
	} else {
		for _, diagnostic := range diagnostics {
			useRange := diagnostic["range"].(map[string]map[string]int)
			if useRange == nil {
				panic("range not in diagnostic (or type-cast is wrong)")
			}
			line := useRange["start"]["line"]
			fmt.Printf("Error at line: %d: %s\n", line, diagnostic["message"].(string))
		}
	}

	os.Exit(1)
}

func init() {
	rootCmd.AddCommand(validateCmd)
	validateCmd.Flags().BoolVarP(&jsonSpecFlag, "json", "j", false, "Output as Json.")
	validateCmd.Flags().BoolVar(&ignoreActionsFlag, "ignore-actions", false, "Ignore actions in the validation.")

	validateCmd.Flags().BoolVarP(&showSpecFlag, "show-spec", "s", false, "Show the spec and exit.")
	validateCmd.Flags().BoolVarP(&nestedFlag, "nested", "n", false, "Show the spec in nested format (only valid with --show-spec).")
}
