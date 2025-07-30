package common

// DockerCatalog represents the structure of catalog.yaml
type DockerCatalog struct {
	Version                      int                          `yaml:"version" json:"version"`
	Name                         string                       `yaml:"name" json:"name"`
	DisplayName                  string                       `yaml:"displayName" json:"display_name"`
	Registry                     DockerCatalogRegistryEntries `yaml:"registry" json:"registry"`
	Sema4DockerCompatibleVersion string                       `yaml:"sema4DockerCompatibleVersion" json:"sema4_docker_compatible_version"`
	Sema4DockerCompatibleBuild   string                       `yaml:"sema4DockerCompatibleBuild" json:"sema4_docker_compatible_build"`
}

type DockerCatalogRegistryEntries = map[string]DockerCatalogRegistry

type DockerCatalogRegistry struct {
	Description string                `yaml:"description" json:"description"`
	Title       string                `yaml:"title" json:"title"`
	Type        string                `yaml:"type" json:"type"`
	DateAdded   string                `yaml:"dateAdded" json:"date_added"`
	Image       string                `yaml:"image" json:"image"`
	Ref         string                `yaml:"ref" json:"ref"`
	Readme      string                `yaml:"readme" json:"readme"`
	ToolsUrl    string                `yaml:"toolsUrl" json:"tools_url"`
	Source      string                `yaml:"source" json:"source"`
	Upstream    string                `yaml:"upstream" json:"upstream"`
	Icon        string                `yaml:"icon" json:"icon"`
	Tools       []DockerCatalogTool   `yaml:"tools" json:"tools"`
	Secrets     []DockerCatalogSecret `yaml:"secrets,omitempty" json:"secrets,omitempty"`
	Env         []DockerCatalogEnv    `yaml:"env,omitempty" json:"env,omitempty"`
	Command     []string              `yaml:"command,omitempty" json:"command,omitempty"`
	AllowHosts  []string              `yaml:"allowHosts,omitempty" json:"allow_hosts,omitempty"`
	Prompts     int                   `yaml:"prompts,omitempty" json:"prompts,omitempty"`
	// Resources   map[interface{}]interface{} `yaml:"resources,omitempty" json:"resources,omitempty"`
	Config   []DockerCatalogConfig  `yaml:"config,omitempty" json:"config,omitempty"`
	Metadata *DockerCatalogMetadata `yaml:"metadata,omitempty" json:"metadata,omitempty"`
	Oauth    *DockerCatalogOauth    `yaml:"oauth,omitempty" json:"oauth,omitempty"`
	Volumes  []string               `yaml:"volumes,omitempty" json:"volumes,omitempty"`
}

type DockerCatalogTool struct {
	Name        string `yaml:"name" json:"name"`
	Description string `yaml:"description,omitempty" json:"description,omitempty"`
	// Parameters  map[string]interface{}      `yaml:"parameters,omitempty" json:"parameters,omitempty"`
	// Container   map[string]interface{}      `yaml:"container,omitempty" json:"container,omitempty"`
	Config  []DockerCatalogConfig `yaml:"config,omitempty" json:"config,omitempty"`
	Volumes []string              `yaml:"volumes,omitempty" json:"volumes,omitempty"`
	Command []string              `yaml:"command,omitempty" json:"command,omitempty"`
	// Resources   map[interface{}]interface{} `yaml:"resources,omitempty" json:"resources,omitempty"`
	Env      []DockerCatalogEnv     `yaml:"env,omitempty" json:"env,omitempty"`
	Secrets  []DockerCatalogSecret  `yaml:"secrets,omitempty" json:"secrets,omitempty"`
	Metadata *DockerCatalogMetadata `yaml:"metadata,omitempty" json:"metadata,omitempty"`
}

type DockerCatalogSecret struct {
	Name    string `yaml:"name" json:"name"`
	Env     string `yaml:"env" json:"env"`
	Example string `yaml:"example,omitempty" json:"example,omitempty"`
}

type DockerCatalogEnv struct {
	Name  string `yaml:"name" json:"name"`
	Value string `yaml:"value" json:"value"`
}

type DockerCatalogConfig struct {
	Name        string `yaml:"name" json:"name"`
	Description string `yaml:"description,omitempty" json:"description,omitempty"`
	Type        string `yaml:"type,omitempty" json:"type,omitempty"`
	// Properties  map[string]interface{} `yaml:"properties,omitempty" json:"properties,omitempty"`
	Required []string              `yaml:"required,omitempty" json:"required,omitempty"`
	AnyOf    []map[string][]string `yaml:"anyOf,omitempty" json:"any_of,omitempty"`
}

type DockerCatalogMetadata struct {
	Pulls       int      `yaml:"pulls,omitempty" json:"pulls,omitempty"`
	Stars       int      `yaml:"stars,omitempty" json:"stars,omitempty"`
	GithubStars int      `yaml:"githubStars,omitempty" json:"github_stars,omitempty"`
	Category    string   `yaml:"category,omitempty" json:"category,omitempty"`
	Tags        []string `yaml:"tags,omitempty" json:"tags,omitempty"`
	License     string   `yaml:"license,omitempty" json:"license,omitempty"`
	Owner       string   `yaml:"owner,omitempty" json:"owner,omitempty"`
}

type DockerCatalogOauth struct {
	Providers []DockerCatalogOauthProvider `yaml:"providers,omitempty" json:"providers,omitempty"`
}

type DockerCatalogOauthProvider struct {
	Provider string `yaml:"provider" json:"provider"`
	Secret   string `yaml:"secret" json:"secret"`
	Env      string `yaml:"env" json:"env"`
}
