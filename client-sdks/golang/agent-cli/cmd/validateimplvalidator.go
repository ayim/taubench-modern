package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"github.com/Sema4AI/rcc/pathlib"
	"gopkg.in/yaml.v3"
)

const (
	nullTag      = "!!null"
	boolTag      = "!!bool"
	strTag       = "!!str"
	intTag       = "!!int"
	floatTag     = "!!float"
	timestampTag = "!!timestamp"
	seqTag       = "!!seq"
	mapTag       = "!!map"
	binaryTag    = "!!binary"
	mergeTag     = "!!merge"
)

type Validator struct {
	specEntries             map[string]*Entry
	stack                   []string
	currentStackAsStr       string
	agentRootDirOrZip       string
	yamlInfoLoaded          *YamlTreeNode
	yamlCursorNode          *YamlTreeNode
	actionPackagesFoundInFS map[string]*ActionPackageInFilesystem
	IsZipValidation         bool
}

func NewValidator(specEntries map[string]*Entry, agentRootDirOrZip string) *Validator {
	// Initialize the YAML tree with a root node.
	yamlRootNode := NewYamlTreeNode("root", nil)

	var isZipValidation bool
	if pathlib.IsDir(agentRootDirOrZip) {
		isZipValidation = false
	} else {
		isZipValidation = true
	}

	return &Validator{
		specEntries:             specEntries,
		stack:                   []string{},
		currentStackAsStr:       "",
		agentRootDirOrZip:       agentRootDirOrZip,
		yamlInfoLoaded:          yamlRootNode,
		yamlCursorNode:          yamlRootNode,
		actionPackagesFoundInFS: make(map[string]*ActionPackageInFilesystem),
		IsZipValidation:         isZipValidation,
	}
}

func (v *Validator) validateKeyPair(keyNode *yaml.Node, errors chan Error) {
	entry := v.specEntries[v.currentStackAsStr]
	if entry == nil {
		parentAsStr := "<unknown>"
		curr := "<unknown>"

		if len(v.stack) > 0 {
			parent := v.stack[:len(v.stack)-1]
			curr = v.stack[len(v.stack)-1]

			if len(parent) > 0 {
				parentAsStr = strings.Join(parent, "/")
			} else {
				parentAsStr = "root"
			}

		} else {
			parentAsStr = "root"
		}

		errors <- *NewError(fmt.Sprintf("Unexpected entry: %s (in %s).", curr, parentAsStr),
			keyNode.Line-1, keyNode.Column-1, keyNode.Line, 0, Critical)
	}
}

