#!/bin/bash
cd ~/thinkabr && source ~/venv/bin/activate && mkdir -p logs
for lv in low medium high xhigh; do
  [ -f runs/fixed_${lv}_v2.jsonl ] || python -c "import json; rows=[json.loads(l) for l in open('runs/fixed_$lv.jsonl') if l.strip()]; keep=[r for r in rows if r['status'].startswith('submitted')]; open('runs/fixed_${lv}_v2.jsonl','w').write(''.join(json.dumps(r)+'\n' for r in keep)); print('$lv kept', len(keep))"
done
for lv in low medium high xhigh; do
  python run_agent.py --level $lv --all --out runs/fixed_${lv}_v2.jsonl 2>&1 | tee -a logs/rerun.log
done
python grade.py runs/fixed_{high,low,medium,xhigh}_v2.jsonl --json runs/fixed_summary_v2.json > /tmp/out.txt 2>&1
echo "=== rerun done $(date '+%H:%M')" | tee -a logs/rerun.log
