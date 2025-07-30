package cmd

import (
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	"github.com/spf13/cobra"
)

var externalsCmd = &cobra.Command{
	Use:   "externals",
	Short: "Manage external sources for agent projects.",
	Long:  "Manage external sources for agent projects.",
	Run:   runExternalsCmd,
}

func runExternalsCmd(cmd *cobra.Command, _ []string) {
	if err := cmd.Help(); err != nil {
		pretty.Error("Error while running help cmd: %+v", err)
	}
}

func init() {
	rootCmd.AddCommand(externalsCmd)
}
