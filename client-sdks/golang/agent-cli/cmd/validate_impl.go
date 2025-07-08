package cmd

import (
	"errors"
	"fmt"
)

type ExpectedTypeEnum string

const (
	ExpectedTypeEnumObject                   ExpectedTypeEnum = "object"
	ExpectedTypeEnumString                   ExpectedTypeEnum = "string"
	ExpectedTypeEnumEnum                     ExpectedTypeEnum = "enum"
	ExpectedTypeEnumFile                     ExpectedTypeEnum = "file"
	ExpectedTypeEnumList                     ExpectedTypeEnum = "list"
	ExpectedTypeEnumBool                     ExpectedTypeEnum = "bool"
	ExpectedTypeEnumInt                      ExpectedTypeEnum = "int"
	ExpectedTypeEnumFloat                    ExpectedTypeEnum = "float"
	ExpectedTypeEnumNOT_SET                  ExpectedTypeEnum = "NOT_SET"
	ExpectedTypeEnumActionPackageVersionLink ExpectedTypeEnum = "action_package_version_link"
	ExpectedTypeEnumActionPackageNameLink    ExpectedTypeEnum = "action_package_name_link"
	ExpectedTypeEnumZipOrFolderBasedOnPath   ExpectedTypeEnum = "zip_or_folder_based_on_path"
	ExpectedTypeEnumAgentSemverVersion       ExpectedTypeEnum = "agent_semver_version"
	ExpectedTypeEnumMcpServerUrl             ExpectedTypeEnum = "mcp_server_url"
	ExpectedTypeEnumMcpServerTransport       ExpectedTypeEnum = "mcp_server_transport"
	ExpectedTypeEnumMcpServerCommandLine     ExpectedTypeEnum = "mcp_server_command_line"
	ExpectedTypeEnumMcpServerCwd             ExpectedTypeEnum = "mcp_server_cwd"
	ExpectedTypeEnumMcpServerEnv             ExpectedTypeEnum = "mcp_server_env"
	ExpectedTypeEnumMcpServerHeaders         ExpectedTypeEnum = "mcp_server_headers"
)

func isValidExpectedTypeEnum(et ExpectedTypeEnum) bool {
	switch et {
	case ExpectedTypeEnumObject,
		ExpectedTypeEnumString,
		ExpectedTypeEnumEnum,
		ExpectedTypeEnumFile,
		ExpectedTypeEnumList,
		ExpectedTypeEnumBool,
		ExpectedTypeEnumInt,
		ExpectedTypeEnumFloat,
		ExpectedTypeEnumNOT_SET,
		ExpectedTypeEnumActionPackageVersionLink,
		ExpectedTypeEnumActionPackageNameLink,
		ExpectedTypeEnumZipOrFolderBasedOnPath,
		ExpectedTypeEnumAgentSemverVersion,
		ExpectedTypeEnumMcpServerUrl,
		ExpectedTypeEnumMcpServerTransport,
		ExpectedTypeEnumMcpServerCommandLine,
		ExpectedTypeEnumMcpServerCwd,
		ExpectedTypeEnumMcpServerEnv,
		ExpectedTypeEnumMcpServerHeaders:
		return true
	default:
		return false
	}
}

type YamlNodeKind string

const (
	YamlNodeKindUnhandled YamlNodeKind = "unhandled"
	YamlNodeKindList      YamlNodeKind = "list"
	YamlNodeKindListItem  YamlNodeKind = "list-item"
	YamlNodeKindBool      YamlNodeKind = "bool"
	YamlNodeKindInt       YamlNodeKind = "int"
	YamlNodeKindFloat     YamlNodeKind = "float"
	YamlNodeKindString    YamlNodeKind = "string"
)

type ErrorCode string

const (
	ActionPackageInfoUnsynchronized ErrorCode = "action_package_info_unsynchronized"
)

type ExpectedType struct {
	// The type which is expected from the spec.
	ExpectedType ExpectedTypeEnum

	// If a "string" type, the recommended values may be provided
	// (this means that any string value is accepted, but the recommended values can be used to help the user).
	RecommendedValues []string

	// If an "enum" type, the accepted values should be provided.
	EnumValues []string

	// If a "file" type, the relative path to the file (based on the agent root dir) should be provided.
	RelativeTo *string
}

func NewExpectedType(expectedType ExpectedTypeEnum, recommendedValues []string, enumValues []string, relativeTo *string) (*ExpectedType, error) {
	et := &ExpectedType{
		ExpectedType:      expectedType,
		RecommendedValues: recommendedValues,
		EnumValues:        enumValues,
		RelativeTo:        relativeTo,
	}

	err := et.validate()
	if err != nil {
		return nil, err
	}
	return et, nil
}

func (et *ExpectedType) validate() error {
	if et.ExpectedType == ExpectedTypeEnumFile && et.RelativeTo == nil {
		return errors.New("relative_to must be provided for file type")
	}

	if et.ExpectedType == ExpectedTypeEnumEnum && len(et.EnumValues) == 0 {
		return errors.New("enum_values must be provided for enum type")
	}

	return nil
}

// Entry struct definition
type Entry struct {
	Path         string       // The path to the key in the YAML spec (i.e.: "agent-package/agents/name")
	Description  string       // The description of the key in the YAML spec.
	ExpectedType ExpectedType // The expected type of the key in the YAML spec.
	Required     bool         // Whether the key is required (default is true).
	Deprecated   bool         // Whether the key is deprecated (default is false).
}

