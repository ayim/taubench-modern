package cmd

import (
	"github.com/spf13/cobra"
)

var projectCmd = &cobra.Command{
	Use:   "project",
	Short: "Create agent projects from scratch or from Sema4.ai Studio.",
	Long:  `Create agent projects from scratch or from Sema4.ai Studio.`,
	Run:   runProjectCmd,
}

func runProjectCmd(cmd *cobra.Command, args []string) {
	cmd.Help()
}

func init() {
	rootCmd.AddCommand(projectCmd)
}
