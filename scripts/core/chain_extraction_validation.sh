#!/bin/bash
cd /Users/bbd5087/Documents/GitHub/ai-policy-science-use
# 1) wait for the check-worthiness panel run to finish (frees MPS)
for i in $(seq 1 60); do
  pgrep -f benchmark_extraction_validation.py >/dev/null || break
  sleep 20
done
echo "PANEL_DONE $(grep -o \"'f1': [0-9.]*\" benchmarks/results/extraction_cw_run.log | tail -3 | tr '\n' ' ')"
# 2) run faithfulness/grounding (MPS now free)
python3 scripts/core/faithfulness_validation.py > benchmarks/results/faithfulness_run.log 2>&1
echo "FAITHFULNESS_DONE $(grep -i 'overall_grounding_rate\|mean_max_entail' benchmarks/results/faithfulness_run.log | tr '\n' ' ')"
