module github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli

go 1.23.9

require (
	github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go v0.5.0
	github.com/Sema4AI/rcc v0.0.0-20250514153248-eec1733ee256
	github.com/google/uuid v1.6.0
	github.com/spf13/cobra v1.9.1
	github.com/stretchr/testify v1.10.0
	golang.org/x/mod v0.25.0
	gopkg.in/yaml.v2 v2.4.0
	gopkg.in/yaml.v3 v3.0.1
)

require (
	github.com/davecgh/go-spew v1.1.2-0.20180830191138-d8f796af33cc // indirect
	github.com/dchest/siphash v1.2.3 // indirect
	github.com/inconshreveable/mousetrap v1.1.0 // indirect
	github.com/kr/pretty v0.3.1 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/pmezard/go-difflib v1.0.1-0.20181226105442-5d4384ee4fb2 // indirect
	github.com/spf13/pflag v1.0.6 // indirect
	github.com/ttacon/chalk v0.0.0-20160626202418-22c06c80ed31
	golang.org/x/sys v0.33.0 // indirect
	golang.org/x/term v0.32.0 // indirect
	gopkg.in/check.v1 v1.0.0-20190902080502-41f04d3bba15 // indirect
)

replace github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go => ../agent-client-go