func (v *Validator) ValidateNodesExistAndBuildYamlInfo(node *yaml.Node, errors chan Error) {
	// fmt.Printf("Node: line: %d, column: %d, kind: %v, tag: %v, value: %v\n", node.Line, node.Column, node.Kind, node.Tag, node.Value)

	// defaultVisitChildren := true
	if node.Kind == yaml.DocumentNode {
		node = node.Content[0]
		// print node info (line and column)
		v.ValidateNodesExistAndBuildYamlInfo(node, errors)

	} else if node.Kind == yaml.ScalarNode {
		if node.Tag == strTag {
			v.yamlCursorNode.data = &YamlNodeData{
				Node: node,
				Kind: YamlNodeKindString,
			}
		} else if node.Tag == boolTag {
			v.yamlCursorNode.data = &YamlNodeData{
				Node: node,
				Kind: YamlNodeKindBool,
			}
		} else if node.Tag == intTag {
			v.yamlCursorNode.data = &YamlNodeData{
				Node: node,
				Kind: YamlNodeKindInt,
			}
		} else if node.Tag == floatTag {
			v.yamlCursorNode.data = &YamlNodeData{
				Node: node,
				Kind: YamlNodeKindFloat,
			}
		} else {
			// Print the current node tag
			// fmt.Printf("Unhandled node tag: %v\n", node.Tag)
		}

	} else if node.Kind == yaml.SequenceNode {
		v.yamlCursorNode.data.Kind = YamlNodeKindList

		for i := 0; i < len(node.Content); i += 1 {
			useKeyName := fmt.Sprintf("list-item-%d", len(v.yamlCursorNode.children))
			v.yamlCursorNode = v.yamlCursorNode.Obtain(useKeyName)

			currNode := node.Content[i]
			v.yamlCursorNode.data = &YamlNodeData{
				Kind: YamlNodeKindListItem,
				Node: currNode,
			}

			v.ValidateNodesExistAndBuildYamlInfo(currNode, errors)

			// Undo the cursor
			v.yamlCursorNode = v.yamlCursorNode.parent
			// fmt.Printf("Found list item: kind: %v - tag: %v - value: %v\n", node.Content[i].Kind, node.Content[i].Tag, node.Content[i].Value)
		}

	} else if node.Kind == yaml.MappingNode {
		for i := 0; i < len(node.Content); i += 2 {
			key := node.Content[i]
			value := node.Content[i+1]

			if key.Kind == yaml.ScalarNode {
				keyName := key.Value
				v.stack = append(v.stack, keyName)
				v.currentStackAsStr = strings.Join(v.stack, "/")

				v.yamlCursorNode = v.yamlCursorNode.Obtain(keyName)
				v.yamlCursorNode.data = &YamlNodeData{
					Kind: YamlNodeKindUnhandled,
					Node: key,
				}
				v.validateKeyPair(key, errors)

				// fmt.Printf("key: %s, value: %v\n", keyName, key.Value)

				v.ValidateNodesExistAndBuildYamlInfo(value, errors)

				// Undo the cursor
				v.yamlCursorNode = v.yamlCursorNode.parent

				// Undo the stack
				v.stack = v.stack[:len(v.stack)-1]
				v.currentStackAsStr = strings.Join(v.stack, "/")
			}
			// else {
			// 	fmt.Printf("key: %s is not a scalar node\n", key.Value)
			// }
		}

	} else {
		// fmt.Printf("unexpected node kind. Found: Kind: %v - Tag: %v - Stack: %s\n", node.Kind, node.Tag, v.currentStackAsStr)
	}
}

func (v *Validator) getActionPackageInfo(
	specNode *SpecTreeNode,
	yamlNode *YamlTreeNode,
) *ActionPackageInFilesystem {
	// Get the path by splitting the spec node's path and adding "path"
	p := append(strings.Split(specNode.GetData().(*Entry).Path, "/")[:len(strings.Split(specNode.GetData().(*Entry).Path, "/"))-1], "path")

	// Get the path yaml node from the parent's children
	pathYamlNode, ok := yamlNode.Parent().GetChildren()["path"].(*YamlTreeNode)
	if !ok {
		return nil
	}

	// Get the node value that points to the path
	errorOrPath := v.getNodeValuePointsToPath(strings.Join(p, "/"), pathYamlNode, "actions")

	// Check if errorOrPath is a string (path) or an error

	if errorOrPath.Error != nil {
		// If not a path, we can ignore it
		return nil
	}
	path := errorOrPath.Path

	var foundInFilesystem *ActionPackageInFilesystem

	// Matches zip files
	foundInFilesystem = v.actionPackagesFoundInFS[path]
	if foundInFilesystem == nil {
		// If it's a directory, look for package.yaml
		foundInFilesystem = v.actionPackagesFoundInFS[filepath.Join(path, "package.yaml")]
	}

	if foundInFilesystem != nil {
		foundInFilesystem.ReferencedFromAgentSpec = true
	}

	return foundInFilesystem

}

// Create structure for Error or string
type ErrorOrPath struct {
	Error *Error
	Path  string
}

