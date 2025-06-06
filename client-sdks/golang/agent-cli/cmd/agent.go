package cmd

import "github.com/spf13/cobra"

var agentCmd = &cobra.Command{
	Use:   "agent",
	Short: "Manage deployed Agents and Agent Projects.",
	Long:  "Manage deployed Agents and Agent Projects.",
	Run:   runAgentCmd,
}

func runAgentCmd(cmd *cobra.Command, args []string) {
	cmd.Help()
}

func init() {
	rootCmd.AddCommand(agentCmd)
}
