import { Agent } from '../types';
import { CheckCircle, XCircle, Clock, Loader2, User } from 'lucide-react';

interface AgentsListProps {
  agents: Agent[];
  selectedAgent: string | null;
  onAgentSelect: (agentName: string | null) => void;
}

export function AgentsList({ agents, selectedAgent, onAgentSelect }: AgentsListProps) {
  const getStatusIcon = (status: Agent['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'pending':
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'failed':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'running':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'pending':
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  if (agents.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
        <User className="h-8 w-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No agents discovered yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Agents</h3>
          {selectedAgent && (
            <button onClick={() => onAgentSelect(null)} className="text-sm text-blue-600 hover:text-blue-800">
              Show All
            </button>
          )}
        </div>
        <p className="text-sm text-gray-600 mt-1">
          Click an agent to filter test results. {agents.length} agent{agents.length !== 1 ? 's' : ''} discovered.
        </p>
      </div>

      <div className="divide-y divide-gray-200">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
              selectedAgent === agent.name ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
            }`}
            onClick={() => onAgentSelect(selectedAgent === agent.name ? null : agent.name)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getStatusIcon(agent.status)}
                <div>
                  <h4 className="font-medium text-gray-900">{agent.name}</h4>
                  {agent.zip_path && <p className="text-xs text-gray-500 mt-1">{agent.zip_path.split('/').pop()}</p>}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(
                    agent.status,
                  )}`}
                >
                  {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                </span>
                {selectedAgent === agent.name && <div className="text-xs text-blue-600 font-medium">Filtered</div>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
