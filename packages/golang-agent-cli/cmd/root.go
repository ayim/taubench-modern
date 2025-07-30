package cmd

import (
	"os"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	rccCommon "github.com/Sema4AI/rcc/common"

	"github.com/spf13/cobra"
)

var (
	versionFlag bool
)

var rootCmd = &cobra.Command{
	Use:          "agent-cli",
	Short:        "agent-cli provides support for managing agent projects and agent packages.",
	Long:         `agent-cli provides support for managing agent projects and agent packages.`,
	SilenceUsage: true,
	Run: func(cmd *cobra.Command, args []string) {
		if versionFlag {
			rccCommon.Stdout("%s\n", common.Version)
			// just getting the version not an error
			os.Exit(0)
		}
		// if no args, show help message
		if len(args) == 0 {
			if err := cmd.Help(); err != nil {
				pretty.Error("Error while running help cmd: %+v", err)
			}
			// no args is an error
			os.Exit(1)
		}
	},
}

func Execute() {
	err := rootCmd.Execute()
	if err != nil {
		os.Exit(1)
	}
}

func init() {
	rootCmd.Flags().BoolVarP(&versionFlag, "version", "v", false, "Show version and exit.")
	rootCmd.PersistentFlags().BoolVarP(&common.Verbose, "verbose", "V", false, "Set the verbose quality")
}
