package cmd

import (
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	"github.com/spf13/cobra"
)

var agentCmd = &cobra.Command{
	Use:   "agent",
	Short: "Manage deployed Agents and Agent Projects.",
	Long:  "Manage deployed Agents and Agent Projects.",
	Run:   runAgentCmd,
}

func runAgentCmd(cmd *cobra.Command, args []string) {
	if err := cmd.Help(); err != nil {
		pretty.Error("Error while running help cmd: %+v", err)
	}
}

func init() {
	rootCmd.AddCommand(agentCmd)
}