func (v *Validator) getNodeValuePointsToPath(specPathForErrorMsg string, yamlNode *YamlTreeNode, relativeTo string) ErrorOrPath {
	valueText := yamlNode.data.Node.Value
	if valueText == "" {
		return ErrorOrPath{
			Error: NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a non-empty string.", specPathForErrorMsg),
				yamlNode.data, Critical),
		}
	}

	if strings.Contains(valueText, "\\") {
		return ErrorOrPath{
			Error: NewErrorFromYamlNode(fmt.Sprintf("%s may not contain `\\` characters.", specPathForErrorMsg),
				yamlNode.data, Critical),
		}
	}

	// If v.agentRootDirOrZip is not a zip file, then it's a directory, read the contents from it

	var p string
	var pathExists bool
	if !v.IsZipValidation {
		if !strings.HasPrefix(relativeTo, ".") {
			relativeTo = "./" + relativeTo
		}
		p = filepath.Clean(filepath.Join(v.agentRootDirOrZip, relativeTo, valueText))
		pathExists = fileExists(p)
	} else {
		relativeTo = strings.TrimPrefix(relativeTo, ".")
		relativeTo = strings.TrimPrefix(relativeTo, "/")
		// Check that the relative path exists in the zip file (same thing as above but we're inside a .zip)
		// Join with / and not with filepath.Join as we're dealing with zip files and not the filesystem
		if relativeTo == "" {
			p = valueText
		} else {
			p = strings.Join([]string{relativeTo, valueText}, "/")
		}
		_, err := GetFileFromZip(v.agentRootDirOrZip, p)
		if err != nil {
			// Get just basename of valueText
			return ErrorOrPath{
				Error: NewErrorFromYamlNodeAndCode(fmt.Sprintf("Expected %s to map to a file named '%s' relative to '%s' (full path inside of .zip: '%s').",
					specPathForErrorMsg, valueText, relativeTo, p),
					yamlNode.data, Critical, ActionPackageInfoUnsynchronized),
			}
		}
		pathExists = true
	}

	if !pathExists {
		relativeTo = strings.TrimPrefix(relativeTo, "./")
		if relativeTo == "./" {
			relativeTo = "dir('agent-spec.yaml')"
		} else {
			relativeTo = fmt.Sprintf("dir('agent-spec.yaml')/%s", relativeTo)
		}
		return ErrorOrPath{
			Error: NewErrorFromYamlNodeAndCode(fmt.Sprintf("Expected %s to map to a file named '%s' relative to '%s'.",
				specPathForErrorMsg, valueText, relativeTo),
				yamlNode.data, Critical, ActionPackageInfoUnsynchronized),
		}
	}

	return ErrorOrPath{
		Path: p,
	}
}

// Helper function to check if a file exists
func fileExists(filename string) bool {
	_, err := os.Stat(filename)
	return !os.IsNotExist(err)
}

/**
 * Validate that the yaml info matches the spec info.
 */
