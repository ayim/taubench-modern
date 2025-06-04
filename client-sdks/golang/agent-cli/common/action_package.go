package common

import (
	"gopkg.in/yaml.v2"
	"os"
)

type ActionPackageYamlDependencies struct {
	CondaForge []string `yaml:"conda-forge"`
	PyPi       []string `yaml:"pypi"`
}

type ActionPackageYamlPackaging struct {
	Exclude []string `yaml:"exclude"`
}

type ActionPackageYaml struct {
	Name         string                         `yaml:"name"`
	Description  string                         `yaml:"description"`
	Version      string                         `yaml:"version"`
	Dependencies *ActionPackageYamlDependencies `yaml:"dependencies"`
	Packaging    *ActionPackageYamlPackaging    `yaml:"packaging"`
}

func GetActionPackageYaml(packageYamlPath string) (*ActionPackageYaml, error) {
	var packageYaml *ActionPackageYaml

	rawPackageYaml, err := os.ReadFile(packageYamlPath)
	if err != nil {
		return nil, err
	}

	if err := yaml.Unmarshal(rawPackageYaml, &packageYaml); err != nil {
		return nil, err
	}

	return packageYaml, nil
}
