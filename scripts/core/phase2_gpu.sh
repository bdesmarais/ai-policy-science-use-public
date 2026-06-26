#!/bin/bash
cd ~/Documents/GitHub/ai-policy-science-use
PANEL="llm:Qwen/Qwen2.5-3B-Instruct llm:microsoft/Phi-3.5-mini-instruct llm:allenai/OLMo-2-1124-7B-Instruct"
echo "[phase2] waiting for SciFact panel to finish..."
while ! grep -q "wrote results/report_scifact_panel" benchmarks/results/panel_scifact.log 2>/dev/null; do sleep 20; done
echo "[phase2] SciFact panel done -> Climate-FEVER benchmark"
python3 scripts/core/benchmark_validation.py --benchmark climate_fever --balanced 150 \
  --validators nli_deberta nli_bart $PANEL \
  --claude-labels benchmarks/claude_labels_climate_fever.json --tag cf
echo "[phase2] waiting for OpenAlex CA retrieval to finish..."
while ! grep -q "^DONE" outputs/openalex_ca.log 2>/dev/null; do sleep 15; done
echo "[phase2] OpenAlex retrieval done -> policy stance on OpenAlex refs"
python3 scripts/core/policy_stance.py --refs openalex --validators nli_deberta nli_bart $PANEL
echo "[phase2] policy stance on GPT-5 refs (for retrieval-robustness comparison)"
python3 scripts/core/policy_stance.py --refs gpt5 --validators nli_deberta nli_bart
echo "[phase2] ALL DONE"
