package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	"github.com/spf13/cobra"
)

var dockerCmd = &cobra.Command{
	Use:   "docker",
	Short: "Manage Docker MCP Gateway configuration.",
	Long:  "Manage Docker MCP Gateway configuration.",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := cmd.Help(); err != nil {
			pretty.Error("Error while running help cmd: %+v", err)
		}
		return nil
	},
}

var getRegistryCmd = &cobra.Command{
	Use:   "get-registry",
	Short: "Get registry for Docker mcp gateway.",
	Long:  "Get registry for Docker mcp gateway.",
	RunE: func(cmd *cobra.Command, args []string) error {
		result, err := common.ExtractDockerMcpGatewayToAgentPackage(nil)
		if err != nil {
			pretty.Error("Failed to extract Docker MCP Gateway from registry: %+v", err)
			return err
		}
		// Marshal result to JSON and print
		data, err := json.MarshalIndent(result, "", "  ")
		if err != nil {
			pretty.Error("Failed to marshal result to JSON: %+v", err)
			return err
		}
		fmt.Println(string(data))
		return nil
	},
}

var getCatalogCmd = &cobra.Command{
	Use:   "get-catalog",
	Short: "Get catalog for Docker mcp gateway.",
	Long:  "Get catalog for Docker mcp gateway.",
	RunE: func(cmd *cobra.Command, args []string) error {
		catalog, err := common.DockerParseEmbeddedCatalogYAML()
		if err != nil {
			pretty.Error("Failed to parse embedded catalog: %+v", err)
			return err
		}
		// Marshal result to JSON and print
		data, err := json.MarshalIndent(catalog, "", "  ")
		if err != nil {
			pretty.Error("Failed to marshal result to JSON: %+v", err)
			return err
		}
		fmt.Println(string(data))
		return nil
	},
}

func init() {
	dockerCmd.AddCommand(getRegistryCmd)
	dockerCmd.AddCommand(getCatalogCmd)
	externalsCmd.AddCommand(dockerCmd)
}
