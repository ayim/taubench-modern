package cmd

import (
	"fmt"
	"slices"
	"strings"

	"gopkg.in/yaml.v3"
)

type TreeNode interface {
	String() string
	GetData() interface{}
	GetChildren() map[string]TreeNode
	GetName() string
	PrettyData() string
}

func Pretty(n TreeNode, level int) string {
	levelStr := ""
	for i := 0; i < level; i++ {
		levelStr += "  "
	}

	ret := fmt.Sprintf("%s%s%s\n", levelStr, n.GetName(), n.PrettyData())

	// Sort children by the name before printing
	children := make([]TreeNode, 0, len(n.GetChildren()))
	for _, child := range n.GetChildren() {
		children = append(children, child)
	}

	slices.SortStableFunc(children, func(a, b TreeNode) int {
		return strings.Compare(a.GetName(), b.GetName())
	})

	for _, child := range children {
		ret += Pretty(child, level+1)
	}
	return ret
}

func (n *SpecTreeNode) String() string {
	return fmt.Sprintf("%T(%s)", n, n.name)
}

func (n *YamlTreeNode) String() string {
	return fmt.Sprintf("%T(%s)", n, n.name)
}

type SpecTreeNode struct {
	name     string
	parent   *SpecTreeNode
	children map[string]*SpecTreeNode
	data     *Entry
}

type YamlNodeData struct {
	Node *yaml.Node
	Kind YamlNodeKind
}

type YamlTreeNode struct {
	name     string
	parent   *YamlTreeNode
	children map[string]*YamlTreeNode
	data     *YamlNodeData
}

func NewSpecTreeNode(name string, parent *SpecTreeNode) *SpecTreeNode {
	node := &SpecTreeNode{
		name:     name,
		parent:   parent,
		children: make(map[string]*SpecTreeNode),
		data:     nil,
	}
	if parent != nil {
		node.parent = parent
	}
	return node
}

func NewYamlTreeNode(name string, parent *YamlTreeNode) *YamlTreeNode {
	node := &YamlTreeNode{
		name:     name,
		parent:   parent,
		children: make(map[string]*YamlTreeNode),
		data:     nil,
	}
	if parent != nil {
		node.parent = parent
	}
	return node
}

func (n *SpecTreeNode) GetData() interface{} {
	if n.data == nil {
		panic(fmt.Sprintf("Data not set for %s", n.name))
	}
	return n.data
}
func (n *YamlTreeNode) GetData() interface{} {
	if n.data == nil {
		panic(fmt.Sprintf("Data not set for %s", n.name))
	}
	return n.data
}

func (n *SpecTreeNode) GetName() string {
	return n.name
}

func (n *YamlTreeNode) GetName() string {
	return n.name
}

func (n *SpecTreeNode) Parent() *SpecTreeNode {
	return n.parent
}

func (n *YamlTreeNode) Parent() *YamlTreeNode {
	return n.parent
}

func (n *SpecTreeNode) GetChildren() map[string]TreeNode {
	ret := make(map[string]TreeNode)
	for _, child := range n.children {
		ret[child.name] = child
	}
	return ret
}

func (n *YamlTreeNode) GetChildren() map[string]TreeNode {
	ret := make(map[string]TreeNode)
	for _, child := range n.children {
		ret[child.name] = child
	}
	return ret
}

func (n *SpecTreeNode) Obtain(name string) *SpecTreeNode {
	child := n.children[name]
	if child == nil {
		child = NewSpecTreeNode(name, n)
		n.children[name] = child
	}
	return child
}

func (n *YamlTreeNode) Obtain(name string) *YamlTreeNode {
	if _, exists := n.children[name]; !exists {
		child := NewYamlTreeNode(name, n)
		n.children[name] = child
	}
	return n.children[name]
}

func (n *SpecTreeNode) PrettyData() string {
	if n.data == nil {
		return " (no data)"
	}
	ret := ""
	if n.data.Required {
		ret += " (required)"
	}
	if n.data.Deprecated {
		ret += " (deprecated)"
	}
	return ret
}

func (n *YamlTreeNode) PrettyData() string {
	if n.GetData() == nil {
		return " (no data)"
	}
	data, ok := n.GetData().(*YamlNodeData)
	if !ok {
		return ""
	}
	return fmt.Sprintf(" (%s)", data.Kind)
}

// ConvertFlattenedToNested converts a flattened dictionary to a nested tree of SpecTreeNode objects
func ConvertFlattenedToNested(flattened map[string]*Entry) *SpecTreeNode {
	root := NewSpecTreeNode("root", nil)
	for path, entry := range flattened {
		curr := root
		parts := strings.Split(path, "/")
		for _, part := range parts {
			curr = curr.Obtain(part)
		}
		curr.data = entry
	}
	return root
}
