package common

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"golang.org/x/mod/semver"
)

func ValidateActionServerVersion() error {
	cmd := exec.Command(GetActionServerBin(), "version")
	output, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to execute action-server: %w", err)
	}

	version := strings.TrimSpace(string(output))
	if semver.Compare("v"+version, "v"+MIN_ACTION_SERVER_VERSION) < 0 {
		// In golang.org/x/mod/semver, version strings must begin with a leading "v".
		return fmt.Errorf(
			"The action-server version %s is lower than the minimum required version %s",
			version, MIN_ACTION_SERVER_VERSION,
		)
	}
	return nil
}

func GetActionServerBin() string {
	val, ok := os.LookupEnv(ACTION_SERVER_BIN_PATH_ENV_VARIABLE)
	if !(ok) {
		val = "action-server"
	}
	return val

}
