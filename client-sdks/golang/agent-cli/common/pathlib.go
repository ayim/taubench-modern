package common

import (
	"crypto/rand"
	"fmt"
	"os"
	"path/filepath"

	"github.com/robocorp/rcc/common"
	"github.com/robocorp/rcc/pathlib"
)

// If destination file exists, a unique name is generated for the file.
func CopyFileWithUniqueName(source, target string) (string, error) {
	var err error
	if pathlib.Exists(target) {
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
	if pathlib.Exists(target) {
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
	if !pathlib.Exists(target) {
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
		if !pathlib.Exists(newTarget) {
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

	defer pathlib.Walk(source, func(info os.FileInfo) bool {
		return false
	}, action)
	return nil
}
