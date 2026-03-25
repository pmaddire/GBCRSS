# Agent Instructions

Before making any code change, run:

```
gcie context . "<task>" --budget auto --intent <edit|debug|refactor|explore>
```

Use only the returned snippets as working context.
If the context seems insufficient, increase the budget or rerun the command.