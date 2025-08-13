export const logger = {
  info: (message: string, ...args: any[]) => {
    console.log(`[SaiSDK] ${message}`, ...args);
  },
  infoIf: (condition: boolean | undefined, message: string, ...args: any[]) => {
    if (condition) {
      console.log(`[SaiSDK] ${message}`, ...args);
    }
  },
  warn: (message: string, ...args: any[]) => {
    console.warn(`[SaiSDK] ${message}`, ...args);
  },
  warnIf: (condition: boolean | undefined, message: string, ...args: any[]) => {
    if (condition) {
      console.warn(`[SaiSDK] ${message}`, ...args);
    }
  },
  debug: (message: string, ...args: any[]) => {
    console.debug(`[SaiSDK] ${message}`, ...args);
  },
  debugIf: (condition: boolean | undefined, message: string, ...args: any[]) => {
    if (condition) {
      console.debug(`[SaiSDK] ${message}`, ...args);
    }
  },
  error: (message: string, ...args: any[]) => {
    console.error(`[SaiSDK] ${message}`, ...args);
  },
  errorIf: (condition: boolean | undefined, message: string, ...args: any[]) => {
    if (condition) {
      console.error(`[SaiSDK] ${message}`, ...args);
    }
  },
};
