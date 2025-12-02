# Documents Feature (Stub Implementation)

This document describes the newly added documents feature.

## Overview

The documents feature provides a framework for managing documents in the agent platform. Documents can be text content or files that
can be used with Reducto to Parse a documents structure or Extract data from a Document in an specific shape.

## Architecture

### Core Layer (`core/`)

**Location:** `core/src/agent_platform/core/documents/`

- **`documents.py`**: Core data model (`PlatformDocument`)

  - Represents a document with metadata (id, user_id, agent_id, thread_id, name)
  - Includes validation and serialization methods

- **`__init__.py`**: Exports the main `PlatformDocument` class

**Location:** `core/src/agent_platform/core/kernel_interfaces/`

- **`documents.py`**: Abstract interface for documents functionality
  - `DocumentArchState`: Protocol for architecture state
  - `DocumentsInterface`: Abstract base class defining the contract for document operations

### Server Layer (`server/`)

**Location:** `server/src/agent_platform/server/kernel/`

- **`documents.py`**: `AgentServerDocumentsInterface` implementation
  - Implements `DocumentsInterface` from core
  - Provides step initialization, enablement checks, summaries, and tools

## Key Features

### Opt-in by Default

Documents is **opt-in**:

- Can be enabled via agent settings: `document_intelligence: internal`

### Document Model

- Automatically built from the internal File representation.
