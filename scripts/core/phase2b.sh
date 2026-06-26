#!/bin/bash
cd ~/Documents/GitHub/ai-policy-science-use
PANEL="llm:Qwen/Qwen2.5-3B-Instruct llm:microsoft/Phi-3.5-mini-instruct llm:allenai/OLMo-2-1124-7B-Instruct"
echo "[p2b] waiting for SciFact panel..."
while ! grep -q "wrote results/report_scifact_panel" benchmarks/results/panel_scifact.log 2>/dev/null; do sleep 20; done
echo "[p2b] === Climate-FEVER benchmark (NLI + panel) ==="
python3 scripts/core/benchmark_validation.py --benchmark climate_fever --balanced 150 \
  --validators nli_deberta nli_bart $PANEL --tag cf
echo "[p2b] === Climate-FEVER Claude scoring ==="
python3 scripts/core/benchmark_validation.py --benchmark climate_fever --balanced 150 \
  --validators claude --claude-labels benchmarks/claude_labels_climate_fever.json --tag cf_claude
echo "[p2b] === policy stance: GPT-5 refs (NLI + panel) ==="
python3 scripts/core/policy_stance.py --refs gpt5 --validators nli_deberta nli_bart $PANEL
echo "[p2b] === policy stance: OpenAlex refs (NLI) ==="
python3 scripts/core/policy_stance.py --refs openalex --validators nli_deberta nli_bart
echo "[p2b] ALL DONE"
