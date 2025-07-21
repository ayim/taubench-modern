#!/bin/bash

# AGENT > CREATE BASED ON PAYLOAD
./dist/agent-cli agent create --agent-server-url http://127.0.0.1:58885 --path "/Users/user/sema4ai-agents/q3" --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.03.json" --deploy --verbose
./dist/agent-cli agent create --agent-server-url http://127.0.0.1:58885 --path "/Users/user/sema4ai-agents/q3" --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.extra.json" --deploy --verbose

# AGENT > GET
./dist/agent-cli agent get --agent-server-url http://127.0.0.1:58885 --agent-project-settings-path "/Users/user/.sema4ai/sema4ai-studio/agent-project-settings.json" --verbose

# AGENT > DELETE
./dist/agent-cli agent delete --agent-server-url http://127.0.0.1:58885 --agent-id 08d8a272-d59b-4dae-8f32-0c2aad451d96 --verbose

# AGENT > UPDATE
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.06.json" --path "/Users/user/sema4ai-agents/q3" --verbose

# AGENT > UPDATE RAW
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.raw.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.string.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.secret.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.oauth2.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.secret.conv.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.welcome.json" --path "/Users/user/sema4ai-agents/q3" --verbose
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.real.welcome.cg.json" --path "/Users/user/sema4ai-agents/q3" --verbose
# AGENT > UPDATE FULL   
./dist/agent-cli agent update --agent-server-url http://127.0.0.1:58885 --deploy --payloadPath "./tests/fixtures/agent-payloads/mcp.payload.full.json" --path "/Users/user/sema4ai-agents/q3" --verbose

# PROJECT > LIST
./dist/agent-cli project list --agent-server-url http://127.0.0.1:58885 --verbose

# PROJECT > EXPORT
./dist/agent-cli project export --agent-server-url http://127.0.0.1:58885 --agent q3 --verbose --path "/Users/user/sema4ai-agents/export-q3"

# PROJECT > DEPLOY
./dist/agent-cli project deploy --agent-server-url http://127.0.0.1:58885 --path "/Users/user/sema4ai-agents/export-q3" --verbose

# PACKAGE > BUILD
./dist/agent-cli package build --input-dir "/Users/user/sema4ai-agents/export-q3" --output-dir ./dist/ --name export-q3.zip --overwrite --verbose

# PACKAGE > IMPORT
./dist/agent-cli package import --agent-server-url http://127.0.0.1:58885 --package "./dist/export-q3.zip" --verbose

# PACKAGE > EXTRACT
./dist/agent-cli package extract --output-dir "/Users/user/sema4ai-agents/export-q3" --package "./dist/export-q3.zip" --overwrite --verbose

# VALIDATE
./dist/agent-cli validate "/Users/user/sema4ai-agents/export-q3" --json --ignore-actions

# PACKAGE > METADATA
./dist/agent-cli package metadata --output-file ./tests/out/test_meta.json --package ./tests/fixtures/agent-packages/a-1.v3.zip --verbose
./dist/agent-cli package metadata --output-file ./tests/out/test_meta.json --package ./tests/fixtures/agent-packages/a-1.v3.cg.zip --verbose
./dist/agent-cli package metadata --output-file ./tests/out/test_meta.json --package ./tests/fixtures/agent-packages/a-1.v3.cg.wm.zip --verbose