// NewEntry constructor function to initialize with default values
func NewEntry(path string, description string, expectedType ExpectedType, required bool, deprecated bool) *Entry {
	return &Entry{
		Path:         path,
		Description:  description,
		ExpectedType: expectedType,
		Required:     required,
		Deprecated:   deprecated,
	}
}

// LoadSpec loads the specification from a JSON-like map (50 python lines turn into ~= 150 lines of Go).
func LoadSpec(jsonSpec map[string]interface{}) (map[string]*Entry, error) {
	ret := make(map[string]*Entry)

	for path, value := range jsonSpec {
		valueMap, ok := value.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("invalid spec: %s. Expected a dictionary. Found %T", path, value)
		}

		// Copy valueMap to avoid mutating the original.
		valueCopy := make(map[string]interface{})
		for k, v := range valueMap {
			valueCopy[k] = v
		}

		// Extract deprecated.
		deprecatedVal, ok := valueCopy["deprecated"]
		if ok {
			delete(valueCopy, "deprecated")
		} else {
			deprecatedVal = false
		}
		deprecatedBool, ok := deprecatedVal.(bool)
		if !ok {
			return nil, fmt.Errorf("invalid spec: %s. 'deprecated' should be bool", path)
		}

		// Extract required.
		requiredVal, ok := valueCopy["required"]
		if ok {
			delete(valueCopy, "required")
		} else {
			requiredVal = false
		}
		requiredBool, ok := requiredVal.(bool)
		if !ok {
			return nil, fmt.Errorf("invalid spec: %s. 'required' should be bool", path)
		}

		// Extract expected-type.
		expectedTypeVal, ok := valueCopy["expected-type"]
		if ok {
			delete(valueCopy, "expected-type")
		} else {
			expectedTypeVal = nil
		}

		// Extract description.
		descriptionVal, ok := valueCopy["description"]
		if ok {
			delete(valueCopy, "description")
		} else {
			return nil, fmt.Errorf("invalid spec: %s. Expected a description", path)
		}
		descriptionStr, ok := descriptionVal.(string)
		if !ok || descriptionStr == "" {
			return nil, fmt.Errorf("invalid spec: %s. Expected a description", path)
		}

		// Remove note if it exists.
		_, ok = valueCopy["note"]
		if ok {
			delete(valueCopy, "note")
		}

		var recommendedValues []string
		var enumValues []string
		var relativeTo string

		if expectedTypeMap, ok := expectedTypeVal.(map[string]interface{}); ok {
			// Extract recommended-values.
			if val, ok := expectedTypeMap["recommended-values"]; ok {
				if arr, ok := val.([]interface{}); ok {
					for _, v := range arr {
						if s, ok := v.(string); ok {
							recommendedValues = append(recommendedValues, s)
						} else {
							return nil, fmt.Errorf("invalid spec: %s. recommended-values should be array of strings", path)
						}
					}
				} else {
					return nil, fmt.Errorf("invalid spec: %s. recommended-values should be array", path)
				}
			}

			// Extract values.
			if val, ok := expectedTypeMap["values"]; ok {
				if arr, ok := val.([]interface{}); ok {
					for _, v := range arr {
						if s, ok := v.(string); ok {
							enumValues = append(enumValues, s)
						} else {
							return nil, fmt.Errorf("invalid spec: %s. values should be array of strings", path)
						}
					}
				} else {
					return nil, fmt.Errorf("invalid spec: %s. values should be array", path)
				}
			}

			// Extract relative-to.
			if val, ok := expectedTypeMap["relative-to"]; ok {
				if s, ok := val.(string); ok {
					relativeTo = s
				} else {
					return nil, fmt.Errorf("invalid spec: %s. relative-to should be string", path)
				}
			}

			// Extract type.
			if val, ok := expectedTypeMap["type"]; ok {
				expectedTypeVal = val
			} else {
				expectedTypeVal = nil
			}
		}

		if len(valueCopy) > 0 {
			return nil, fmt.Errorf("invalid spec: %s. Unexpected keys: %v", path, valueCopy)
		}

		var expectedTypeEnum ExpectedTypeEnum
		if expectedTypeVal == nil {
			expectedTypeEnum = ExpectedTypeEnumNOT_SET
		} else {
			expectedTypeStr, ok := expectedTypeVal.(string)
			if !ok {
				return nil, fmt.Errorf("invalid spec: %s. Expected type %v is not a valid expected type", path, expectedTypeVal)
			}
			expectedTypeEnum = ExpectedTypeEnum(expectedTypeStr)
			if !isValidExpectedTypeEnum(expectedTypeEnum) {
				return nil, fmt.Errorf("invalid spec: %s. Expected type %s is not a valid expected type", path, expectedTypeStr)
			}
		}

		entry := NewEntry(
			path,
			descriptionStr,
			ExpectedType{
				ExpectedType:      expectedTypeEnum,
				RecommendedValues: recommendedValues,
				EnumValues:        enumValues,
				RelativeTo:        &relativeTo,
			},
			requiredBool,
			deprecatedBool,
		)

		ret[path] = entry
	}

	return ret, nil
}
