import { meta, paths, components } from "./index";

// Agent Server meta
const version = meta.version;

// Schema objects
type Agent = components["schemas"]["Agent"];

// Path params
type EndpointParams = paths["/api/v1/agents"]["parameters"];
