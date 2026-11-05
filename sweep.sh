#!/bin/bash
# Overnight fixed-level sweep: all 40 cases at each level, then power off.
# Resumable: rerun the same command after a restart and finished cases are skipped.
#   tmux new -s sweep  ->  ./sweep.sh        (add --no-poweroff to keep the VM up)
cd ~/thinkabr
source ~/venv/bin/activate
mkdir -p runs logs

for level in high low medium xhigh; do
  echo "=== $(date '+%H:%M') level=$level" | tee -a logs/sweep.log
  python run_agent.py --level "$level" --all 2>&1 | tee -a logs/sweep.log
done

python grade.py runs/fixed_high.jsonl runs/fixed_low.jsonl runs/fixed_medium.jsonl runs/fixed_xhigh.jsonl \
  --json runs/fixed_summary.json 2>&1 | tee -a logs/sweep.log
echo "=== $(date '+%H:%M') sweep done" | tee -a logs/sweep.log

if [ "$1" != "--no-poweroff" ]; then
  sudo poweroff
fi