func (v *Validator) verifyYamlMatchesSpec(
	specNode *SpecTreeNode,
	yamlNode *YamlTreeNode,
	parentNode *YamlTreeNode,
	errors chan Error,
) {
	if specNode.Parent() == nil {
		if yamlNode == nil {
			panic("Expected yaml node to be provided for root.")
		}
		for _, child := range specNode.GetChildren() {
			childNode, ok := child.(*SpecTreeNode)
			if !ok {
				panic("Expected child node to be a SpecTreeNode.")
			}
			yamlChild, _ := yamlNode.GetChildren()[childNode.GetName()].(*YamlTreeNode)
			// It's ok for yamlChild to be nil.
			v.verifyYamlMatchesSpec(childNode, yamlChild, yamlNode, errors)
		}
		return
	}

	if specNode.GetData() == nil {
		panic(fmt.Sprintf("Expected data to be loaded. Name: %s. Parent: %s", specNode.GetName(), specNode.Parent().GetName()))
	}

	specData, ok := specNode.GetData().(*Entry)
	if !ok {
		panic("Expected specNode.GetData() to be *Entry")
	}

	if specData.Required {
		if yamlNode == nil {
			var data *YamlNodeData
			if parentNode != nil {
				parentData, ok := parentNode.GetData().(*YamlNodeData)
				if ok {
					data = parentData
				}
			}
			errors <- *NewErrorFromYamlNode(fmt.Sprintf("Missing required entry: %s.", specData.Path),
				data, Critical)
		}
	}

	if yamlNode == nil {
		// Unable to proceed the validation for this node as the yaml info was not found.
		return
	}
	// Ok, the node exists. Let's validate it.
	if specData.Deprecated {
		errors <- *NewErrorFromYamlNode(fmt.Sprintf("Deprecated: '%s'. %s.", specData.Path, specData.Description),
			yamlNode.data, Warning)
	} else {
		switch specData.ExpectedType.ExpectedType {
		case ExpectedTypeEnumObject:
			for _, child := range specNode.GetChildren() {
				childNode, ok := child.(*SpecTreeNode)
				if !ok {
					panic("Expected child node to be a SpecTreeNode.")
				}
				yamlChild, _ := yamlNode.GetChildren()[childNode.GetName()].(*YamlTreeNode)
				v.verifyYamlMatchesSpec(childNode, yamlChild, yamlNode, errors)
			}

		case ExpectedTypeEnumList:
			if yamlNode.data.Kind != YamlNodeKindList {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a list.", specData.Path),
					yamlNode.data, Critical)
			} else {
				for _, listItemNode := range yamlNode.GetChildren() {
					for _, specChild := range specNode.GetChildren() {
						childNode, ok := listItemNode.GetChildren()[specChild.GetName()].(*YamlTreeNode)
						if !ok {
							childNode = nil
						}
						v.verifyYamlMatchesSpec(specChild.(*SpecTreeNode), childNode, yamlNode, errors)
					}
				}
			}

		case ExpectedTypeEnumString:
			if yamlNode.data.Kind != YamlNodeKindString {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a string (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			}

		case ExpectedTypeEnumActionPackageVersionLink, ExpectedTypeEnumActionPackageNameLink:
			if yamlNode.data.Kind != YamlNodeKindString {
				errors <- *NewErrorFromYamlNodeAndCode(fmt.Sprintf("Expected %s to be a string (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical, ActionPackageInfoUnsynchronized)
			} else {
				packageInfoInFilesystem := v.getActionPackageInfo(specNode, yamlNode)
				if packageInfoInFilesystem != nil {
					if specData.ExpectedType.ExpectedType == ExpectedTypeEnumActionPackageVersionLink {
						versionInFilesystem := packageInfoInFilesystem.GetVersion()
						if versionInFilesystem == "" {
							versionInFilesystem = "Unable to get version from package.yaml"
						}
						versionInAgentPackage := yamlNode.data.Node.Value
						if versionInFilesystem != versionInAgentPackage {
							errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to match the version in the action package being referenced ('%s'). Found in spec: '%s'", specData.Path, versionInFilesystem, versionInAgentPackage),
								yamlNode.data, Critical)
						}
					} else if specData.ExpectedType.ExpectedType == ExpectedTypeEnumActionPackageNameLink {
						nameInFilesystem := packageInfoInFilesystem.GetName()
						if nameInFilesystem == "" {
							nameInFilesystem = "Unable to get name from package.yaml"
						}
						nameInAgentPackage := yamlNode.data.Node.Value
						if nameInFilesystem != nameInAgentPackage {
							errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to match the name in the action package being referenced ('%s'). Found in spec: '%s'", specData.Path, nameInFilesystem, nameInAgentPackage),
								yamlNode.data, Critical)
						}
					}
				}
			}

		case ExpectedTypeEnumInt:
			if yamlNode.data.Kind != YamlNodeKindInt {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be an int (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			}

		case ExpectedTypeEnumFloat:
			if yamlNode.data.Kind != YamlNodeKindInt && yamlNode.data.Kind != YamlNodeKindFloat {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a float (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			}

		case ExpectedTypeEnumBool:
			if yamlNode.data.Kind != YamlNodeKindBool {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a bool (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			}

		case ExpectedTypeEnumEnum, ExpectedTypeEnumZipOrFolderBasedOnPath:
			if yamlNode.data.Kind != YamlNodeKindString {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a string (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			} else {
				yamlNodeText := yamlNode.data.Node.Value
				enumValues := specData.ExpectedType.EnumValues
				if len(enumValues) == 0 {
					enumValues = []string{"No enum values specified"}
				}

				// Check if yamlNodeText is in enumValues
				if !slices.Contains(enumValues, yamlNodeText) {
					errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be one of %v (found '%s').", specData.Path, enumValues, yamlNodeText),
						yamlNode.data, Critical)
				} else if specData.ExpectedType.ExpectedType == ExpectedTypeEnumZipOrFolderBasedOnPath {
					packageInfoInFilesystem := v.getActionPackageInfo(specNode, yamlNode)
					if packageInfoInFilesystem != nil {
						var expectedTypeFromFilesystem string
						if packageInfoInFilesystem.IsZip() {
							expectedTypeFromFilesystem = "zip"
						} else {
							expectedTypeFromFilesystem = "folder"
						}

						if yamlNodeText != expectedTypeFromFilesystem {
							errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to match the type in the action package being referenced ('%s'). Found in spec: '%s'", specData.Path, expectedTypeFromFilesystem, yamlNodeText),
								yamlNode.data, Critical)
						}

						if expectedTypeFromFilesystem == "zip" {
							if !v.IsZipValidation {
								errors <- *NewErrorFromYamlNode("The 'zip' mode is only supported inside a .zip distribution. When unzipped, action packages must NOT be zipped! -- maybe `agent-cli package extract` was not used to extract the agent?",
									yamlNode.data, Critical)
							}
						} else {
							if v.IsZipValidation {
								errors <- *NewErrorFromYamlNode("The 'folder' mode is only supported when validating an unzipped distribution. When a .zip distribution is provided, action packages are expected to be zipped. -- maybe `agent-cli package build` was not used to create the .zip?",
									yamlNode.data, Critical)
							}
						}
					}
				}
			}

		case ExpectedTypeEnumFile:
			if yamlNode.data.Kind != YamlNodeKindString {
				errors <- *NewErrorFromYamlNode(fmt.Sprintf("Expected %s to be a string (found %s).", specData.Path, yamlNode.data.Kind),
					yamlNode.data, Critical)
			} else {
				relativeTo := specData.ExpectedType.RelativeTo
				if relativeTo == nil || *relativeTo == "" {
					panic(fmt.Sprintf("Expected relative_to to be set in %s", specData.Path))
				}

				errorOrPath := v.getNodeValuePointsToPath(specData.Path, yamlNode, *relativeTo)
				if errorOrPath.Error != nil {
					errors <- *errorOrPath.Error
				}
			}

		default:
			panic(fmt.Sprintf("Unexpected expected type: %v", specData.ExpectedType.ExpectedType))
		}
	}
}

/**
 * Validate that all action packages found in the filesystem are referenced in the agent-spec.yaml.
 */
func (v *Validator) validateUnreferencedActionPackages(errors chan Error) {
	agentPackage := v.yamlInfoLoaded.GetChildren()["agent-package"]
	if agentPackage == nil {
		errors <- *NewErrorFromYamlNode("Did not find agent-package in the agent-spec.yaml.", nil, Critical)
		return
	}
	reportErrorAtNode := agentPackage

	agents, ok := agentPackage.GetChildren()["agents"].(*YamlTreeNode)
	if ok {
		reportErrorAtNode = agents
		for _, agent := range agents.GetChildren() {
			actionPackagesNode, ok := agent.(*YamlTreeNode).GetChildren()["action-packages"].(*YamlTreeNode)
			if ok {
				reportErrorAtNode = actionPackagesNode
				break
			}
		}
	}

	for _, actionPackageInFilesystem := range v.actionPackagesFoundInFS {
		if !actionPackageInFilesystem.ReferencedFromAgentSpec {
			var errorNode *YamlNodeData
			if reportErrorAtNode != nil {
				errorNode = reportErrorAtNode.GetData().(*YamlNodeData)
			}

			errors <- *NewErrorFromYamlNode(
				fmt.Sprintf("Action Package path not referenced in the `agent-spec.yaml`: '%s'.", actionPackageInFilesystem.RelativePath),
				errorNode,
				Warning,
			)
		}
	}
}

/**
 * Entry point for validation
 */
func (v *Validator) Validate(rootNode *yaml.Node, errors chan Error, ignoreActions bool) {
	v.actionPackagesFoundInFS = make(map[string]*ActionPackageInFilesystem)
	if !ignoreActions {
		v.actionPackagesFoundInFS = ListActionPackagesFromAgent(v.agentRootDirOrZip)
	}

	v.ValidateNodesExistAndBuildYamlInfo(rootNode, errors)
	root := ConvertFlattenedToNested(v.specEntries)
	v.verifyYamlMatchesSpec(root, v.yamlInfoLoaded, nil, errors)
	v.validateUnreferencedActionPackages(errors)
	close((errors))
}
