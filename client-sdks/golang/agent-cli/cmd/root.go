package cmd

import (
	"os"

	"github.com/Sema4AI/agents-spec/cli/common"
	rccCommon "github.com/Sema4AI/rcc/common"

	"github.com/spf13/cobra"
)

var (
	versionFlag bool
)

// Aliases for backward compatibility
func log(format string, a ...interface{}) {
	common.Log(format, a...)
}

// Aliases for backward compatibility
func logVerbose(format string, a ...interface{}) {
	common.LogVerbose(format, a...)
}

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
			cmd.Help()
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
	rootCmd.PersistentFlags().BoolVarP(&common.Verbose, "verbose", "p", false, "Set the verbose quality")
}
