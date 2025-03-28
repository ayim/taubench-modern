import { paths, components } from "./index";

// Schema objects
type Agent = components["schemas"]["Agent"];

// Path params
type EndpointParams = paths["/api/v1/agents"]["parameters"];
