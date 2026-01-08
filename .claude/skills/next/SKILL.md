---
name: next
description: Start working on your next Linear issue. Retrieves in-progress and upcoming tickets, helps spec and plan them, then guides implementation. Keywords: "linear", "ticket", "issue", "next", "start work"
---

# /next - Linear Issue Workflow

This skill helps you work on Linear issues with a structured workflow: Spec → Plan → Implement.

## Prerequisites

- Linear MCP server must be connected (`linear-server`)
- You must be authenticated with Linear

## General Principles

- **Always use `AskUserQuestion`** for user input throughout this workflow - never assume
- **When multiple approaches exist**, present all options with pros/cons and let the user decide
- **Linear is the source of truth** - update it proactively and frequently
- **You are the driver** - maintain momentum, follow the plan, only pause for genuine blockers

## Workflow

### Step 1: Retrieve Assigned Issues

Fetch issues assigned to you (ignore issues you only created but aren't assigned to).

Call these Linear MCP tools in parallel:
1. `mcp__linear-server__list_issues(assignee: "me", state: "In Progress", limit: 20)`
2. `mcp__linear-server__list_issues(assignee: "me", state: "Next", limit: 10)`

Include: issue identifier, title, description, status, parent issue/project info.
Sort by: priority, then by status (In Progress first).

### Step 2: Present Issues and Let User Pick

Use `AskUserQuestion` to present the list. Format each issue as:
```
[IDENTIFIER] Title (Status)
```

Mark issues with ✓ if they already have both #SPEC and #PLAN sections.

### Step 3: Analyze Issue Content

Fetch full content:
```
mcp__linear-server__get_issue(id: "<ISSUE_ID>", includeRelations: true)
```

If the issue has a `parentId`, also fetch the parent for context.

Check for:
1. **#SPEC section** - WHAT needs to be done
2. **#PLAN section** - HOW it will be done
3. **Parent issue/project context**

### Step 4: Handle Missing #SPEC

If no `#SPEC` section exists:

1. Show the user the issue title and any parent context
2. Ask for the specification:
   - "What is the expected behavior?"
   - "What are the acceptance criteria?"
   - "Are there any constraints or requirements?"
3. Format under `#SPEC` heading and update the Linear issue

### Step 5: Handle #PLAN

**If no `#PLAN` section exists:**

1. Ask technical questions:
   - "Where is the code that needs to change? (file paths, modules)"
   - "What are potential shortcomings or risks?"
   - "What should we pay attention to? (edge cases, dependencies)"
   - "Are there any related patterns in the codebase to follow?"

2. **Explore the codebase** using `Task` tool with `subagent_type=Explore` to understand existing patterns, possible approaches, and constraints

3. **If multiple approaches identified**: Present them with pros/cons. Let the user decide before proceeding.

4. Create structured `#PLAN` and update Linear (see Format Reference below)

**If `#PLAN` already exists:**

1. Present the existing plan
2. Ask if modifications are needed
3. Update if requested

### Step 6: Ready to Implement

Once both #SPEC and #PLAN are present, use `AskUserQuestion` with options:
- **Start Implementation** - Begin working now
- **End Session** - Clear context and start fresh later

### Step 7: During Implementation

1. **Load the `pr-review` skill** as a guide - implementation will be reviewed against it
2. Follow the #PLAN steps
3. Track deviations in `#DECISION LOG` section
4. Check off completed items in #PLAN

**Driving the implementation:**
- Always have a next action - never wait passively
- If blocked, ask immediately with specific options
- When plan is complete, say so and ask if there's more

**Anti-patterns:**
- "Let me know what you'd like to do next" (you should know from the plan)
- "Should I continue?" (yes, unless blocked)
- Waiting for confirmation after every small step

## Background Linear Updates

Linear updates should NOT block implementation. Use background agents for:
- Updating #DECISION LOG entries
- Checking off completed items in #PLAN
- Adding #SESSION HANDOVER content

```
Task tool with:
  - subagent_type: "general-purpose"
  - run_in_background: true
  - prompt: "Update Linear issue <ID> description to add: <content>"
```

**Wait for Linear only when:**
- Initial issue fetch (need content to proceed)
- Creating new issues (may need the ID)
- User explicitly asks to verify the update

## Session Handover

**Trigger when:**
- User requests to end the session
- Context is getting long (many tool calls, large exploration)
- Work cannot be completed in current session
- Before any `/clear` command

Update Linear with `#SESSION HANDOVER` section (can use background agent).

## Branch Requirement

**You MUST be on a branch before committing any work.**

Before starting implementation:
1. Check if a branch for this issue already exists (e.g., from a previous session/handover): `git branch -a | grep <ISSUE-ID>`
2. If it exists, check it out: `git checkout <branch-name>`
3. If not, create a new branch with the format:

```
<type>/<ISSUE-ID>_<description>
```

Where:
- `<type>` is one of: `feat`, `fix`, `chore`, `docs`
- `<ISSUE-ID>` is the Linear issue identifier (e.g., `PRD-1286`, `CLOUD-5794`)
- `<description>` is a very short, git-friendly description

Examples:
```
feat/PRD-1286_public-api
fix/CLOUD-5794_agent-visibility
chore/CLOUD-5730_bucket-versioning
```

## Commit Convention

Always prefix commits with the issue identifier:
```
<ISSUE-ID> - <type>: <description>
```

Types: `feat`, `fix`, `chore`, `docs`

Examples:
```
PRD-1286 - feat: add public API routes with API key authentication
CLOUD-5794 - fix: resolve agent visibility sync between Work Room and Control Room
```

## Format Reference

### #SPEC
```
#SPEC

## Goal
[What this issue aims to achieve]

## Requirements
- Requirement 1
- Requirement 2

## Acceptance Criteria
- [ ] Criteria 1
- [ ] Criteria 2
```

### #PLAN
```
#PLAN

## Overview
[High-level approach]

## Files to Modify
- [ ] file1.ts - changes
- [ ] file2.ts - changes

## Implementation Steps
1. Step 1
2. Step 2

## Considerations
- Note 1
- Note 2
```

### #DECISION LOG
```
#DECISION LOG

- [YYYY-MM-DD] **Decision**: Description of what was decided and why
```

### #SESSION HANDOVER
```
#SESSION HANDOVER (YYYY-MM-DD)

## Work Completed
1. Description of completed work
   - Specific files changed
   - Key decisions made

## Remaining Work
1. [ ] Specific task with file paths and code examples if needed
2. [ ] Another specific task

## Build/Test Status
- Current errors (if any)
- Command to verify: `npm run build` or similar

## Files Changed
- path/to/file.ts - description
```
