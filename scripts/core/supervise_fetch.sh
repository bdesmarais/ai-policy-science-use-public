#!/bin/bash
# Supervisor for the refresh fetcher: restarts on stall/death (fetcher is resumable),
# emits an event line on each restart and on completion, then exits. Each echoed line
# becomes a notification, so the agent re-engages on real events only.
cd /Users/bbd5087/Documents/GitHub/ai-policy-science-use
LOG=outputs/refresh/fetch.log
last=-1; stall=0
count() { find outputs/refresh/text -name '*.txt' 2>/dev/null | wc -l | tr -d ' '; }
running() { pgrep -f fetch_refresh_releases.py >/dev/null; }
for i in $(seq 1 80); do
  if grep -q "^done:" "$LOG" 2>/dev/null; then
    echo "FETCH_DONE $(grep '^done:' "$LOG" | tail -1) | files=$(count)"; exit 0
  fi
  c=$(count)
  if running; then
    if [ "$c" -le "$last" ]; then stall=$((stall+1)); else stall=0; fi
    if [ "$stall" -ge 5 ]; then
      echo "FETCH_STALLED at $c files (5x30s no progress) -> restarting"
      pkill -f fetch_refresh_releases.py; sleep 3
      nohup python3 scripts/core/fetch_refresh_releases.py >> "$LOG" 2>&1 &
      stall=0
    fi
  else
    echo "FETCH_PROC_DIED at $c files -> restarting (resumable)"
    nohup python3 scripts/core/fetch_refresh_releases.py >> "$LOG" 2>&1 &
  fi
  last=$c
  sleep 30
done
echo "SUPERVISOR_TIMEOUT at $(count) files (still running=$(running && echo yes || echo no))"
