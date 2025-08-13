/**
 * Test setup file for Vitest
 * Sets up global polyfills and configurations needed for testing
 */

import WebSocket from 'ws';

// Polyfill WebSocket for Node.js environment
global.WebSocket = WebSocket as any;

// Also polyfill for the global scope used by some libraries
(globalThis as any).WebSocket = WebSocket;

// Set up any other global test configurations here if needed
