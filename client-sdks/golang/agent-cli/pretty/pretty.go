package pretty

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/ttacon/chalk"
)

func getStdLogLine(format string, a ...interface{}) string {
	timestamp := time.Now().Format("2006-01-02 15:04:05.000")
	formattedStr := fmt.Sprintf("[agent-cli][%s] "+format, append([]interface{}{timestamp}, a...)...)
	lines := strings.Split(formattedStr, "\n")
	for i := 1; i < len(lines); i++ {
		lines[i] = "    " + lines[i]
	}
	indentedStr := strings.Join(lines, "\n")
	return indentedStr
}

func Log(format string, a ...interface{}) {
	if common.Verbose {
		logLine := getStdLogLine(format, a...)
		// Print to stderr so that it doesn't get mixed with stdout (which may be used for json output).
		fmt.Fprintln(os.Stderr, logLine)
		return
	}
	formattedStr := fmt.Sprintf(format, a...)
	fmt.Fprintln(os.Stderr, formattedStr)

}

func LogIfVerbose(format string, a ...interface{}) {
	if common.Verbose {
		Log(format, a...)
	}
}

func Print(format string, a ...interface{}) {
	formattedStr := fmt.Sprintf(format, a...)
	fmt.Fprintln(os.Stdout, formattedStr)

}

func StartSection(title string) {
	if common.Verbose {
		Info(title)
		return
	}
	fmt.Fprintln(os.Stderr)
	fmt.Fprintln(os.Stderr, title)
	fmt.Fprintln(os.Stderr)

}

func ListItem(format string, a ...interface{}) {
	formattedStr := fmt.Sprintf(format, a...)
	if common.Verbose {
		Info(format, a...)
		return
	}
	fmt.Fprintln(os.Stderr, " > ", formattedStr)

}

func SubListItem(format string, a ...interface{}) {
	formattedStr := fmt.Sprintf(format, a...)
	if common.Verbose {
		Info(format, a...)
		return
	}
	fmt.Fprintln(os.Stderr, " >> ", formattedStr)

}

func EndSection() {
	if common.Verbose {
		return
	}
	fmt.Fprintln(os.Stderr)

}

func SuccessLine(format string, a ...interface{}) string {
	style := chalk.Green.NewStyle().Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf(format+" [OK]", a...)
	return fmt.Sprint(style(formattedStr))
}

func WarningLine(format string, a ...interface{}) string {
	style := chalk.Yellow.NewStyle().WithTextStyle(chalk.Bold).Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf(format+" [WARN]", a...)
	return fmt.Sprint(style(formattedStr))
}

func ErrorLine(format string, a ...interface{}) string {
	style := chalk.Red.NewStyle().WithTextStyle(chalk.Bold).Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf(format+" [FAILED]", a...)
	return fmt.Sprint(style(formattedStr))
}

func Info(format string, a ...interface{}) {
	style := chalk.White.NewStyle().Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf("[INFO] "+format, a...)
	LogIfVerbose(style(formattedStr))
}

func Debug(format string, a ...interface{}) {
	style := chalk.White.NewStyle().WithTextStyle(chalk.Dim).Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf("[DEBUG] "+format, a...)
	LogIfVerbose(style(formattedStr))
}

func Warning(format string, a ...interface{}) {
	style := chalk.Yellow.NewStyle().Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf("[WARN] "+format, a...)
	LogIfVerbose(style(formattedStr))
}

func Error(format string, a ...interface{}) {
	style := chalk.Red.NewStyle().WithTextStyle(chalk.Bold).Style
	if common.NoColor {
		style = func(s string) string { return s }
	}
	formattedStr := fmt.Sprintf("[ERROR] "+format, a...)
	LogIfVerbose(style(formattedStr))
}

func Exit(code int, format string, a ...interface{}) {
	var style func(string) string
	if code == 0 {
		style = chalk.Green.NewStyle().Style
	} else {
		style = chalk.Red.NewStyle().WithTextStyle(chalk.Bold).Style
	}
	if common.NoColor {
		style = func(s string) string { return s }
	}
	common.Exit(code, style(format), a...)
}

func ErrorF(ignoreError bool, err error, format string, a ...interface{}) error {
	Error(format, a)
	if ignoreError {
		return nil
	}
	return err
}
