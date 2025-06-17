import { useState, useEffect } from 'react';
import { Timer } from 'lucide-react';

interface AgentTimerProps {
  startedAt: string;
  completedAt?: string | null;
  className?: string;
  isRunning?: boolean;
}

export function AgentTimer({ startedAt, completedAt, className = '', isRunning = false }: AgentTimerProps) {
  const [elapsedTime, setElapsedTime] = useState<string>('00:00');

  useEffect(() => {
    const startTime = new Date(startedAt).getTime();

    const updateTimer = () => {
      const endTime = completedAt ? new Date(completedAt).getTime() : Date.now();
      const elapsed = Math.max(0, endTime - startTime);

      const minutes = Math.floor(elapsed / (1000 * 60));
      const seconds = Math.floor((elapsed % (1000 * 60)) / 1000);

      const formattedTime = [minutes.toString().padStart(2, '0'), seconds.toString().padStart(2, '0')].join(':');

      setElapsedTime(formattedTime);
    };

    // Update immediately
    updateTimer();

    // If agent is still running, update every second
    if (isRunning && !completedAt) {
      const interval = setInterval(updateTimer, 1000);
      return () => clearInterval(interval);
    }
  }, [startedAt, completedAt, isRunning]);

  return (
    <div className={`flex items-center space-x-1 ${className}`}>
      <Timer className={`h-4 w-4 ${isRunning ? 'text-blue-500' : 'text-gray-400'}`} />
      <span className={`text-sm font-mono ${isRunning ? 'text-blue-600' : 'text-gray-600'}`}>{elapsedTime}</span>
    </div>
  );
}
