package cmd

import (
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/spf13/cobra"
)

var projectCmd = &cobra.Command{
	Use:   "project",
	Short: "Create agent projects from scratch or from Sema4.ai Studio.",
	Long:  `Create agent projects from scratch or from Sema4.ai Studio.`,
	Run:   runProjectCmd,
}

func runProjectCmd(cmd *cobra.Command, args []string) {
	if err := cmd.Help(); err != nil {
		common.Log("Error while running help cmd: %+v", err)
	}
}

func init() {
	rootCmd.AddCommand(projectCmd)
}
