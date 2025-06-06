package cmd

import (
	"github.com/spf13/cobra"
)

var packageCmd = &cobra.Command{
	Use:   "package",
	Short: "Build and manage agent packages.",
	Long:  `Build and manage agent packages.`,
	Run:   runPackageCmd,
}

func runPackageCmd(cmd *cobra.Command, args []string) {
	cmd.Help()
}

func init() {
	rootCmd.AddCommand(packageCmd)
}
