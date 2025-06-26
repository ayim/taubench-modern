package common

import (
	"archive/zip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unicode"
)

var (
	Verbose bool
)

func Log(format string, a ...interface{}) {
	timestamp := time.Now().Format("2006-01-02 15:04:05.000")
	formattedStr := fmt.Sprintf("[%s] $: "+format, append([]interface{}{timestamp}, a...)...)
	lines := strings.Split(formattedStr, "\n")
	for i := 1; i < len(lines); i++ {
		lines[i] = "    " + lines[i]
	}
	indentedStr := strings.Join(lines, "\n")
	// Print to stderr so that it doesn't get mixed with stdout (which may be used for json output).
	fmt.Fprintln(os.Stderr, indentedStr)
}

func LogVerbose(format string, a ...interface{}) {
	if Verbose {
		Log(format, a...)
	}
}

func UnzipFile(sourceZip, targetDir string) error {
	archive, err := zip.OpenReader(sourceZip)
	if err != nil {
		return fmt.Errorf("failed to open zip file: %w", err)
	}
	defer archive.Close()

	for _, f := range archive.File {
		filePath := filepath.Join(targetDir, f.Name)

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(filePath, os.ModePerm); err != nil {
				return fmt.Errorf("failed to create directory: %w", err)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(filePath), os.ModePerm); err != nil {
			return fmt.Errorf("failed to create directory: %w", err)
		}

		dstFile, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
		if err != nil {
			return fmt.Errorf("failed to create file: %w", err)
		}

		fileInArchive, err := f.Open()
		if err != nil {
			dstFile.Close()
			return fmt.Errorf("failed to open file in archive: %w", err)
		}

		if _, err := io.Copy(dstFile, fileInArchive); err != nil {
			dstFile.Close()
			fileInArchive.Close()
			return fmt.Errorf("failed to copy file contents: %w", err)
		}

		dstFile.Close()
		fileInArchive.Close()
	}
	return nil
}

func KebabCase(s string) string {
	var result []rune
	for i, r := range s {
		if unicode.IsSpace(r) || r == '_' || r == '.' || r == ',' {
			result = append(result, '-')
		} else {
			if unicode.IsUpper(r) {
				if i > 0 && (unicode.IsLower(rune(s[i-1])) || unicode.IsDigit(rune(s[i-1]))) {
					result = append(result, '-')
				}
				result = append(result, unicode.ToLower(r))
			} else {
				result = append(result, r)
			}
		}
	}
	return strings.Trim(strings.Join(strings.Fields(string(result)), "-"), "-")
}

func CreateTempDir(suffix string) (string, error) {
	// Construct a temp directory in a way that we can find it in case we forget to delete something
	dirName := fmt.Sprintf("sema4ai-agent-cli-%s-", suffix)
	return os.MkdirTemp("", dirName)
}

func ConcatErrors(errors []error) error {
	message := ""

	for _, error := range errors {
		message += error.Error() + "\n"
	}

	return fmt.Errorf("%s", message)
}

func AddIfNotExists[T comparable](slice []T, s T) []T {
	for _, ele := range slice {
		if ele == s {
			return slice
		}
	}
	return append(slice, s)
}

type ConcurrentSlice[T comparable] struct {
	sync.RWMutex
	items []T
}

func (cs *ConcurrentSlice[T]) Has(target T) bool {
	cs.RLock()
	defer cs.RUnlock()

	for _, item := range cs.items {
		if item == target {
			return true
		}
	}

	return false
}

func (cs *ConcurrentSlice[T]) AddIfNotExists(item T) []T {
	cs.Lock()
	defer cs.Unlock()

	cs.items = AddIfNotExists(cs.items, item)
	return cs.items
}
