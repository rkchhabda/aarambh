"""Test corporate action parser on all harvested corporate action files."""

import json
import glob
import re
from datetime import datetime

def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%d-%b-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            pass
    return None

def parse_corporate_actions():
    files = glob.glob('data/fundamentals/corporate_actions/*_ca.json')
    actions = []

    for f in files:
        sym = f.split('\\')[-1].replace('_ca.json', '')
        with open(f, 'r', encoding='utf-8') as jf:
            records = json.load(jf)

        for r in records:
            subj = r.get('subject') or ''
            ex_str = r.get('exDate') or ''
            ex_dt = parse_date(ex_str)
            if not ex_dt:
                continue

            multiplier = 1.0
            action_type = None

            # 1. Bonus: "Bonus N:D"
            bonus_match = re.search(r'bonus\s+(\d+)\s*:\s*(\d+)', subj, re.IGNORECASE)
            if bonus_match:
                n = float(bonus_match.group(1))
                d = float(bonus_match.group(2))
                multiplier *= (n + d) / d
                action_type = "BONUS"

            # 2. Split: "From Rs ... To Rs ..."
            split_match = re.search(r'(?:split|sub-division).*?from\s+(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?).*?to\s+(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?)', subj, re.IGNORECASE)
            if split_match:
                from_fv = float(split_match.group(1))
                to_fv = float(split_match.group(2))
                if to_fv > 0:
                    multiplier *= (from_fv / to_fv)
                    action_type = "SPLIT" if not action_type else f"{action_type}+SPLIT"

            if multiplier > 1.0:
                actions.append({
                    'symbol': sym,
                    'ex_date': ex_dt.strftime('%Y-%m-%d'),
                    'action_type': action_type,
                    'multiplier': multiplier,
                    'subject': subj
                })

    print(f"Total parsed splits/bonuses: {len(actions)}")
    # Sort by symbol, ex_date
    actions.sort(key=lambda x: (x['symbol'], x['ex_date']))
    for a in actions:
        print(f"  {a['symbol']:12} | Ex: {a['ex_date']} | Multiplier: {a['multiplier']:5.2f}x | {a['action_type']:10} | {a['subject']}")

if __name__ == '__main__':
    parse_corporate_actions()
