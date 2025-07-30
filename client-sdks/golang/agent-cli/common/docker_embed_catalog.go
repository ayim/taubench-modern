package common

import _ "embed"

//go:embed docker_catalog.yaml
var CatalogYAML []byte
