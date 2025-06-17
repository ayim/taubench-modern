import { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

interface RunTimerProps {
  startedAt: string | null; // ISO timestamp when run started
  completedAt?: string | null; // ISO timestamp when run completed (optional)
  className?: string;
}

export function RunTimer({ startedAt, completedAt, className = '' }: RunTimerProps) {
  const [elapsedTime, setElapsedTime] = useState<string>('00:00:00');

  useEffect(() => {
    if (!startedAt) {
      setElapsedTime('--:--:--');
      return;
    }

    const startTime = new Date(startedAt).getTime();

    const updateTimer = () => {
      const endTime = completedAt ? new Date(completedAt).getTime() : Date.now();
      const elapsed = Math.max(0, endTime - startTime);

      const hours = Math.floor(elapsed / (1000 * 60 * 60));
      const minutes = Math.floor((elapsed % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((elapsed % (1000 * 60)) / 1000);

      const formattedTime = [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        seconds.toString().padStart(2, '0'),
      ].join(':');

      setElapsedTime(formattedTime);
    };

    // Update immediately
    updateTimer();

    // If run is not completed, update every second
    if (!completedAt) {
      const interval = setInterval(updateTimer, 1000);
      return () => clearInterval(interval);
    }
  }, [startedAt, completedAt]);

  if (!startedAt) {
    return null;
  }

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <Clock className="h-5 w-5 text-gray-500" />
      <div className="text-sm text-gray-600">
        <span className="font-medium">Runtime:</span>
        <span className="ml-1 font-mono text-lg font-semibold text-gray-900">{elapsedTime}</span>
      </div>
    </div>
  );
}
