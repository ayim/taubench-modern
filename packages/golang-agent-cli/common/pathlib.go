package common

import (
	"crypto/rand"
	"fmt"
	"os"
	"path/filepath"

	"github.com/Sema4AI/rcc/common"
	"github.com/Sema4AI/rcc/pathlib"
)

// FileExists checks if a file or directory exists at the given path.
// Returns true if the path exists, false if it doesn't exist.
// For other errors (e.g., permission denied), returns true since the path
// likely exists but is inaccessible.
func FileExists(path string) bool {
	_, err := os.Stat(path)
	if err == nil {
		return true
	}
	// Only return false if we're certain the file doesn't exist
	return !os.IsNotExist(err)
}

// If destination file exists, a unique name is generated for the file.
func CopyFileWithUniqueName(source, target string) (string, error) {
	var err error
	if FileExists(target) {
		target, err = getUniquePath(target)
		if err != nil {
			return "", err
		}
	}

	err = pathlib.CopyFile(source, target, false)
	if err != nil {
		return "", err
	}
	return target, nil
}

// If destination file exists, a unique name is generated for the file.
func WriteFileWithUniqueName(
	target string, data []byte, mode os.FileMode,
) (string, error) {
	var err error
	if FileExists(target) {
		target, err = getUniquePath(target)
		if err != nil {
			return "", err
		}
	}

	err = pathlib.WriteFile(target, data, mode)
	if err != nil {
		return "", err
	}
	return target, nil
}

func getUniquePath(target string) (string, error) {
	if !FileExists(target) {
		return target, nil
	}
	ext := filepath.Ext(target)
	name := target[:len(target)-len(ext)]
	for {
		randomStr, err := generateRandomString(6)
		if err != nil {
			return "", err
		}
		newTarget := fmt.Sprintf("%s_%s%s", name, randomStr, ext)
		if !FileExists(newTarget) {
			return newTarget, nil
		}
	}
}

func generateRandomString(n int) (string, error) {
	const letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	bytes := make([]byte, n)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}

	for i, b := range bytes {
		bytes[i] = letters[b%byte(len(letters))]
	}
	return string(bytes), nil
}

type targetDir string

func (it targetDir) CopyBack(fullpath, relativepath string, details os.FileInfo) {
	targetFile := filepath.Join(string(it), relativepath)
	err := pathlib.CopyFile(fullpath, targetFile, false)
	if err != nil {
		common.Log("Warning %v while copying %v", err, targetFile)
	}
}

func (it targetDir) OverwriteBack(fullpath, relativepath string, details os.FileInfo) {
	targetFile := filepath.Join(string(it), relativepath)
	err := pathlib.CopyFile(fullpath, targetFile, true)
	if err != nil {
		common.Log("Warning %v while copying %v", err, targetFile)
	}
}

func CopyDir(source string, target string, overwrite bool) error {
	err := os.MkdirAll(target, 0o755)
	if err != nil {
		return err
	}

	action := targetDir(target).CopyBack
	if overwrite {
		action = targetDir(target).OverwriteBack
	}

	defer func() {
		if err := pathlib.Walk(source, func(info os.FileInfo) bool {
			return false
		}, action); err != nil {
			common.Log("Error %v while walking through source %v", err, source)
		}
	}()
	return nil
}
