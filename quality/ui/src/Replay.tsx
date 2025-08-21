import { AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { SettingsButton } from './components/SettingsButton';
import { TraceDisplay } from './components/TraceDisplay';
import { useReplayResults } from './hooks/useReplayResults';
import { useParams } from 'react-router-dom';
import { ReplayResult } from './types';

function Replay() {
  const [settings, setSettings] = useState({
    homeFolder: '~/.sema4x/quality',
  });
  const { runId } = useParams();
  const { fetchReplayRun } = useReplayResults(settings);
  const [result, setResult] = useState<ReplayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchReplayRun(runId);
        if (!cancelled) setResult(data);
        if (!cancelled && !data) setError('Run not found');
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, fetchReplayRun]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading test results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Results</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => alert('TODO')}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Results</h2>
          <p className="text-gray-600 mb-4">Cannot find replay {runId}</p>
        </div>
      </div>
    );
  }

  const getStatusIcon = () => {
    switch (result?.success) {
      case true:
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case false:
        return <XCircle className="h-6 w-6 text-red-500" />;
      default:
        return <Clock className="h-6 w-6 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (result?.success) {
      case true:
        return 'Trace replayed successfully';
      case false:
        return 'Cannot replay trace';
      default:
        return 'Status Unknown';
    }
  };

  const getStatusColor = () => {
    switch (result?.success) {
      case true:
        return 'text-green-600';
      case false:
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {getStatusIcon()}
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Regression Testing Dashboard</h1>
                <p className={`text-lg ${getStatusColor()}`}>{getStatusText()}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <SettingsButton isLoading={loading} settings={settings} saveSettings={setSettings} />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Replay Diffs</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
            <div className={'ring-2 ring-amber-400/80 bg-amber-50/60'}>
              <TraceDisplay trace={result.golden_trace} />
            </div>
            <div>
              {result.trace && <TraceDisplay trace={result.trace} />}
              {result.error && (
                <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded">
                  <h5 className="text-sm font-medium text-red-800 mb-1">Error</h5>
                  <p className="text-sm text-red-700">{result.error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Replay;
