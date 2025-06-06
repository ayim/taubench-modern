package cmd

import (
	"fmt"
)

type Severity string

const (
	Critical Severity = "critical"
	Warning  Severity = "warning"
	Info     Severity = "info"
)

type Range struct {
	StartPoint Point
	EndPoint   Point
}

type Point struct {
	Row    int
	Column int
}

type Error struct {
	Message  string
	Range    Range
	Code     ErrorCode
	Severity Severity
}

// Error constructor (use 0-based coordinates -- remember that yaml.Node.Line/Column is 1-based)
func NewError(message string, startLine int, startColumn int, endLine int, endColumn int, severity Severity) *Error {
	return &Error{
		Message:  message,
		Range:    Range{StartPoint: Point{Row: startLine, Column: startColumn}, EndPoint: Point{Row: endLine, Column: endColumn}},
		Severity: severity,
	}
}
func NewErrorFromYamlNodeAndCode(message string, yamlNode *YamlNodeData, severity Severity, code ErrorCode) *Error {
	err := NewErrorFromYamlNode(message, yamlNode, severity)
	err.Code = code
	return err
}

func NewErrorFromYamlNode(message string, yamlNode *YamlNodeData, severity Severity) *Error {
	if yamlNode == nil || yamlNode.Node == nil {
		return &Error{
			Message:  message,
			Range:    Range{StartPoint: Point{Row: 0, Column: 0}, EndPoint: Point{Row: 1, Column: 0}},
			Severity: severity,
		}
	}

	return &Error{
		Message:  message,
		Range:    Range{StartPoint: Point{Row: yamlNode.Node.Line - 1, Column: yamlNode.Node.Column - 1}, EndPoint: Point{Row: yamlNode.Node.Line, Column: 0}},
		Severity: severity,
	}
}

func createRangeFromLocation(startLine int, startCol int, endLine int, endCol int) map[string]map[string]int {

	return map[string]map[string]int{
		"start": {
			"line":      startLine,
			"character": startCol,
		},
		"end": {
			"line":      endLine,
			"character": endCol,
		},
	}
}

func (e *Error) AsDiagnostic(agentNode *Range) map[string]interface{} {
	var useLocation []int

	if e.Range == (Range{}) {
		useLocation = []int{0, 0, 1, 0}
		if agentNode != nil {
			useLocation = []int{
				agentNode.StartPoint.Row,
				agentNode.StartPoint.Column,
				agentNode.EndPoint.Row,
				agentNode.EndPoint.Column,
			}
		}
	} else {
		useLocation = []int{
			e.Range.StartPoint.Row,
			e.Range.StartPoint.Column,
			e.Range.EndPoint.Row,
			e.Range.EndPoint.Column,
		}
	}

	useRange := createRangeFromLocation(useLocation[0], useLocation[1], useLocation[2], useLocation[3])

	var severity int
	switch e.Severity {
	case Critical:
		severity = 1
	case Warning:
		severity = 2
	case Info:
		severity = 3
	default:
		panic(fmt.Sprintf("Unexpected severity: %s", e.Severity))
	}

	diagnostic := map[string]interface{}{
		"range":    useRange,
		"severity": severity,
		"source":   "sema4ai",
		"message":  e.Message,
	}

	if e.Code != "" {
		diagnostic["code"] = e.Code
	}

	return diagnostic
}
