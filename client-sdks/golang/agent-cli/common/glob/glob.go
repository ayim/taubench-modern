package glob

import (
	"os"
	"path/filepath"
	"strings"
)

// IsMatch checks if a path matches a glob pattern
// Supports * for any characters in a segment and ** for any number of segments
func IsMatch(pattern, path string) bool {
	// Normalize paths to use forward slashes
	pattern = filepath.ToSlash(pattern)
	path = filepath.ToSlash(path)

	// Remove leading ./ from pattern and path for consistency
	if strings.HasPrefix(pattern, "./") {
		pattern = pattern[2:]
	}
	if strings.HasPrefix(path, "./") {
		path = path[2:]
	}

	// Split pattern and path into segments
	patternSegments := strings.Split(pattern, "/")
	pathSegments := strings.Split(path, "/")

	return matchSegments(patternSegments, pathSegments, 0, 0)
}

// matchSegments recursively matches pattern segments against path segments
func matchSegments(pattern, path []string, patternIdx, pathIdx int) bool {
	// Base cases
	if patternIdx == len(pattern) {
		return pathIdx == len(path)
	}

	// Current pattern segment
	segment := pattern[patternIdx]

	// Handle ** (matches zero or more segments)
	if segment == "**" {
		// Try matching zero segments
		if matchSegments(pattern, path, patternIdx+1, pathIdx) {
			return true
		}

		// Try matching one or more segments
		for i := pathIdx; i < len(path); i++ {
			if matchSegments(pattern, path, patternIdx, i+1) { // Keep ** in pattern
				return true
			}
		}
		return false
	}

	// We've reached the end of the path but not the pattern
	if pathIdx >= len(path) {
		return false
	}

	// Match current segment with wildcards
	matched, err := filepath.Match(segment, path[pathIdx])
	if err != nil {
		// If there's an error in the pattern, treat as no match
		return false
	}

	if matched {
		return matchSegments(pattern, path, patternIdx+1, pathIdx+1)
	}

	return false
}

// Exclude returns all files and directories in rootDir that don't match any of the exclude patterns
// Returns a map where keys are paths and values indicate if the path is a directory
func Exclude(rootDir string, patterns []string) (map[string]bool, error) {
	// Normalize rootDir
	rootDir = filepath.Clean(rootDir)
	absRootDir, err := filepath.Abs(rootDir)
	if err != nil {
		return nil, err
	}
	rootDir = absRootDir

	// Map to track included paths (true = directory, false = file)
	included := make(map[string]bool)

	// First, collect all paths
	err = filepath.WalkDir(rootDir, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}

		// Skip the root directory itself
		if path == rootDir {
			return nil
		}

		// Get relative path for pattern matching
		relPath, err := filepath.Rel(rootDir, path)
		if err != nil {
			return err
		}

		// Check if path matches any exclude pattern
		excluded := false
		for _, pattern := range patterns {
			if IsMatch(pattern, relPath) {
				excluded = true
				break
			}
		}

		if !excluded {
			// Add to included paths (true if directory, false if file)
			included[path] = d.IsDir()
		}

		return nil
	})

	return included, err
}
