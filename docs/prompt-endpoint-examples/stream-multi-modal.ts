import fs from 'fs';
import process from 'process';
import { applyPatch, Operation } from 'json-joy/esm/json-patch/index.js';
import { findByPointer } from '@jsonjoy.com/json-pointer';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

// --- Argument Parsing with yargs ---
const argv = yargs(hideBin(process.argv))
  .option('text', {
    alias: 't',
    type: 'string',
    description: 'The text prompt to send with the media.',
    demandOption: true,
  })
  .option('image', {
    alias: 'i',
    type: 'string',
    description: 'The path to the image file (mutually exclusive with --audio and --pdf).',
  })
  .option('audio', {
    alias: 'a',
    type: 'string',
    description: 'The path to the audio file (mutually exclusive with --image and --pdf).',
  })
  .option('pdf', {
    alias: 'p',
    type: 'string',
    description: 'The path to the PDF file (mutually exclusive with --image and --audio).',
  })
  .option('url', {
    alias: 'u',
    type: 'string',
    description: 'The base server URL for the prompt endpoint.',
    default: 'http://localhost:8000/api/v2/prompts/stream',
  })
  .option('model', {
    alias: 'm',
    type: 'string',
    description: 'The model name to use.',
    default: 'o4-mini-high',
  })
  .usage('Usage: $0 --text "<prompt>" (--image <path> | --audio <path> | --pdf <path>) [--url <url>] [--model <model>]')
  .check((argv) => {
    const mediaArgs = [argv.image, argv.audio, argv.pdf].filter(Boolean);
    if (mediaArgs.length > 1) {
      throw new Error('Arguments --image, --audio, and --pdf are mutually exclusive.');
    }
    if (mediaArgs.length === 0) {
      throw new Error('Either --image, --audio, or --pdf must be provided.');
    }
    return true;
  })
  .help()
  .alias('help', 'h')
  .parseSync();

// --- Use Parsed Arguments ---
const promptText = argv.text;
const imagePath = argv.image;
const audioPath = argv.audio;
const pdfPath = argv.pdf;
const baseUrl = argv.url;
const modelName = argv.model;

// Construct the final URL with the model query parameter
const serverUrl = new URL(baseUrl);
serverUrl.searchParams.set('model', modelName);
const finalServerUrl = serverUrl.toString();

// --- Prepare Media Content ---
let mediaContent: any;
if (imagePath) {
  // Read and base64 encode the image
  const imageBase64 = fs.readFileSync(imagePath).toString('base64');
  mediaContent = {
    kind: "image",
    value: imageBase64,
    mime_type: "image/jpeg",
    sub_type: "base64",
    detail: "high_res"
  };
  console.log(`Using image: ${imagePath}`);
} else if (audioPath) {
  // Read and base64 encode the audio
  const audioBase64 = fs.readFileSync(audioPath).toString('base64');
  mediaContent = {
    kind: "audio",
    value: audioBase64,
    mime_type: "audio/mp3",
    sub_type: "base64"
  };
  console.log(`Using audio: ${audioPath}`);
} else if (pdfPath) {
  // Read and base64 encode the PDF
  const pdfBase64 = fs.readFileSync(pdfPath).toString('base64');
  mediaContent = {
    kind: "document",
    value: pdfBase64,
    name: "document.pdf",
    mime_type: "application/pdf",
    sub_type: "base64"
  };
  console.log(`Using PDF: ${pdfPath}`);
}

// Create the request payload
const payload = pdfPath ? {
  platform_config_raw: {
    kind: "reducto",
    reducto_api_key: process.env.REDUCTO_API_KEY,
    reducto_api_url: "https://backend.sema4ai.dev/reducto"
  },
  prompt: {
    // Reducto is our only platform handling documents, and
    // it just wants system instructions and a user message
    // with the document to process
    system_instructions: promptText,
    messages: [
      {
        role: "user",
        content: [
          mediaContent
        ]
      }
    ],
    tools: [],
    temperature: 0.0,
    max_output_tokens: 1024
  }
} : {
  platform_config_raw: {
    kind: "openai",
    openai_api_key: process.env.OPENAI_API_KEY
  },
  prompt: {
    messages: [
      {
        role: "user",
        content: [
          { text: promptText },
          mediaContent
        ]
      }
    ],
    tools: [],
    temperature: 0.0,
    max_output_tokens: 1024
  }
};

// Class to handle streaming response processing
class ResponseStreamHandler {
  private currentMessage: any = {};

  handleStreamData(line: string) {
    // Skip empty lines
    if (!line.trim()) return;

    // Handle SSE format - ignore comment lines and extract data
    if (!line.startsWith('data:')) {
      // This is a comment/ping/event line, we can ignore it
      return;
    }
    
    // Handle data lines
    const jsonData = line.substring(5).trim(); // Remove 'data:' prefix
    try {
      let data = JSON.parse(jsonData);
      
      if (data.op === 'concat_string') {
        const { val: oldValue } = findByPointer(data.path, this.currentMessage);
  
        // concatinated value
        const concatinatedVal = (oldValue ?? '') + (data.value as string);
        data = {
          op: 'replace',
          path: data.path, // keep the same path
          value: concatinatedVal,
        };
      }
      
      // Apply the patch
      this.currentMessage = applyPatch(
        this.currentMessage,
        [data as Operation],
        { mutate: false }
      ).doc;
    } catch (error) {
      console.error('Error processing JSON data:', error);
    }
  }

  getMessage() {
    return this.currentMessage;
  }
}

// Send the request and handle streaming response
async function main() {
  let startTime: number = 0; // To store the start time of the request

  // Function to clear console and render current state
  const renderLiveOutput = (message: any, time: number, isFinal: boolean = false) => {
    process.stdout.write('\x1Bc'); // Clears the console (works on most terminals)
    // Or use console.clear(); if preferred and available

    const elapsedTime = ((Date.now() - time) / 1000).toFixed(2);

    if (isFinal) {
      console.log(`Stream finished in ${elapsedTime}s.\n`);
      console.log('Final message:\n');
    } else {
      console.log(`Receiving stream... Time elapsed: ${elapsedTime}s\n`);
      console.log('Current message constructing:\n');
    }
    console.log(JSON.stringify(message, null, 2)); // Pretty print the JSON
  };

  try {
    console.log(`Sending request to: ${finalServerUrl}`);
    startTime = Date.now(); // Start timer right before the fetch call

    const response = await fetch(finalServerUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const streamHandler = new ResponseStreamHandler();
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // Initial render (optional, shows "waiting" state)
    // renderLiveOutput({}, startTime); 

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      
      let newlineIndex;
      while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        
        if (line) {
          streamHandler.handleStreamData(line);
          renderLiveOutput(streamHandler.getMessage(), startTime); // Re-render after each line
        }
      }
    }
    
    if (buffer.trim()) { // Process any remaining data in the buffer
      streamHandler.handleStreamData(buffer.trim());
    }

    // Final render
    renderLiveOutput(streamHandler.getMessage(), startTime, true);

  } catch (error) {
    // Ensure console is usable if an error occurs mid-stream
    process.stdout.write('\x1Bc'); // Clear potentially broken output
    console.error('Error during streaming or processing:', error);
    if (startTime > 0) {
        const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.error(`Operation failed after ${elapsedTime}s`);
    }
  }
}

main();