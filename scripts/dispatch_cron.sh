#!/bin/zsh
# Local launchd-driven dispatcher for tjr-bot GitHub Actions.
# GitHub's own cron drops/delays runs badly; this fires gh workflow_dispatch at exact ET
# times instead. launchd runs this every 5 min on weekdays; the script decides which mode
# (if any) to trigger based on the current America/New_York time. Idempotent-ish: each slot
# fires once per day because launchd ticks on 5-min boundaries and we match exact HH:MM.
#
# Installed by com.drake.tjr-cron.plist (StartInterval 300, RunAtLoad).
export PATH="/Users/drake/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG=/Users/drake/Claude/trading-bot/logs/cron_dispatch.log
mkdir -p "$(dirname "$LOG")"

REPO=drakethegamer1102-blip/tjr-bot
WF=trade.yml

# Current ET time parts
DOW=$(TZ=America/New_York date +%u)   # 1=Mon .. 7=Sun
HHMM=$(TZ=America/New_York date +%H:%M)
HH=$(TZ=America/New_York date +%H)
MIN=$(TZ=America/New_York date +%M)

# Weekdays only
[[ "$DOW" -ge 6 ]] && exit 0

fire() {
  local mode="$1"
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] dispatch mode=$mode" >> "$LOG"
  gh workflow run "$WF" -R "$REPO" -f mode="$mode" >> "$LOG" 2>&1 \
    && echo "  -> ok" >> "$LOG" || echo "  -> FAIL" >> "$LOG"
}

# --- Exact-time close/session jobs (match HH:MM once/day) ---
case "$HHMM" in
  09:35) fire rebound-open ;;
  15:55) fire rebound-close ;;
  16:05) fire summary ;;
  16:20) fire orb-futures ;;
  16:30) fire review ;;
esac
# Weekly recap: Friday 16:10 ET
[[ "$DOW" == "5" && "$HHMM" == "16:10" ]] && fire weekly

# --- Intraday scan: every 5 min, 09:30-16:00 ET inclusive ---
# HH in 09..15 (any minute on the 5s), plus exactly 16:00.
if { [[ "$HH" -ge 9 && "$HH" -le 15 ]] && [[ $((10#$MIN % 5)) -eq 0 ]]; }; then
  # skip 09:00-09:25 pre-open
  if [[ "$HH" == "09" && "$MIN" -lt 30 ]]; then
    :
  else
    fire once
  fi
elif [[ "$HHMM" == "16:00" ]]; then
  fire once
fi
