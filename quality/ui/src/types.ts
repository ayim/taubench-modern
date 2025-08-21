export interface TestStatus {
  run_id: string;
  current_run_dir: string;
  started_at: string;
  completed_at?: string;
  status: 'initializing' | 'running' | 'completed' | 'failed';
  agents: Record<string, AgentStatus>;
  overall_stats: OverallStats;
  error?: string;
}

export interface AgentStatus {
  name: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  total_tests: number;
  completed_tests: number;
  passed_tests: number;
  failed_tests: number;
  current_test?: CurrentTest | null;
  error?: string | null;
  test_results: TestResultGroup[];
}

export interface CurrentTest {
  test_name: string;
  platform: string;
  started_at: string;
  status: 'running';
}

export interface OverallStats {
  total_agents: number;
  completed_agents: number;
  total_tests: number;
  completed_tests: number;
  passed_tests: number;
  failed_tests: number;
  total_trials?: number;
  completed_trials?: number;
}

export interface TestSummary {
  last_run_id: string;
  last_updated: string;
  stats: OverallStats;
  agents: Record<string, AgentSummary>;
}

export interface AgentSummary {
  total_tests: number;
  completed_tests: number;
  passed_tests: number;
  failed_tests: number;
  status: string;
}

export interface TestResultGroup {
  test_name: string;
  platform: string;
  test_case: TestCase;
  trials: TrialResult[];
}
export interface TrialResult {
  trial_id: string;
  agent_name?: string;
  success: boolean;
  started_at?: string;
  completed_at: string;
  error?: string;
  agent_messages: AgentMessage[];
  evaluation_results: EvaluationResult[];
}

export interface TestResult {
  test_name: string;
  platform: string;
  test_case: TestCase;
  agent_name?: string;
  success: boolean;
  started_at?: string;
  completed_at: string;
  error?: string;
  agent_messages: AgentMessage[];
  evaluation_results: EvaluationResult[];
}

export interface TestCase {
  name: string;
  description: string;
  trials: number;
  metrics: Array<{ name: string; k: number }>;
  file_path: string;
  evaluations: Evaluation[];
}

export interface Evaluation {
  kind: string;
  expected: string;
  description: string;
}

export interface AgentMessage {
  role: 'user' | 'agent';
  content: MessageContent[];
}

export interface MessageTextContent {
  text: string;
}

export interface MessageThoughtContent {
  thought: string;
}

export interface MessageContent {
  type: 'text' | 'thought' | 'tool_use' | 'unknown';
  data: MessageTextContent | MessageThoughtContent | ToolUseData;
}

export interface ToolUseData {
  tool_name: string;
  input_as_string: string;
  output_as_string: string;
  started_at: string;
  ended_at: string;
  error?: string | null;
}

export interface EvaluationResult {
  kind: string;
  expected: string;
  passed: boolean;
  actual_value: string;
  error?: string | null;
}

export interface AgentMetadata {
  name: string;
  zip_path: string;
  test_cases: TestCaseMetadata[];
  total_tests: number;
  started_at: string;
}

export interface TestCaseMetadata {
  name: string;
  description: string;
  file_path: string;
  target_platforms: string[];
  evaluations: Evaluation[];
}

export interface Agent {
  name: string;
  zip_path: string;
  path: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface DiscoveredAgents {
  discovered_at: string;
  run_id: string;
  agents: Agent[];
}

export interface ToolDefinition {
  name: string;
  description: string;
  input_schema: object;
}
export interface TraceEnvironment {
  name: string;
  agent_name: string;
  agent_server_version: string;
  platform: string;
}
export interface Trace {
  environment: TraceEnvironment;
  messages: AgentMessage[];
  tools: ToolDefinition[];
}
export interface ReplayResult {
  golden_trace: Trace;
  success: boolean;
  trace?: Trace;
  error?: string;
  completed_at: string;
  started_at: string;
}
