#!/bin/bash
# Supervisor for the corpus retrieval: emits an event when the 44 fresh claims are done
# and when all claims are done; restarts the (resumable) retrieval if it stalls/dies.
cd /Users/bbd5087/Documents/GitHub/ai-policy-science-use
export AI_RETRIEVAL_BACKEND=crossref
LOG=outputs/ai_corpus/retrieval_cr.log
last=-1; stall=0; fresh_announced=0
stat() { python3 - <<'PY'
import json
d=json.load(open('outputs/ai_corpus/retrieved_pairs.json'))
total=len(d); fresh=sum(1 for r in d if r['id'].startswith('n'))
print(total, fresh)
PY
}
running() { pgrep -f ai_corpus_retrieval.py >/dev/null; }
for i in $(seq 1 120); do
  read total fresh < <(stat 2>/dev/null)
  total=${total:-0}; fresh=${fresh:-0}
  if [ "$fresh_announced" = "0" ] && [ "$fresh" -ge 44 ]; then
    echo "FRESH_DONE 44/44 fresh claims retrieved (total=$total)"; fresh_announced=1
  fi
  if grep -q "^done:" "$LOG" 2>/dev/null; then echo "RETRIEVAL_DONE total=$total fresh=$fresh"; exit 0; fi
  if running; then
    if [ "$total" -le "$last" ]; then stall=$((stall+1)); else stall=0; fi
    if [ "$stall" -ge 6 ]; then
      echo "RETRIEVAL_STALLED at $total (restarting)"; pkill -f ai_corpus_retrieval.py; sleep 3
      nohup python3 scripts/core/ai_corpus_retrieval.py >> "$LOG" 2>&1 & stall=0
    fi
  else
    if ! grep -q "^done:" "$LOG" 2>/dev/null; then
      echo "RETRIEVAL_PROC_DIED at $total (restarting)"
      nohup python3 scripts/core/ai_corpus_retrieval.py >> "$LOG" 2>&1 &
    fi
  fi
  last=$total; sleep 25
done
echo "RETRIEVAL_SUPERVISOR_TIMEOUT at $last"
