package common

import (
	"archive/zip"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"unicode"

	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

var (
	Verbose bool
	NoColor bool
)

func Ptr[T any](v T) *T { return &v }

type ExitCode struct {
	Code    int
	Message string
}

func Exit(code int, format string, rest ...interface{}) {
	message := format
	if len(rest) > 0 {
		message = fmt.Sprintf(format, rest...)
	}

	defer func() {
		if r := recover(); r != nil {
			if ec, ok := r.(ExitCode); ok {
				os.Exit(ec.Code)
			}
			panic(r)
		}
	}()

	panic(ExitCode{
		Code:    code,
		Message: message,
	})
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

// Copied from the action server to ensure consistent file naming conventions
func Slugify(s string) string {
	// Handle unicode: decompose (NFKD), then filter out accents (nonspacing marks), then compose (NFC)
	t := transform.Chain(
		norm.NFKD,
		runes.Remove(runes.In(unicode.Mn)), // drop combining marks
		norm.NFC,
	)
	s, _, _ = transform.String(t, s)

	// Lowercase
	s = strings.ToLower(s)
	// Remove all non-word, non-space, non-hyphen characters
	re := regexp.MustCompile(`[^\w\s-]`)
	s = re.ReplaceAllString(s, "")
	// Replace spaces and hyphens with a single hyphen
	re = regexp.MustCompile(`[-\s]+`)
	s = re.ReplaceAllString(s, "-")
	// Trim leading/trailing hyphens and underscores
	return strings.Trim(s, "-_")
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

// === HELPERS ===

// StringSlicesEqual checks if two string slices are equal (order and content)
func StringSlicesEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// DerefString returns the value of a string pointer or an empty string if nil
func DerefString(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// DecodeBase64 decodes a base64-encoded string and returns the bytes.
func DecodeBase64(s string) ([]byte, error) {
	if s == "" {
		return nil, errors.New("input string is empty")
	}
	decoded, err := base64.StdEncoding.DecodeString(s)
	if err != nil {
		return nil, err
	}
	return decoded, nil
}
