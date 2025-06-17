import { useState, useEffect } from 'react';
import { Timer } from 'lucide-react';

interface TestTimerProps {
  startedAt?: string | null;
  completedAt: string;
  className?: string;
  showIcon?: boolean;
}

export function TestTimer({ startedAt, completedAt, className = '', showIcon = true }: TestTimerProps) {
  const [elapsedTime, setElapsedTime] = useState<string>('--:--');

  useEffect(() => {
    if (!startedAt) {
      setElapsedTime('--:--');
      return;
    }

    const startTime = new Date(startedAt).getTime();
    const endTime = new Date(completedAt).getTime();
    const elapsed = Math.max(0, endTime - startTime);

    const minutes = Math.floor(elapsed / (1000 * 60));
    const seconds = Math.floor((elapsed % (1000 * 60)) / 1000);

    const formattedTime = [minutes.toString().padStart(2, '0'), seconds.toString().padStart(2, '0')].join(':');

    setElapsedTime(formattedTime);
  }, [startedAt, completedAt]);

  if (!startedAt) {
    return null;
  }

  return (
    <div className={`flex items-center space-x-1 ${className}`}>
      {showIcon && <Timer className="h-3 w-3 text-gray-400" />}
      <span className="text-xs text-gray-500 font-mono">{elapsedTime}</span>
    </div>
  );
}
