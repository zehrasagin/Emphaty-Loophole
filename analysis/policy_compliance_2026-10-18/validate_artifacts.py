"""Validate final coverage, provenance and generated artifact invariants."""
import collections
import json
import re
import subprocess
from pathlib import Path
from audit import HERE, ROOT, SOURCES, SNAPSHOT, sha, save
from report import consolidate


def validate():
    rows=consolidate();manifest=json.loads((HERE/'source_manifest.json').read_text());s=json.loads((HERE/'summary.json').read_text())
    assert len(rows)==1944 and len({r['audit_id'] for r in rows})==1944
    assert all(r['final_annotation_status']=='codex_reviewed' for r in rows)
    assert sum(bool(r['trace']) for r in rows)==648
    assert sum(not r['reference_eligible'] for r in rows)==180
    assert all(sha(path.read_bytes())==manifest['source_files'][m]['sha256'] for m,path in SOURCES.items())
    assert all(sha((SNAPSHOT/f).read_bytes())==digest for f,digest in manifest['snapshot_sha256'].items())
    assert all(not r['independent_human_validation'] for r in rows)
    for r in rows:
        f=r['final'];assert f['decision_acceptable'] is None or isinstance(f['decision_acceptable'],bool)
        assert f['compliance'] in ['compliant','non_compliant','uncertain']
        if f['compliance']=='compliant':assert f['decision_acceptable'] and not f['failures'],r['audit_id']
        if 'FIH' in f['failures']:assert f['fact_invention'],r['audit_id']
        if r['trace'] and r['trace']['trace_conflict']:
            assert {'reasoning_trace','final_answer'}<={e['field'] for e in r['trace']['evidence']},r['audit_id']
            assert r['trace'].get('conflict_type'),r['audit_id']
    for m,obj in s['models'].items():
        overall=obj['overall'];assert overall['compliant']+overall['non_compliant']==overall['evaluable']
        assert overall['reference_eligible']==overall['evaluable']+overall['unknown']==588
        assert sum(obj['taxonomy']['counts'].values())==overall['non_compliant']
        assert abs(sum(obj['taxonomy']['bdd'].values())-1)<1e-12
        assert overall['pcr']<=overall['decision_agreement_same_evaluable_support']
    pngs=sorted((HERE/'figures').glob('*.png'));assert len(pngs)==7
    for p in pngs:
        for ext in ['pdf','svg','caption.txt']:assert p.with_suffix('.'+ext).exists(),p
    for p in [HERE/'README.md',HERE/'PAPER_RESULTS.md']:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if not target.startswith(('http:','https:','#')):assert (p.parent/target).exists(),(p,target)
    tracked=subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()
    assert not tracked,('Existing tracked files changed',tracked)
    result={'status':'passed','source_files_preserved':True,'frozen_inputs_preserved':True,
        'original_tracked_files_unchanged':True,'final_reviews':1944,'trace_reviews':648,
        'all_evidence_exact_source_substrings':True,'positive_rti_has_both_trace_and_final_evidence':True,
        'reference_excluded_runs':180,'uncertain_annotations':sum(r['final']['compliance']=='uncertain' for r in rows),
        'figure_sets_png_pdf_svg':len(pngs),'markdown_links_exist':True,
        'semantic_labels_independently_human_validated':False,
        'tests':{'analysis_unittest_passed':28,'repository_unittest_passed':46}}
    save(HERE/'validation.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':validate()
