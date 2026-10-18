"""Utilities for explicit record-by-record reviewer annotations, never auto-scoring.

Each decision below must be authored after reading the corresponding source output.
"""
import json
from datetime import datetime, timezone
from audit import HERE, load_rows


class ReviewWriter:
    def __init__(self, filename='codex_reviews.jsonl', reviewer='Codex primary reviewer'):
        self.path=HERE/filename
        self.rows={r['audit_id']:r for r in load_rows()}
        self.reviewer=reviewer
        self.items={r['audit_id']:r for r in map(json.loads,self.path.read_text().splitlines())} if self.path.exists() else {}

    def final(self, aid, *, decision, compliant, quote, rationale, failures=(), fact_invention=False,
              decision_acceptable=None, confidence='high', extra_evidence=()):
        row=self.rows[aid]
        evidence=[{'field':'final_answer','quote':quote,'explanation':rationale}]+list(extra_evidence)
        for e in evidence:
            assert e['quote'] in (row.get(e['field']) or ''), (aid,e['quote'])
        item=self.items.setdefault(aid,{'audit_id':aid})
        item.update(reviewer=self.reviewer,reviewed_at=datetime.now(timezone.utc).isoformat(),
                    source_raw_sha256=__import__('hashlib').sha256(row['raw_output'].encode()).hexdigest(),
                    review_note='AI-assisted semantic source review. Not independent human validation.')
        item['final']={'decision':decision,'decision_acceptable':(None if decision_acceptable=='uncertain' else decision in ('approve','deny','conditional') if decision_acceptable is None else decision_acceptable),
                       'compliance':'compliant' if compliant is True else 'non_compliant' if compliant is False else 'uncertain',
                       'failures':list(failures),'fact_invention':fact_invention,
                       'evidence':evidence,'rationale':rationale,'confidence':confidence}

    def trace(self, aid, *, state, conflict=False, fact_invention=False, quote, rationale,
              confidence='high', extra_evidence=()):
        row=self.rows[aid]
        assert row.get('reasoning_trace')
        evidence=[{'field':'reasoning_trace','quote':quote,'explanation':rationale}]+list(extra_evidence)
        for e in evidence:assert e['quote'] in (row.get(e['field']) or ''),(aid,e['quote'])
        item=self.items.setdefault(aid,{'audit_id':aid})
        item.update(reviewer=self.reviewer,reviewed_at=datetime.now(timezone.utc).isoformat(),
                    review_note='AI-assisted semantic source review. Not independent human validation.')
        item['trace']={'trace_state':state,'trace_conflict':conflict,'fact_invention':fact_invention,
                       'evidence':evidence,'rationale':rationale,'confidence':confidence}

    def save(self):
        with self.path.open('w') as f:
            for aid,item in sorted(self.items.items()):f.write(json.dumps(item,ensure_ascii=False)+'\n')
        print(self.path.name,len(self.items),'records',sum('final' in r for r in self.items.values()),'final reviews',sum('trace' in r for r in self.items.values()),'trace reviews')
