import { Settings2 } from 'lucide-react';
import { useEffect, useState } from 'react';

interface Settings {
  homeFolder: string;
}

interface SettingsButtonProps {
  isLoading: boolean;
  settings: Settings;
  saveSettings(settings: Settings): void;
}

export function SettingsButton({ isLoading, settings, saveSettings }: SettingsButtonProps) {
  const [open, setOpen] = useState(false);
  const [homeFolder, setHomeFolder] = useState(settings.homeFolder);

  useEffect(() => {
    function onKeyDown(e: { key: string }) {
      if (e.key === 'Escape') setOpen(false);
    }
    if (open) {
      window.addEventListener('keydown', onKeyDown);
      document.body.style.overflow = 'hidden'; // prevent background scroll
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        disabled={isLoading}
        className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Settings2 className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
      </button>
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40 bg-black/50" onClick={() => setOpen(false)} />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
              <h2 className="mb-4 text-xl font-semibold">Settings</h2>

              <label htmlFor="homeFolder" className="mb-1 block text-sm font-medium text-gray-700">
                Home Folder
              </label>
              <input
                id="homeFolder"
                type="text"
                value={homeFolder}
                onChange={(e) => setHomeFolder(e.target.value)}
                className="mb-6 w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. /Users/marco"
              />

              <div className="flex justify-end space-x-2">
                <button
                  className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </button>
                <button
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  onClick={() => {
                    saveSettings({
                      ...settings,
                      homeFolder,
                    });
                    setOpen(false);
                  }}
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
