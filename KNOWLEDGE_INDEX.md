# KNOWLEDGE_INDEX.md

Codebase Knowledge Index Specification

---

PURPOSE

The Knowledge Index is a structured metadata representation of the repository.

It enables fast code queries without requiring an LLM.

The index works alongside the graph system.

---

INDEX CONTENT

The index stores structured metadata for:

files
classes
functions
variables
imports
dependencies

---

FUNCTION ENTRY FORMAT

Each function entry should contain:

name
file
start_line
end_line
parameters
variables_read
variables_written
functions_called
docstring

Example:

FunctionEntry

name: compute_diff
file: slam/update.py
start_line: 42
end_line: 68
parameters: state, prediction
variables_read: state
variables_written: diff
functions_called: normalize, clip

---

CLASS ENTRY FORMAT

Each class entry should contain:

class name
file
methods
attributes
base classes

---

FILE ENTRY FORMAT

Each file entry should contain:

file path
imports
classes defined
functions defined

---

INDEX STORAGE

Initial implementation should store the index in memory.

Later versions may persist the index using:

JSON
SQLite
or graph database.

---

QUERY TYPES

The Knowledge Index must support queries such as:

find functions modifying variable

find functions calling function

find files importing module

find classes inheriting from class

---

INDEX USAGE IN RETRIEVAL PIPELINE

Query
↓
Extract symbol
↓
Search knowledge index
↓
Retrieve candidate nodes
↓
Graph traversal
↓
Semantic ranking

---

ADVANTAGES

The Knowledge Index allows many queries to be answered without LLM usage.

Examples:

Where is variable diff modified?

Which functions call compute_diff?

Which modules depend on slam.update?

These queries can be answered directly using the index.

---

FUTURE EXTENSIONS

Possible improvements:

cross-language support

dependency metrics

code complexity scoring

architecture summaries

---

END KNOWLEDGE INDEX SPEC
