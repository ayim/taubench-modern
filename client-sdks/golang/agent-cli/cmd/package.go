package cmd

import (
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/spf13/cobra"
)

var packageCmd = &cobra.Command{
	Use:   "package",
	Short: "Build and manage agent packages.",
	Long:  `Build and manage agent packages.`,
	Run:   runPackageCmd,
}

func runPackageCmd(cmd *cobra.Command, args []string) {
	if err := cmd.Help(); err != nil {
		common.Log("Error while running help cmd: %+v", err)
	}
}

func init() {
	rootCmd.AddCommand(packageCmd)
}
