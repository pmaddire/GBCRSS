# ARCHITECTURE.md

GraphCode Intelligence Engine (GCIE) Architecture

This document describes the architecture of the GCIE system.

---

SYSTEM PURPOSE

GCIE is a graph-based code intelligence engine that retrieves minimal execution-relevant code context for LLM workflows.

The system reduces token usage by retrieving only relevant code paths rather than entire files.

---

CORE SUBSYSTEMS

The system consists of five primary subsystems.

1. Code Parser
2. Graph Builder
3. Knowledge Index
4. Retrieval Engine
5. LLM Context Builder

---

ARCHITECTURE DIAGRAM

Repository
↓
Repository Scanner
↓
AST Parser
↓
Symbol Extractor
↓
Graph Builders
↓
Unified Knowledge Graph
↓
Knowledge Index
↓
Retrieval Engine
↓
LLM Context Builder
↓
CLI Interface

---

GRAPH SYSTEM

The graph system builds multiple graphs representing the codebase.

Code Structure Graph

Represents relationships between files, classes, and functions.

Call Graph

Represents which functions call other functions.

Variable Dependency Graph

Represents read/write relationships between functions and variables.

Execution Trace Graph

Represents runtime execution paths captured via tracing.

Git History Graph

Represents relationships between commits and code elements.

Test Coverage Graph

Represents relationships between tests and executed code.

---

KNOWLEDGE INDEX

The Knowledge Index is a structured metadata index of the codebase.

It stores:

function metadata
class metadata
file metadata
variable metadata
dependency metadata

The Knowledge Index allows fast queries such as:

Which functions modify variable X

Which modules depend on module Y

Which functions call function Z

These queries can be answered without calling an LLM.

---

RETRIEVAL PIPELINE

Query
↓
Symbol Extraction
↓
Knowledge Index Query
↓
Graph Traversal
↓
Semantic Ranking
↓
Context Builder
↓
LLM

---

TOKEN REDUCTION STRATEGY

Token usage is reduced by:

1. Graph-based symbolic retrieval
2. Knowledge index filtering
3. Semantic ranking
4. Minimal context packaging

---

EXPECTED TOKEN SAVINGS

Typical context sizes:

Naive repo prompt:
20k tokens

Vector RAG:
3k tokens

GCIE graph retrieval:
300–800 tokens

---

END ARCHITECTURE
