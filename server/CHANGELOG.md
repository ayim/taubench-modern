# Sema4.ai Agent Server 2.1.8 (2025-09-29)

- [tiny] Makefile fix for observability (#1116)
- [GPT-1344] Use spar instead of spar-no-auth compose profile in GH Workflow (#1118)
- GPT-1336 Address concurrency issues with sqlite  (#1117)
- [GPT-1343] More Tuning of Exp Arch (#1108)
- Read evals parameters from env vars and tune values (#1099)
- Submit feedback and copy feature (#1092)
- Terminate and fail evals if cannot gather tools (#1101)
- feat: Add disabled state to ConversationGuideCard and integrate strea… (#1103)
- Improve Sidepanel navigation buttons behaviour (#1096)
- feat(spar-files): AWS File management support in SPAR (#1084)
- Adding tooltip to thread and workitem list items (#1097)
- CLOUD-5224: Add the ability to delete OAuth connection (#1100)
- feat: (@sema4ai/spar-ui@0.0.28) evaluations UI updates and code refactor (#1059)
- Feat: Semantic Data UI (#1094)
- API to list semantic data models "globally" (#1086)
- Feat: Work Item Name on UI (#1081)
- fix(spar-sessions): Fix session handling for OIDC auth mode (#1093)
- [GPT-1293] Fix `delete_agent` in Postgres (#1045)
- [GPT-1298] Modify `delete_thread` in SQLite (#1050)
- [GPT-1291] Modify `patch_agent` implementation (#1049)
- Fix Local VCR Playback (w/ Parallel Pytest) for Bedrock (#1073)
- Sai SDK improvements (#1085)
- CLOUD-5278: Reversed order of threads (#1079)
- feat: surface actionServerRunId in openActionLogs and hide logs for generic mcp servers (#1068)
- GPT-1273 cancel scenario runs (#1035)
- [GPT-1292] Fix `upsert_thread` user checking issue (#1046)

# Sema4.ai Agent Server 2.1.7 (2025-09-24)

- [GPT-1302] Replay only `action-external` and `mcp-external` tools [#1070](https://github.com/Sema4AI/agent-platform/pull/1070)
- [Data Frames] Associate a semantic data model to an agent or thread [#1061](https://github.com/Sema4AI/agent-platform/pull/1061)
- Generate OpenAPI without starting the server [#1067](https://github.com/Sema4AI/agent-platform/pull/1067)
- Ignore extra kwargs in Agent and Thread model validation [#1064](https://github.com/Sema4AI/agent-platform/pull/1064)
- [GPT-1274] Store `models`, `architecture` and `runbook` in run metadata [#1032](https://github.com/Sema4AI/agent-platform/pull/1032)
- [Data Frames] APIs to generate a semantic data model from a data connection inspection or a file inspection [#1033](https://github.com/Sema4AI/agent-platform/pull/1033)
- [GPT-1285] Use PromptDocumentContent via prompts/generate [#1004](https://github.com/Sema4AI/agent-platform/pull/1004)
- Fix missing fields when getting a single scenario run [#1040](https://github.com/Sema4AI/agent-platform/pull/1040)
- Prevent Bedrock VCR playback from writing new cassettes [#1047](https://github.com/Sema4AI/agent-platform/pull/1047)
- Small agent architecture tweaks [#1052](https://github.com/Sema4AI/agent-platform/pull/1052)

# Sema4.ai Agent Server 2.1.6 (2025-09-23)

- [PRD-892] Add optional user-friendly work_item_name to work_item [#1024](https://github.com/Sema4AI/agent-platform/pull/1024)
- [GPT-1284] mismatch agent tools vs conversation error [#1016](https://github.com/Sema4AI/agent-platform/pull/1016)
- Ensure that initial thread message AND conversation starters works fo… [#1037](https://github.com/Sema4AI/agent-platform/pull/1037)
- Add remote run id in the response from the action server [#1014](https://github.com/Sema4AI/agent-platform/pull/1014)
- [GPT-1248] Improve error management in scenario runs [#963](https://github.com/Sema4AI/agent-platform/pull/963)
- Fix user scoping for OIDC auth [#1027](https://github.com/Sema4AI/agent-platform/pull/1027)
- Increase memory allocation for SPAR on ECS/Fargate [#1029](https://github.com/Sema4AI/agent-platform/pull/1029)
- [Cloud-5293]: BUG: the Agent list briefly shows "no agents yet" even if there are agents [#1028](https://github.com/Sema4AI/agent-platform/pull/1028)

# Sema4.ai Agent Server 2.1.5 (2025-09-22)

- [GPT-1287] Lock new models to the new architecture; improve backward compatibility [#1019](https://github.com/Sema4AI/agent-platform/pull/1019)
- Add APIs to extract tables, columns, and sample data from data connections (via Ibis) [#1006](https://github.com/Sema4AI/agent-platform/pull/1006)
- Skip frequently failing `test_evals_e2e` [#1020](https://github.com/Sema4AI/agent-platform/pull/1020)
- GPT-1282: Increase timeouts for evals integration tests [#1013](https://github.com/Sema4AI/agent-platform/pull/1013)

# Sema4.ai Agent Server 2.1.4 (2025-09-22)

- Graceful shutdown of work items with health endpoints [#940](https://github.com/Sema4AI/agent-platform/pull/940)
- Add created_at and updated_at ts for data connection payload [#996](https://github.com/Sema4AI/agent-platform/pull/996)
- [GPT-1266] Implement whitelisting of tools for MCP Servers [#943](https://github.com/Sema4AI/agent-platform/pull/943)
- Data Frames are now opt-out (disabled with `agent_settings.enable_data_frames` as False or `SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES` env var as `0`/`false`). [#1005](https://github.com/Sema4AI/agent-platform/pull/1005)
- [Data Frames] Provide CRUD APIs for creating semantic data models. [#968](https://github.com/Sema4AI/agent-platform/pull/968)
- [Data Frames] Improve data frames tool description. [#991](https://github.com/Sema4AI/agent-platform/pull/991)

# Sema4.ai Agent Server 2.1.3 (2025-09-18)

- [GPT-1276] Studio Failing on 5+ minute Action Invocations (Turn Async Actions Default ON) [#980](https://github.com/Sema4AI/agent-platform/pull/980)
- [DIN-578] Make generate_citations optional on /extract [#981](https://github.com/Sema4AI/agent-platform/pull/981)
- [DIN-566] Endpoint for generating a description for a data model [#950](https://github.com/Sema4AI/agent-platform/pull/950)

# Sema4.ai Agent Server 2.1.2 (2025-09-18)

- [PRD-857] Claude 4 Thinking [#951](https://github.com/Sema4AI/agent-platform/pull/951)
- [GPT-1261] Allow list and create work-items endpoints w/o trailing slashes [#929](https://github.com/Sema4AI/agent-platform/pull/929)
- [DIN-510] trim the citation docs in openapi [#952](https://github.com/Sema4AI/agent-platform/pull/952)
- Provide citations with extract results [#905](https://github.com/Sema4AI/agent-platform/pull/905)
- feat: integrate evaluations [#877](https://github.com/Sema4AI/agent-platform/pull/877)
- Spec for semantic data model, CRUD to associate data connections to an agent [#936](https://github.com/Sema4AI/agent-platform/pull/936)
- [GPT-1260] bump timeout for integration tests [#935)](https://github.com/Sema4AI/agent-platform/pull/935)

# Sema4.ai Agent Server 2.1.1 (2025-09-16)

- [GPT-1238] [GPT-1236] Propagate and modify user-facing errors [#886](https://github.com/Sema4AI/agent-platform/pull/886)
- Sai SDK Improvements [#937](https://github.com/Sema4AI/agent-platform/pull/937)
- Bumped turbo version [#934](https://github.com/Sema4AI/agent-platform/pull/934)
- GPT-1241 autofill scenario description [#924](https://github.com/Sema4AI/agent-platform/pull/924)
- Fix delete scenario [#907](https://github.com/Sema4AI/agent-platform/pull/907)
- [GPT-1264] Handle Bedrock seed validation error [#930](https://github.com/Sema4AI/agent-platform/pull/930)
- Fix tests that fail when SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE is … [#931](https://github.com/Sema4AI/agent-platform/pull/931)
- [PRD-854] Update Exp Arch from Benchmarking [#928](https://github.com/Sema4AI/agent-platform/pull/928)
- GPT-1253 Overwrite the user_id for files attached to Threads created by a work-item [#921](https://github.com/Sema4AI/agent-platform/pull/921)
- GPT-1260 Skip frequently failing test_evals_e2e test [#927](https://github.com/Sema4AI/agent-platform/pull/927)
- Create CRUD endpoints for Data Connections [#896](https://github.com/Sema4AI/agent-platform/pull/896)
- [PRD-856] Response Based Clients for (Azure)OpenAI + GPT-5 [#902](https://github.com/Sema4AI/agent-platform/pull/902)
- GPT-1247 Handle unknown fields in ThreadThoughtContent [#904](https://github.com/Sema4AI/agent-platform/pull/904)
- Spar UI: Shared queries [#913](https://github.com/Sema4AI/agent-platform/pull/913)
- chore: SPAR Dockerization improvements [#912](https://github.com/Sema4AI/agent-platform/pull/912)
- Configuration Tab & Sidebar links tweaks [#910](https://github.com/Sema4AI/agent-platform/pull/910)
- GPT-1212 Remove chatty logs for work-items [#922](https://github.com/Sema4AI/agent-platform/pull/922)
- GPT-1249 Never change user_id on Thread update. [#919](https://github.com/Sema4AI/agent-platform/pull/919)
- Make platform_id required [#914](https://github.com/Sema4AI/agent-platform/pull/914)
- Spar UI: Work Item related UI updates [#909](https://github.com/Sema4AI/agent-platform/pull/909)
- CLOUD-5236: Fix the recommended LLM that was broken after the redesign [#885](https://github.com/Sema4AI/agent-platform/pull/885)
- Different fixes related to threads [#906](https://github.com/Sema4AI/agent-platform/pull/906)
- GPT-1240 conversation flow adherence and result accuracy [#894](https://github.com/Sema4AI/agent-platform/pull/894)
- CLOUD-5238 chore: replace SPAR with Teams edition [#898](https://github.com/Sema4AI/agent-platform/pull/898)
- [PRD-878] GPT-5 Prepwork [#865](https://github.com/Sema4AI/agent-platform/pull/865)
- fix: agents settings permissions [#895](https://github.com/Sema4AI/agent-platform/pull/895)
- GPT-1217 evals background job [#871](https://github.com/Sema4AI/agent-platform/pull/871)
- CLOUD-5242: Use the platform ID when selecting a configured LLM [#881](https://github.com/Sema4AI/agent-platform/pull/881)
- ci/fix: Remove problematic npm caching [#893](https://github.com/Sema4AI/agent-platform/pull/893)
- fix: SPAR illustrations relative lookup [#892](https://github.com/Sema4AI/agent-platform/pull/892)
- [Data Frames] Improve error message to show sheet names on multi sheet case. [#887](https://github.com/Sema4AI/agent-platform/pull/887)
- CLOUD-5226: Re-implement agent deletion [#874](https://github.com/Sema4AI/agent-platform/pull/874)
- Spar UI: Work items views refactor [#880](https://github.com/Sema4AI/agent-platform/pull/880)
- Use the in-memory transport mode for AgentServeClientDependency in DIv2 endpoints ( DIN-387 DIN-448 ) [#772](https://github.com/Sema4AI/agent-platform/pull/772)
- ci/fix: Run ASI publish on merge to maintenance branch, too [#884](https://github.com/Sema4AI/agent-platform/pull/884)
- Fix QuickOption Causing UI failures sometimes [#855](https://github.com/Sema4AI/agent-platform/pull/855)
- ci: Add `base_branch` input to ASI PR workflow [#882](https://github.com/Sema4AI/agent-platform/pull/882)
- feat: add spar-ui CreateEvalDialog and EvalSidebarView [#878](https://github.com/Sema4AI/agent-platform/pull/878)
- Implement the tab view MCPs and LLMs as per the design [#866](https://github.com/Sema4AI/agent-platform/pull/866)
- chore: Slim down SPAR image by ~50% [#876](https://github.com/Sema4AI/agent-platform/pull/876)
- fix: preserve query params when redirecting oauth [#879](https://github.com/Sema4AI/agent-platform/pull/879)
- Add x-action-invocation-header when making a call to the action server as MCP Server [#860](https://github.com/Sema4AI/agent-platform/pull/860)
- fix: oauth redirect [#873](https://github.com/Sema4AI/agent-platform/pull/873)
- CLOUD-5212 GPT-1200: Introduce platform params and create a link table with agents table [#831](https://github.com/Sema4AI/agent-platform/pull/831)
- CLOUD-5229: Data Frame vega-lite to show charts [#861](https://github.com/Sema4AI/agent-platform/pull/861)
- Spar UI: Minor Ui fixes [#868](https://github.com/Sema4AI/agent-platform/pull/868)
- [Data Frames] Create GET API to get data frame data from `threads/{tid}/data-frames/{data_frame_name}` to use in vega-lite charts [#842](https://github.com/Sema4AI/agent-platform/pull/842)
- Implement Work Item creation Dialog [#867](https://github.com/Sema4AI/agent-platform/pull/867)
- CLOUD-5231: Rename Create Agent to Deploy Agent [#869](https://github.com/Sema4AI/agent-platform/pull/869)
- ci: Add helpful error message on SPAR build fail [#870](https://github.com/Sema4AI/agent-platform/pull/870)
- Converting `copy-legacy-types` command to script [#856](https://github.com/Sema4AI/agent-platform/pull/856)
- GPT-1195: Persist DIDS data connections to database [#839](https://github.com/Sema4AI/agent-platform/pull/839)
- [DIN-478] Fail fast if description and limit are provided while generating quality checks [#848](https://github.com/Sema4AI/agent-platform/pull/848)
- Improve the tools description to specify what's actually a valid data frame name and try to auto-fix [#841](https://github.com/Sema4AI/agent-platform/pull/841)
- Docker vulnerabilities fix - Smaller image [#858](https://github.com/Sema4AI/agent-platform/pull/858)
- GPT-1214 Eval API: scenario CRUD operations [#796](https://github.com/Sema4AI/agent-platform/pull/796)
- CLOUD-5218: part 2 - Data Frame client tools [#844](https://github.com/Sema4AI/agent-platform/pull/844)
- Spar: Initial sidebar implementation [#859](https://github.com/Sema4AI/agent-platform/pull/859)
- chore: keep incomplete WebSocket messages until completed  [#857](https://github.com/Sema4AI/agent-platform/pull/857)
- Spar: Added missing base [#853](https://github.com/Sema4AI/agent-platform/pull/853)
- fix: add missing SPAR features env variables [#852](https://github.com/Sema4AI/agent-platform/pull/852)
- GPT-1232: Explicitly select thread columns instead of t.* [#850](https://github.com/Sema4AI/agent-platform/pull/850)
- chore: enable data frames for spar [#814](https://github.com/Sema4AI/agent-platform/pull/814)
- [DIN-403] Split up DIv2 REST endpoints into different files [#805](https://github.com/Sema4AI/agent-platform/pull/805)
- Workroom v2 [#634](https://github.com/Sema4AI/agent-platform/pull/634)
- feat(agent-server-interface): Keep spec up to date [#786](https://github.com/Sema4AI/agent-platform/pull/786)
- CLOUD-5220: fix - do not surface DELETE agents in Work Room (ACE / SPCS) [#847](https://github.com/Sema4AI/agent-platform/pull/847)

# Sema4.ai Agent Server 2.1.0 (2025-09-08)

- Bump version number to v2.1.x with v2.0.x being maintained in agent-server-2.0.x branch for ACE and Studio v1.5.x
- No other changes compared to v2.0.42

# Sema4.ai Agent Server 2.0.42 (2025-09-05)

- Fix: Add missing type in MCPServerResponse [#832](https://github.com/Sema4AI/agent-platform/pull/832)
- Bump sema4ai-docint to 0.4.12 [#837](https://github.com/Sema4AI/agent-platform/pull/837)

# Sema4.ai Agent Server 2.0.41 (2025-09-04)

- [Data Frames] Don't remove tools after they were added into the context [#808](https://github.com/Sema4AI/agent-platform/pull/808)
- [GPT-1197] Use sema4ai-http-helper while exporting traces to LS [#799](https://github.com/Sema4AI/agent-platform/pull/799)
- Add x-data-context header to action servers (as mcp) [#810](https://github.com/Sema4AI/agent-platform/pull/810)
- Reduce code duplication in test_tools_interface. [#817](https://github.com/Sema4AI/agent-platform/pull/817)
- GPT-1175: Add work_item_id field to Thread [#816](https://github.com/Sema4AI/agent-platform/pull/816)
- GPT-1188: Include usage tokens in the thread message [#818](https://github.com/Sema4AI/agent-platform/pull/818)
- Improve Document Layout Payload handling and Extraction Schema Generation [#824](https://github.com/Sema4AI/agent-platform/pull/824)
- Automatically create a data frame when a tool returns something with a table shape. [#828](https://github.com/Sema4AI/agent-platform/pull/828)

# Sema4.ai Agent Server 2.0.40 (2025-09-02)

- [Data Frames] Fix TypeError: can only concatenate list (not tuple) to list [#806](https://github.com/Sema4AI/agent-platform/pull/806)
- [Data Frames] Improve SQL handling (accept CTEs, union, ...) [#794](https://github.com/Sema4AI/agent-platform/pull/794)
- [Data Frames] Fix issue collecting dates, use proper API to get sample data, support open office sheets. [#790](https://github.com/Sema4AI/agent-platform/pull/790)
- [DIN-461] Use snake_case instead of camelCase for data models [#798](https://github.com/Sema4AI/agent-platform/pull/798)
- Create an integration test to test the generate layout flow via SPAR [#795](https://github.com/Sema4AI/agent-platform/pull/795)
- GPT-1115: Unnest MCP Server config from agent table [#740](https://github.com/Sema4AI/agent-platform/pull/740)
- Manage secrets in MCP Server. Send relevant headers in x-action-context  [#803](https://github.com/Sema4AI/agent-platform/pull/803)

# Sema4.ai Agent Server 2.0.39 (2025-08-28)

- DIN-454 Drop the DocumentLayoutBridge and unify document layout payloads between endpoints [#781](https://github.com/Sema4AI/agent-platform/pull/781)
- Allow redirects to support MCP endpoints [#791](https://github.com/Sema4AI/agent-platform/pull/791)
- Implement `/documents/generate-schema` to provide an extraction schema for use extracting transiently [#780](https://github.com/Sema4AI/agent-platform/pull/780)

# Sema4.ai Agent Server 2.0.38 (2025-08-27)

- DIN-451 Update `generate_quality_checks` endpoint to fail on empty views array (#779)
- GPT-1176 Automatically push workitem `payload` into thread if given (#777)
- DEV-2177: Extend metrics endpoint with granular telemetry data (#758)
- CON-1350: Data Frames sidebar in workroom (#662)
- GPT-1193 Truncation Overhaul (#747)
- feat: doc intel UI configuration (#751)
- feat(workroom-selector): Handle new tenant workspace url (#755)
- Regression harness: multi turn conversations (#727)

# Sema4.ai Agent Server 2.0.37 (2025-08-25)

- [DIN-447] Use DI Service to create a data model (#748)
- Update parse and extract to use async client; add job flow endpoints (#705)
- [DataFrames] Provide more information for the UI (#746)
- Use `agent_settings.enable_data_frames` for feature flag to enable data frames for specific agents (#726)
- Skip the undecryptable rows and list the decryptable ones with error message (#695)
- Doc intel configuration view (#735)
- feat(tools): Enhance Tool functionality with ToolCategory type (#743)
- [DIN-337] Add ingest endpoint (#738)

# Sema4.ai Agent Server 2.0.36 (2025-08-22)

- fix: Handle PlatformHTTPError in upsert_layout function [#734](https://github.com/Sema4AI/agent-platform/pull/734)
- DIN-430 Fix validation when upserting DocumentLayouts [#733](https://github.com/Sema4AI/agent-platform/pull/733)

# Sema4.ai Agent Server 2.0.35 (2025-08-22)

- Create builtin tools for data frames. [#706](https://github.com/Sema4AI/agent-platform/pull/706)
- Add check to `DocIntDatasourceDependency` to check we can connect before returning [#693](https://github.com/Sema4AI/agent-platform/pull/693)
- GPT-1174 add REST API to interact with DataSources [#707](https://github.com/Sema4AI/agent-platform/pull/707)
- Fix: Main branch has a failing unit test [#719](https://github.com/Sema4AI/agent-platform/pull/719)
- Simen/spar-ui-dynamic-llm [#666](https://github.com/Sema4AI/agent-platform/pull/666)
- data-frames/slice is now a POST (as we want to have json in the body, which is not good for a GET). [#717](https://github.com/Sema4AI/agent-platform/pull/717)
- Create builtin tools for data frames. [#706](https://github.com/Sema4AI/agent-platform/pull/706)
- GPT-1174 add REST API to interact with DataSources [#707](https://github.com/Sema4AI/agent-platform/pull/707)
- Make MCP Client More Robust to Transient Errors [#675](https://github.com/Sema4AI/agent-platform/pull/675)
- GPT-1143: Setup tool_use for MCP to fix no View logs issue [#700](https://github.com/Sema4AI/agent-platform/pull/700)

# Sema4.ai Agent Server 2.0.34 (2025-08-21)

- Fix regression in QuotasService [#713](https://github.com/Sema4AI/agent-platform/pull/713)
- [DIN-338] Generate and execute data quality checks [#694](https://github.com/Sema4AI/agent-platform/pull/694)

# Sema4.ai Agent Server 2.0.33 (2025-08-20)

- DIN-418 Use reducto types in our openapi (#708)
- Support Reasoning Throughout our Stack (#704)

# Sema4.ai Agent Server 2.0.32 (2025-08-20)

- GPT-1174 Separate DataServer configuration from DocInt [#683](https://github.com/Sema4AI/agent-platform/pull/683)
- GPT-1179 Increase single work-item execution timeout from 20mins to 4 hours [#692](https://github.com/Sema4AI/agent-platform/pull/692)
- API to get data frame slices [#687](https://github.com/Sema4AI/agent-platform/pull/687)
- [GPT-1093] Retention Policy - cleanup stale threads [#614](https://github.com/Sema4AI/agent-platform/pull/614)
- Agents Respect `agent_settings.conversation_turns_kept_in_context` When Set By Clients [#699](https://github.com/Sema4AI/agent-platform/pull/699)

# Sema4.ai Agent Server 2.0.31 (2025-08-19)

- Implement Document Layout GET, PUT, and DELETE endpoints [#682](https://github.com/Sema4AI/agent-platform/pull/682)
- Data frames may now be created using a SQL referencing existing data frames. [#655](https://github.com/Sema4AI/agent-platform/pull/655)
- GPT-1158 New endpoint to clear docint details from mindsdb and agentserver [#670](https://github.com/Sema4AI/agent-platform/pull/670)

# Sema4.ai Agent Server 2.0.30 (2025-08-18)

- Agent Settings Support in Agent Spec [#613](https://github.com/Sema4AI/agent-platform/pull/613)
- GPT-1159 Add ability to specify data_connections in DIv2 setup endpoint [#661](https://github.com/Sema4AI/agent-platform/pull/661) [#667](https://github.com/Sema4AI/agent-platform/pull/667)
- Implement documents/extract endpoint [#658](https://github.com/Sema4AI/agent-platform/pull/658)
- GPT-1169 Fix generate_layout_from_file endpoint by encapsulating layout name generation in a threadpool [#669](https://github.com/Sema4AI/agent-platform/pull/669)
- GPT-1164 Increase the max tool duration from 20 mins to 60 mins [#671](https://github.com/Sema4AI/agent-platform/pull/671)
- Bump default context; add arch to LS tracing [#672](https://github.com/Sema4AI/agent-platform/pull/672)
  - Increases the default architeccture context window from 5 turns to 20 turns
- In Public Agent API, the /stream endpoint does not trigger any processing flow. [#676](https://github.com/Sema4AI/agent-platform/pull/676)
- Zendesk 7330. In Public Agent API, the /stream endpoint does not trigger any processing flow. [#676](https://github.com/Sema4AI/agent-platform/pull/676)
- Fixes to truncation finalizer [#673](https://github.com/Sema4AI/agent-platform/pull/673)
- [GPT-1170] File Handling Fix [#678](https://github.com/Sema4AI/agent-platform/pull/678)
- fix: incoming_events.wait_for_event predicate is a just dict [#679](https://github.com/Sema4AI/agent-platform/pull/679)

# Sema4.ai Agent Server 2.0.29 (2025-08-14)

- SAI SDK first iteration [#635](https://github.com/Sema4AI/agent-platform/pull/635)
- [DIN-388] Generate data model from file [#638](https://github.com/Sema4AI/agent-platform/pull/638)
- DIv2 Parse Document Endpoint [#640](https://github.com/Sema4AI/agent-platform/pull/640)
- Include data files for sema4ai_docint in agent-server PyInstaller spec [#649](https://github.com/Sema4AI/agent-platform/pull/649)
- GPT-1155 Enable workitems by default [#650](https://github.com/Sema4AI/agent-platform/pull/650)
- [DIN-339] Enable partial updates in data model (such as quality_checks) [#639](https://github.com/Sema4AI/agent-platform/pull/639)
- [DIN-336] Create default document layout when data model is created [#647](https://github.com/Sema4AI/agent-platform/pull/647)
- Extend generate layout endpoint to fully create Document Layout and return it [#648](https://github.com/Sema4AI/agent-platform/pull/648)

# Sema4.ai Agent Server 2.0.28 (2025-08-13)

- Quotas & limits [PR 498](https://github.com/Sema4AI/agent-platform/pull/498) & [PR 577](https://github.com/Sema4AI/agent-platform/pull/577)
- Add pre-ignition check for document intelligence data server in private v2 API, currently only a stub and will fail with a 412 error. [PR 599](https://github.com/Sema4AI/agent-platform/pull/599)
- (DIv2) Add CRUD API for Data Models. [PR 607](https://github.com/Sema4AI/agent-platform/pull/607) & [PR 630](https://github.com/Sema4AI/agent-platform/pull/630)
- Add create, read, update, delete endpoints for platforms. [PR 597](https://github.com/Sema4AI/agent-platform/pull/597)
- Initial data frame functionality. [PR 631](https://github.com/Sema4AI/agent-platform/pull/631)
- Fix to prompt endpoint tools integration. [PR 611](https://github.com/Sema4AI/agent-platform/pull/611)
- Fix package/deploy endpoint [PR 641](https://github.com/Sema4AI/agent-platform/pull/641)

# Sema4.ai Agent Server 2.0.27 (2025-08-04)

- Add default API key for action server authentication

# Sema4.ai Agent Server 2.0.26 (2025-08-04)

- Release pipeline updates; no functional changes in server.

# Sema4.ai Agent Server 2.0.25 (2025-08-01)

- Model Platform Clients now respect a `models` allowlist (that maps from `provider`: [ `list of allowed models` ]).
- Cortex Client will now retry 500s (as we're seeing Snowflake Cortex throw some of those randomly).
- `/api/v2/providers/{kind}/test` renamed to `/api/v2/platforms/{kind}/test` (aligning clients to our internal terminology more).
- `/api/v2/providers` renamed to `/api/v2/platforms`.
- Server will retry getting an OpenAPI spec from action servers; logging in this area is increased.
- Increase robustness around model params serialization/deserialization.

# Sema4.ai Agent Server 2.0.24 (2025-07-30)

- Add key identifier for static key encryption keys (KEK) to
  enable graceful key rotation and migrations.
- Fix duplicate actions showing in agent-details endpoint.

# Sema4.ai Agent Server 2.0.23 (2025-07-28)

- Enhance the prompt for the work-items judge.

# Sema4.ai Agent Server 2.0.22 (2025-07-26)

- Rebuild of v2.0.21 due to an error in v2.0.21 release process

# Sema4.ai Agent Server 2.0.21 (2025-07-25)

- Hot Reload for Agent Backend
- First Class Storage for Platform Configs
- Enhance CI workflow by adding S3 path for artifact storage across platforms
- Fix Headers Issue w/ MCP Tools & Disable Tool Caching
- Update S3 path in CI workflow for Ubuntu artifact storage from 'ubuntu_x64' to 'linux_x64'
- List workitems (newest comes first)

# Sema4.ai Agent Server 2.0.20 (2025-07-23)

- Add CRUD for MCP servers.
- Added encryption and secret manager for MCP configs.

# Sema4.ai Agent Server 2.0.19 (2025-07-22)

- Update migration numbers to be unique for SQLite and Postgres.

# Sema4.ai Agent Server 2.0.18 (2025-07-22)

- **BREAKING CHANGE**: Reworked work-items list endpoint to support pagination - response is now an object with `work_items` array instead of a direct array ([GPT-1112](https://linear.app/sema4ai/issue/GPT-1112))
- Added work-items endpoints to private v2 API for Workroom integration ([GPT-1113](https://linear.app/sema4ai/issue/GPT-1113))
- Added `/complete` endpoint for work-items ([GPT-1105](https://linear.app/sema4ai/issue/GPT-1105))
- Generate Workroom URL automatically when thread is assigned to work-item ([GPT-1102](https://linear.app/sema4ai/issue/GPT-1102))
- Added MCP servers CRUD endpoints for server configuration ([GPT-1082](https://linear.app/sema4ai/issue/GPT-1082))
- Exposed Agent as MCP under the public API
- Changed work-item ownership model: all work-items now owned by system user with separate creator tracking
- Added `completed_by` parameter to work-item status updates to track completion source
- Implemented secret manager with envelope encryption
- Handle setting `status_updated_by` on work items during various transitions ([GPT-1111](https://linear.app/sema4ai/issue/GPT-1111))


# Sema4.ai Agent Server 2.0.17 (2025-07-17)

- SPAR: Workroom integration with monorepo
- Fix ordering issue in agent server spec tests.
- Regenerate Public API Spec for workitems related endpoints
- Agent CLI & Agent Spec v3

# Sema4.ai Agent Server 2.0.16 (2025-07-16)

- More bug-fixes for work-items

# Sema4.ai Agent Server 2.0.15 (2025-07-16)

- Bug-fixes for work-items

# Sema4.ai Agent Server 2.0.14 (2025-07-16)

- Support pre-signed URLs for uploading files to work-items ([GPT-1069](https://linear.app/sema4ai/issue/GPT-1069/add-presigned-url-file-upload-support-for-large-files))
- Properly set `work_item_url` into work-item callback ([GPT-1087](https://linear.app/sema4ai/issue/GPT-1087/properly-set-work-item-url-into-work-item-callback))

# Sema4.ai Agent Server 2.0.13 (2025-07-14)

- Implement status-based callbacks for Work-Items service.
- Improve LLM-as-Judge checks for Work-Items service.

# Sema4.ai Agent Server 2.0.12 (2025-07-11)

- Make Work Items visible in Work Room ([GPT-1077](https://linear.app/sema4ai/issue/GPT-1077/file-is-not-visible-to-action-when-created-by-work-items))
- Update async action calling to use pod IP instead of ID (change header name to `x-action-server-pod-ip`)
- Assorted non-functional changes to support Quality Framework

# Sema4.ai Agent Server 2.0.11 (2025-07-09)

- Redacted sensitive data from validation errors and request body before logging. ([GPT-1065](https://linear.app/sema4ai/issue/GPT-1065))
- Add SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true in Dockerfile for ACE.

# Sema4.ai Agent Server 2.0.10 (2025-07-09)

- Added work item validation using LLM-as-a-judge. [GPT-1017](https://linear.app/sema4ai/issue/GPT-1017)
- Support file attachments in work-item API. [GPT-1018](https://linear.app/sema4ai/issue/GPT-1018)
- Modifications to streaming, clients may notice responses being a bit "chunkier" but in general they should come even slightly faster than they used to.
- Workitems should be more efficiently processed under load now (less impact to other routes/server activities).

# Sema4.ai Agent Server 2.0.9 (2025-07-08)

- Errors related to stored agents, threads, etc. are now handled consistently across the platform. ([GPT-1028](https://linear.app/sema4ai/issue/GPT-1028))
- Added error handling for invoking models via the Google platform client. ([GPT-1032](https://linear.app/sema4ai/issue/GPT-1032))
- Added error handling for invoking models via the Groq platform client. ([GPT-1033](https://linear.app/sema4ai/issue/GPT-1033))
- Added error handling for 404s and 405s. Now such error responses will have a similar error body to other errors. ([GPT-1036](https://linear.app/sema4ai/issue/GPT-1036))
- Changed handling of environment variables for MCP servers using stdio transport to merge the server's environment variables with the agent-server's environment variables. ([GPT-1062](https://linear.app/sema4ai/issue/GPT-1062))
- Allowed absolute paths for MCP servers using stdio transport.

# Sema4.ai Agent Server 2.0.8 (2025-07-03)

- No significant changes. This is a release from the new branch model in the Agent Platform repo.

# Sema4.ai Agent Server 2.0.7 (2025-07-02)

- Work items are now disabled by default due to issues with the work item system.

# Sema4.ai Agent Server 2.0.6 (2025-07-01)

- Added error handling for invoking models via the Bedrock platform client. ([GPT-1029](https://linear.app/sema4ai/issue/GPT-1029))
- Added tests for agent packages with knowledge files to make sure they do not affect agent creation and interaction. ([GPT-1041](https://linear.app/sema4ai/issue/GPT-1041))

# Sema4.ai Agent Server 2.0.5 (2025-06-27)

## Agent Server

### Bugfixes

- Changed the Resource instantiation for OTEL based telemetry. ([GPT-1027](https://linear.app/sema4ai/issue/GPT-1027))

## Private API

### Features

- Added new endpoint for surfacing runbook and action package details.
 ([GPT-1016](https://linear.app/sema4ai/issue/GPT-1016))


# Sema4.ai Agent Server 2.0.4 (2025-06-23)

## Agent Server

### Features

- Add support for async actions invoke ([GPT-946](https://linear.app/sema4ai/issue/GPT-946))
- Add Claude 4 series models (Sonnet, Opus) specs to the Bedrock Platform Client. ([GPT-1009](https://linear.app/sema4ai/issue/GPT-1009))

### Bugfixes

- Fixed an issue where errors occuring mid-stream could break the kernel. ([GPT-896](https://linear.app/sema4ai/issue/GPT-896))
- Add numpy to the PyInstaller exclude list to prevent existence of multiple NumPy packages. ([GPT-1001](https://linear.app/sema4ai/issue/GPT-1001))
- Make sure we can support SSE/MCP for Studio for now (via default 'auto' mode on server defs) to provide smoother onramp to studio (eventually) sending us this information in the payload (the transport type). For them to send this info, we need to update agent-client-go and agent-cli I believe. ([GPT-1005](https://linear.app/sema4ai/issue/GPT-1005))
- Fix unawaited coroutine log warnings in MCP use ([GPT-1006](https://linear.app/sema4ai/issue/GPT-1006))
- Suppress MCP ping warning logs. ([GPT-1007](https://linear.app/sema4ai/issue/GPT-1007))
- Fix some issues in the underyling SQL for advanced thread message manipulation APIs. ([GPT-1014](https://linear.app/sema4ai/issue/GPT-1014))
- Removed 503 requests from Claude 4 model cassettes

### Miscellaneous

- Keep dependencies up to date (fixing dependabot alerts) ([GPT-1003](https://linear.app/sema4ai/issue/GPT-1003))

### Additional Information Not Pertinent to Client Users

- [GPT-896](https://linear.app/sema4ai/issue/GPT-896), [GPT-1010](https://linear.app/sema4ai/issue/GPT-1010)


## Public API

No significant changes.


## Private API

### Features

- Standardized all error responses across HTTP APIs and WebSocket streams to use a consistent `{ "error": { "code", "error_id", "message" } }` structure. This replaces the previous `detail` field in HTTP responses and flat `error_message`/`error_stack_trace` fields in streaming responses.

      - **Action Required**: Update error handling to use `response.error.message` instead of `response.detail`
      - **Security**: Sensitive debugging information no longer exposed in client responses
      - **Traceability**: Each error now includes a unique `error_id` for support correlation ([GPT-896](https://linear.app/sema4ai/issue/GPT-896))
- workitem crud ([GPT-993](https://linear.app/sema4ai/issue/GPT-993))


# Sema4.ai Agent Server 2.0.2 (2025-06-17)

## Agent Server

### Features

- Adding new quality benchmarking project for assessing quality of agents in aggregate ([GPT-923](https://linear.app/sema4ai/issue/GPT-923))
- Update the events infrastructure to prepare for the concept of client-side tools and further clarify the separation between incoming and outgoing events. ([GPT-966](https://linear.app/sema4ai/issue/GPT-966))
- Support client-side tools (and tag tool defs with their category so we know if they're actions, or from MCP servers, or client-side, etc.) ([GPT-971](https://linear.app/sema4ai/issue/GPT-971))

### Bugfixes

- Fixed thread messages always showing `commited: false` and `complete: false` in API responses. ([GPT-895](https://linear.app/sema4ai/issue/GPT-895))
- Converted ResponseToolUseContent messages in LangSmith traces to tool calls rendered by LangSmith. ([GPT-903](https://linear.app/sema4ai/issue/GPT-903))
- Implemented ConditionalLangSmithProcessor to route LangSmith traces to the right exporters for a given configuration. ([GPT-972](https://linear.app/sema4ai/issue/GPT-972))
- Use Control Room User ID instead of internal user ID while emitting OTEL events ([GPT-975](https://linear.app/sema4ai/issue/GPT-975))

### Removals and Deprecations

- Removed llm.model and llm.provider attributes from OTEL events to be added back at a later date. ([GPT-936](https://linear.app/sema4ai/issue/GPT-936))

### Miscellaneous

- Added inputs/outputs to some LangSmith traces and removed old OTEL code from the OpenAI Platform Client. ([GPT-902](https://linear.app/sema4ai/issue/GPT-902))
- Move common OTEL attributes to kernel function for usage across spans. ([GPT-947](https://linear.app/sema4ai/issue/GPT-947))
- Added check for LangSmith env vars to use as a global config over agent config. ([GPT-988](https://linear.app/sema4ai/issue/GPT-988))
- Exclude dist from typecheck and uv run pyright ([GPT-992](https://linear.app/sema4ai/issue/GPT-992))
- Make sure lint/fix/typecheck runs so we stop breaking that ([GPT-998](https://linear.app/sema4ai/issue/GPT-998))
- Fixed minor lint + format issues.

### Additional Information Not Pertinent to Client Users

- [GPT-973](https://linear.app/sema4ai/issue/GPT-973), [GPT-978](https://linear.app/sema4ai/issue/GPT-978), [GPT-990](https://linear.app/sema4ai/issue/GPT-990)


## Public API

### Features

- Add auth to MCP endpoints ([GPT-911](https://linear.app/sema4ai/issue/GPT-911))
- Agent MCP ([GPT-986](https://linear.app/sema4ai/issue/GPT-986))
- Typescript Public SDK - surface endpoint for streaming conversations

### Bugfixes

- Remove trailing slash to make it compatible with legacy api

### Miscellaneous

- Change public api prefix to v1


## Private API

### Features

- Add POST /tid/fork endpoint to fork thread messages ([GPT-907](https://linear.app/sema4ai/issue/GPT-907))
- Implement edit thread message endpoint ([GPT-908](https://linear.app/sema4ai/issue/GPT-908))
- Allow the prompt endpoint to take either a platform_config_raw (as it does today) or an agent_id or a thread_id; if agent or thread IDs are provided, the endpoint will grab the first platform config from the agent (or agent associated with the thread). ([GPT-921](https://linear.app/sema4ai/issue/GPT-921))
- Add new ephemeral agent stream endpoint to private API (allows you to stream against an agent created in an ephemeral way --- not persisted to storage) ([GPT-967](https://linear.app/sema4ai/issue/GPT-967))
- New endpoint to list tools on MCP servers given their name/URL. Introduced to capabilities API ([GPT-977](https://linear.app/sema4ai/issue/GPT-977))

### Bugfixes

- Added sync and async endpoints to Typescript SDK.
- In a previous PR we made description field in package payload optional and this broke some clients. Here, we revert those changes.


# Sema4.ai Agent Server 2.0.1 (2025-06-06)

## Agent Server

### Bugfixes

- Restore INSERT .. ON CONFLICT logic to match agentserver v1 to try to mitigate a files issue in ACE ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))

### Additional Information Not Pertinent to Client Users

- [GPT-959](https://linear.app/sema4ai/issue/GPT-959)


## Public API

### Features

- Porting public API to v2: sse streaming for agent conversations. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913))


## Private API

### Bugfixes

- Fix package import failing to handle UNSET legacy Azure fields correctly ([GPT-964](https://linear.app/sema4ai/issue/GPT-964))


# Sema4.ai Agent Server 2.0.0 (2025-06-06)

## Agent Server

### Features

- Improved conversation management with smart content truncation: When conversations become too long for the AI model, the system now intelligently manages content by selectively truncating tool outputs rather than cutting all content equally. Larger tool outputs are reduced more than smaller ones, ensuring important conversation context is preserved while maintaining readability. This results in better conversation quality and more predictable behavior when dealing with long threads containing extensive tool results. ([GPT-849](https://linear.app/sema4ai/issue/GPT-849))
- Faster agent-server startup, no longer leaving leftover files in temp dir when agent-server is killed (using go-wrapper instead of pyinstaller --onefile mode). ([GPT-854](https://linear.app/sema4ai/issue/GPT-854))
- Automatically upgrade existing agents and conversations to the latest format on server startup. Users will not need to take any action - existing agents and conversations should continue to work as expected. ([GPT-862](https://linear.app/sema4ai/issue/GPT-862))
- Updated approximate token counting to use a fast heuristic method by default instead of tiktoken. Set SEMA4AI_AGENT_SERVER_TOKEN_COUNTING_ENABLE_TIKTOKEN=true to restore tiktoken-based counting or use the similar configuration option. ([GPT-891](https://linear.app/sema4ai/issue/GPT-891))
- Added OTEL counters for token usage with attributes for filtering. ([GPT-901](https://linear.app/sema4ai/issue/GPT-901))
- Added token usage information for OpenAI and Azure OpenAI Platform Clients ([GPT-909](https://linear.app/sema4ai/issue/GPT-909))
- Implemented a comprehensive metrics observability stack using Prometheus and Jaeger for our OTEL setup. ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))
- Add sema4ai otel metrics.

### Bugfixes

- Fix typo in package endpoint; cache tools and add /api/v2/agents/{aid}/refresh-tools ([GPT-843](https://linear.app/sema4ai/issue/GPT-843))
- Disconnect handled more carefully now for clients using WebSocket streaming; Bedrock platform parameters serialization/deserialization upgraded for robustness ([GPT-844](https://linear.app/sema4ai/issue/GPT-844))
- Increase test robustness by checking in test data file instead of fetching it ([GPT-847](https://linear.app/sema4ai/issue/GPT-847))
- Use polling API to interact with Reducto. ([GPT-851](https://linear.app/sema4ai/issue/GPT-851))
- Token counting now gracefully handles invalid model names by falling back to a default model instead of failing with an error ([GPT-853](https://linear.app/sema4ai/issue/GPT-853))
- Fix for cortex authentication: some internal configuration changes altered expected contract between us, Studio, space-client, etc. This PR introduces a fix and more logging for future troubleshooting. ([GPT-856](https://linear.app/sema4ai/issue/GPT-856))
- Increase tool definition caching sophistication (for MCP and Action servers); allow clients to disable tool caching using the SEMA4AI_AGENT_SERVER_TOOL_CACHE_ENABLED=false environment variable. ([GPT-858](https://linear.app/sema4ai/issue/GPT-858))
- Made tool error handling more reliable with clearer error messages when tools encounter problems during execution ([GPT-860](https://linear.app/sema4ai/issue/GPT-860))
- Use env variables to setup langsmith for back compat ([GPT-865](https://linear.app/sema4ai/issue/GPT-865))
- Improved error handling for action server tools that return errors in the {result: None, error: message} format. Users will now see clear error messages when external tools fail rather than receiving malformed responses or generic errors. ([GPT-867](https://linear.app/sema4ai/issue/GPT-867))
- Update json parsing for action-server response and check for MCP result. ([GPT-869](https://linear.app/sema4ai/issue/GPT-869))
- Fixed issue where Agent Server wouldn't start because it presumed a port was being used while it was actually free. ([GPT-870](https://linear.app/sema4ai/issue/GPT-870))
- Fixed an issue where results from tools could be reports as malformed when they are not. ([GPT-875](https://linear.app/sema4ai/issue/GPT-875))
- Fix tool call rendering in LangSmith input history. ([GPT-876](https://linear.app/sema4ai/issue/GPT-876))
- Enable propagation of token usage information to LangSmith ([GPT-877](https://linear.app/sema4ai/issue/GPT-877))
- Increased the default maximum content limit when truncation is triggered on long tool results to approximately 10,000 tokens. ([GPT-882](https://linear.app/sema4ai/issue/GPT-882))
- More robust output format parsing to convert LLM replies into thoughts/responses/processing status. Prompt changes to come in a separate PR. Before prompt changes are in, this still wont be quite enough to solve the behavior we're seeing, but it's a start. ([GPT-883](https://linear.app/sema4ai/issue/GPT-883))
- Fix to get parallel tool calls operational for Cortex platform client, parsing was sligtly off. New test and fresh VCR fixtures to verify fix. ([GPT-910](https://linear.app/sema4ai/issue/GPT-910))
- Migrations for Cortex agents and threads may be missing a few small things; fixed migrations for these niche cases. ([GPT-917](https://linear.app/sema4ai/issue/GPT-917))
- Prompt scaffold and step parsing upgrades for robustness in default agent arch ([GPT-918](https://linear.app/sema4ai/issue/GPT-918))
- Modify attributes emitted in OTEL spans so ACE does not block them. ([GPT-936](https://linear.app/sema4ai/issue/GPT-936))
- Correct uniqueness constraint over file uploads to allow the same filename to be uploaded across threads in an agent. ([GPT-938](https://linear.app/sema4ai/issue/GPT-938))
- Second round of prompt scaffold updates; Gemini still shaky, other platforms should have improved behavior in less looping and more consistent correct use of tools. ([GPT-940](https://linear.app/sema4ai/issue/GPT-940))
- Backup prompt to ensure output format adherance updated to also pass tools (shouldn't be necessary, but Cortex seems to need it) ([GPT-942](https://linear.app/sema4ai/issue/GPT-942))
- Fix handling of whitelist for separate action packages on same server ([GPT-950](https://linear.app/sema4ai/issue/GPT-950))
- A faulty env variable was changed to make cloud file manager tests work again. Also, the cloud server file had its request parameters changed. ([GPT-951](https://linear.app/sema4ai/issue/GPT-951))
- Clean up OTEL logs to remove logs related to 409 conflicts and warnings. ([GPT-956](https://linear.app/sema4ai/issue/GPT-956))
- Fixed action metadata not coming through for more complex action definitions ([GPT-957](https://linear.app/sema4ai/issue/GPT-957))
- Revert locking changes in LangSmithContext and updated collector url checking in telemtry. ([GPT-960](https://linear.app/sema4ai/issue/GPT-960))

### Improved Documentation

- Added developer guide and updated the readme for recent changes
- Added vscode launch profile for testing jwt local and postgres config

### Miscellaneous

- Start of Agent Server v2 changelog in the Agent Platform repo! ([GPT-839](https://linear.app/sema4ai/issue/GPT-839))
- Improved reliability when processing large documents and tool outputs by automatically preserving the most important information while avoiding model context limits. ([GPT-842](https://linear.app/sema4ai/issue/GPT-842))
- Code formatting for non-python files (.json, .yaml, .ts, .tsx, .md) with prettier. ([GPT-855](https://linear.app/sema4ai/issue/GPT-855))
- Updated debug widget used for quick internal testing to have fresh build of widget UX and more recent deps. ([GPT-898](https://linear.app/sema4ai/issue/GPT-898))
- Move orchestrator repo for our integration tests in. Misc, should have no downstream effects, purely for ease of testing and to unblock Codex setup. ([GPT-904](https://linear.app/sema4ai/issue/GPT-904))
- Improving otel with message counter ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- OTEL: Remove 'user' field from OTEL logs implementation ([GPT-915](https://linear.app/sema4ai/issue/GPT-915))
- Remove old collector files and create new make targets for observability purporses ([GPT-930](https://linear.app/sema4ai/issue/GPT-930))
- Updates to the Makefile and README to list all make targets. ([GPT-937](https://linear.app/sema4ai/issue/GPT-937))
- More tests for files fixes ([GPT-941](https://linear.app/sema4ai/issue/GPT-941))
- Adds classify prompt for Reducto
- Fixes some dev related settings and a broken integration tests. Nothing user facing.
- If the agent server binary does not exist, the built Docker image is broken because curl does not fail and we don't know in advance that no actual file was downloaded. We change the Dockerfile in order to fail early and not ship broken images.

### Additional Information Not Pertinent to Client Users

- [GPT-839](https://linear.app/sema4ai/issue/GPT-839), [GPT-866](https://linear.app/sema4ai/issue/GPT-866), [GPT-866](https://linear.app/sema4ai/issue/GPT-866), [GPT-889](https://linear.app/sema4ai/issue/GPT-889), [GPT-890](https://linear.app/sema4ai/issue/GPT-890), [GPT-920](https://linear.app/sema4ai/issue/GPT-920), [GPT-927](https://linear.app/sema4ai/issue/GPT-927), [GPT-939](https://linear.app/sema4ai/issue/GPT-939), [GPT-962](https://linear.app/sema4ai/issue/GPT-962)


## Public API

### Features

- Porting public API to v2. ([GPT-913](https://linear.app/sema4ai/issue/GPT-913), [GPT-913](https://linear.app/sema4ai/issue/GPT-913))
- Typescript SDK for public API

### Miscellaneous

- Public API v1 tweaks, cleanup, and some observations while testing agent connector.


## Private API

### Features

- Add PUT /threads api ([GPT-861](https://linear.app/sema4ai/issue/GPT-861))
- Trace name in LangSmith has been changed to the thread name for better searchability. Added new metadata as well. ([GPT-879](https://linear.app/sema4ai/issue/GPT-879))
- Implement async invoke endpoint in runs ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Implement GET run status endpoint ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Patch openapi spec with an endpoint for websocket streaming
- Surface MCP servers in package endpoint
- Update Typescript Client with spec 2.0.0-beta.3.
- Update Typescript SDK to 2.0.0-rc.

### Bugfixes

- Fix missing model name for legacy api ([GPT-864](https://linear.app/sema4ai/issue/GPT-864))
- Fixed file upload errors that could occur when files were successfully uploaded but the system incorrectly reported them as failed ([GPT-868](https://linear.app/sema4ai/issue/GPT-868))
- agents are wrongly created with conversational mode even if worker mode is specified ([GPT-872](https://linear.app/sema4ai/issue/GPT-872))
- Ignore thread messages from all GET thread endpoints ([GPT-885](https://linear.app/sema4ai/issue/GPT-885))
- Hide sensitive variables from get agents api and post agents api ([GPT-886](https://linear.app/sema4ai/issue/GPT-886))
- Make threads name filter case insensitive ([GPT-893](https://linear.app/sema4ai/issue/GPT-893))
- Bug fix in the route name ([GPT-928](https://linear.app/sema4ai/issue/GPT-928))
- Roundtripping of legacy worker config was broken, fix and tests introduced ([GPT-934](https://linear.app/sema4ai/issue/GPT-934))
- Fix masking: /agents/{aid}/raw needs to _not_ mask sensitive info ([GPT-935](https://linear.app/sema4ai/issue/GPT-935))
- Hotfix to include in UploadedFile structure so that the GET file-by-ref endpoint works. ([GPT-939](https://linear.app/sema4ai/issue/GPT-939))
- Missing thread rename support; current UX uses GET and PUT but after we stopped sending thread message contents, this pattern leads to deleting thread messages on rename! ([GPT-952](https://linear.app/sema4ai/issue/GPT-952))
- Action invocation user id should be control room `user_id` and not the database `id`.
- Adding action context headers required for Ace integration
- Expires for presigned urls are controlled by Ace. Agent Platorm side we should always refresh the url otherwise we may found out that a cached url is already expired.
- Messages are not persisted when a file is created
- Missing endpoints for file uploading; porting from v1 to v2.
- When agent is created via package endpoint, mode is always conversational and worker agent metadata are lost.
- url join strips the last segment

### Miscellaneous

- Start foundational work for patching types that are not correctly generated by tools
- improve type tests for v1 compatibility in Typescript SDK
