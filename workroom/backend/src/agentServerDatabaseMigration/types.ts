type AgentServerUserTable = {
  sub: string;
  user_id: string;
};

export interface AgentServerDatabase {
  user: AgentServerUserTable;
}
