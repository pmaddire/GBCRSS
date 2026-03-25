# Performance Notes

## Baseline Benchmarks

- `.venv\\Scripts\\python.exe -m unittest tests.performance.test_benchmarks -v`
- `.venv\\Scripts\\python.exe -m unittest` for full-suite timing signal

## Tracked Metrics

- Retrieval cache hit behavior
- Graph snapshot copy cost and integrity
- Symbolic retrieval micro-latency (ms)

## Guidance

Keep benchmark fixtures deterministic and lightweight.