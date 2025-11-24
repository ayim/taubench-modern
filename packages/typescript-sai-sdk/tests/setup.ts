/**
 * Test setup file for Vitest
 * Sets up global polyfills and configurations needed for testing
 */

import { afterAll } from 'vitest';
import WebSocket from 'ws';

// Polyfill WebSocket for Node.js environment
global.WebSocket = WebSocket as any;

// Also polyfill for the global scope used by some libraries
(globalThis as any).WebSocket = WebSocket;

// Cleanup after all tests to prevent stack overflow in tinypool
afterAll(() => {
  // Give time for any pending WebSocket connections to close
  return new Promise<void>((resolve) => {
    setTimeout(() => {
      resolve();
    }, 100);
  });
});

// Set up any other global test configurations here if needed
