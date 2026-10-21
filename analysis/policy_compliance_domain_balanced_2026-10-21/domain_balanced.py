"""Domain-standardized reaggregation of frozen, existing semantic annotations.

No model/judge invocation, annotation edits, or baseline artifact writes.
Run from the repository root with .venv/bin/python and this file's path.
"""
from __future__ import annotations

import collections
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / 'policy_compliance_2026-10-18'
ROOT = HERE.parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(HERE / '.mpl_cache'))
sys.path.insert(0, str(BASELINE))
import numpy as np
import report as pooled

DOMAINS = ('airlines', 'customer_support', 'hotels', 'retail', 'telecom')
MODELS = pooled.MODELS
EMOTIONS = pooled.EMOTIONS
POLICIES = pooled.POLICIES
CATEGORIES = ('DPB', 'UEG', 'PRI', 'FIH', 'other_noncompliance')
STATES = ('faithful_enforcement', 'post_hoc_rationalization', 'constraint_oversight',
          'allowed_action_reasoning', 'other')
BOOTSTRAPS = 5000
SEED = 20261021


def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StratifiedDesign:
    """One shared resampling plan: scenarios drawn within each fixed domain.

    Whole scenario multiplicities are reused for every model, policy, emotion,
    metric and paired contrast. Ineligible rows never become eligible; their
    scenario may still be sampled, so missing-support draws remain visible.
    """
    def __init__(self, rows, *, domains=DOMAINS, repeats=BOOTSTRAPS, seed=SEED):
        self.domains = tuple(domains)
        self.repeats = repeats
        self.seed = seed
        membership = {}
        for r in rows:
            sid, domain = r['scenario_id'], r['domain']
            if domain not in self.domains:
                raise ValueError(f'Unexpected domain: {domain}')
            if sid in membership and membership[sid] != domain:
                raise ValueError(f'Scenario occurs in multiple domains: {sid}')
            membership[sid] = domain
        self.scenarios = {d: sorted(s for s, dd in membership.items() if dd == d)
                          for d in self.domains}
        self.index = {d: {s: i for i, s in enumerate(ss)} for d, ss in self.scenarios.items()}
        rng = np.random.default_rng(seed)
        self.multiplicities = {}
        for d, ss in self.scenarios.items():
            n = len(ss)
            if not n:
                raise ValueError(f'No source scenarios for domain {d}')
            # Each draw contains exactly the original number of source scenarios
            # in this domain; policies/emotions/models stay in the same cluster.
            draws = rng.integers(0, n, size=(repeats, n))
            counts = np.zeros((repeats, n), dtype=np.int32)
            np.add.at(counts, (np.arange(repeats)[:, None], draws), 1)
            self.multiplicities[d] = counts

    def metadata(self):
        return {'replicates': self.repeats, 'seed': self.seed,
                'unit': 'scenario cluster, stratified within fixed domain',
                'shared_across_models_and_metrics': True,
                'scenarios_per_domain': {d: len(ss) for d, ss in self.scenarios.items()},
                'draws_sha256': {d: hashlib.sha256(w.tobytes()).hexdigest()
                                for d, w in self.multiplicities.items()}}

    def for_domain(self, domain):
        """Reuse the exact same draws for a descriptive within-domain interval."""
        if domain not in self.domains:
            raise ValueError(domain)
        view = copy.copy(self)
        view.domains = (domain,)
        return view


def standardized_ratio(observations, numerator, denominator, design):
    """Ratio of equal-domain means, normalized within the metric's base support.

    w_i = 1 / (D * n_d) for supported observations in domain d.
    estimate = sum(w_i * numerator_i) / sum(w_i * denominator_i).
    For ordinary rates denominator_i=1, hence the mean of domain rates.
    For conditional BDD/RAI, the denominator is a violation indicator on the
    SAME evaluable-trial base. A domain with zero violations contributes zero
    mass, without an invented conditional rate or a silent change of weights.
    """
    domains = design.domains
    arrays = {d: np.zeros((len(design.scenarios[d]), 3), dtype=float) for d in domains}
    by_domain = {d: {'base_observations': 0, 'raw_numerator': 0.0, 'raw_denominator': 0.0}
                 for d in domains}
    for r in observations:
        d, sid = r['domain'], r['scenario_id']
        if d not in arrays or sid not in design.index[d]:
            raise ValueError(f'Observation is outside the frozen resampling design: {d}/{sid}')
        a, b = float(numerator(r)), float(denominator(r))
        if not np.isfinite(a) or not np.isfinite(b) or b < 0:
            raise ValueError('Metric terms must be finite; denominator terms cannot be negative')
        arrays[d][design.index[d][sid]] += [1, a, b]
        by_domain[d]['base_observations'] += 1
        by_domain[d]['raw_numerator'] += a
        by_domain[d]['raw_denominator'] += b
    missing = [d for d, v in by_domain.items() if not v['base_observations']]
    a_total = b_total = 0.0
    for d, v in by_domain.items():
        n = v['base_observations']
        v['domain_weight'] = 1 / len(domains)
        v['observation_weight'] = 1 / (len(domains) * n) if n else None
        v['domain_rate'] = v['raw_numerator'] / v['raw_denominator'] if v['raw_denominator'] else None
        if n:
            a_total += v['raw_numerator'] / n / len(domains)
            b_total += v['raw_denominator'] / n / len(domains)
    result = {'estimate': a_total / b_total if not missing and b_total > 0 else None,
              'ci95': None, 'base_observations': len(observations),
              'raw_numerator': sum(v['raw_numerator'] for v in by_domain.values()),
              'raw_denominator': sum(v['raw_denominator'] for v in by_domain.values()),
              'weighted_numerator_mass': a_total if not missing else None,
              'weighted_denominator_mass': b_total if not missing else None,
              'per_domain': by_domain, 'missing_domains': missing,
              'bootstrap_valid_draws': 0, 'bootstrap_missing_support_draws': 0,
              'bootstrap_zero_denominator_draws': 0}
    if missing:
        result['undefined_reason'] = 'At least one required domain has no supported observations; no reweighting to fewer domains.'
        return result
    a_draw = np.zeros(design.repeats)
    b_draw = np.zeros(design.repeats)
    support_ok = np.ones(design.repeats, dtype=bool)
    for d, a in arrays.items():
        totals = design.multiplicities[d] @ a
        n = totals[:, 0]
        support_ok &= n > 0
        with np.errstate(divide='ignore', invalid='ignore'):
            a_draw += totals[:, 1] / n / len(domains)
            b_draw += totals[:, 2] / n / len(domains)
    valid = support_ok & np.isfinite(a_draw) & np.isfinite(b_draw) & (b_draw > 0)
    result['bootstrap_missing_support_draws'] = int((~support_ok).sum())
    result['bootstrap_zero_denominator_draws'] = int((support_ok & ~(b_draw > 0)).sum())
    result['bootstrap_valid_draws'] = int(valid.sum())
    if result['estimate'] is not None and valid.any():
        result['ci95'] = [float(v) for v in np.quantile(a_draw[valid] / b_draw[valid], [.025, .975])]
    if b_total <= 0:
        result['undefined_reason'] = 'The weighted denominator is zero.'
    return result


def compliance(rows, design):
    valid = [r for r in rows if pooled.evaluable(r)]
    result = standardized_ratio(valid, pooled.success, lambda r: 1, design)
    eligible = [r for r in rows if r['reference_eligible']]
    result['coverage'] = {'recorded_runs': len(rows), 'reference_eligible': len(eligible),
                          'reference_excluded': len(rows)-len(eligible),
                          'evaluable': len(valid), 'unknown': len(eligible)-len(valid),
                          'raw_compliant': sum(pooled.success(r) for r in valid)}
    # Unknown-label bounds keep each domain's reference-eligible population fixed.
    result['unknown_lower_bound'] = standardized_ratio(
        eligible, pooled.success, lambda r: 1, design)['estimate']
    result['unknown_upper_bound'] = standardized_ratio(
        eligible, lambda r: pooled.success(r) if pooled.evaluable(r) else 1,
        lambda r: 1, design)['estimate']
    result['decision_agreement_lower_bound'] = standardized_ratio(
        valid, lambda r: int(r['final']['decision_acceptable'] is True), lambda r: 1, design)['estimate']
    result['decision_agreement_upper_bound'] = standardized_ratio(
        valid, lambda r: int(r['final']['decision_acceptable'] is not False), lambda r: 1, design)['estimate']
    return result


def within_domain(rows, domain, design):
    result = pooled.rate(rows)
    valid = [r for r in rows if pooled.evaluable(r)]
    result['scenario_cluster_ci95'] = standardized_ratio(
        valid, pooled.success, lambda r:1, design.for_domain(domain))['ci95']
    result['interval_method'] = 'same within-domain scenario multiplicities as balanced metrics'
    return result


def paired_rows(rows, contrast):
    """Unique matched cells, never pairing on scenario alone."""
    by = {}
    seen = set()
    for r in rows:
        key = (r['model_key'], r['scenario_id'], r['policy_type'], r['emotion'])
        if key in seen:
            raise ValueError(f'Duplicate experimental condition: {key}')
        seen.add(key)
        if pooled.evaluable(r):
            by[key] = r
    pairs = []
    for (m, sid, policy, emotion), r in by.items():
        if contrast in EMOTIONS[1:] and emotion == 'neutral':
            other = by.get((m, sid, policy, contrast))
        elif contrast == 'strict_vs_ambiguous' and policy == 'strict':
            other = by.get((m, sid, 'ambiguous', emotion))
        else:
            continue
        if other is not None:
            pairs.append({'domain': r['domain'], 'scenario_id': sid,
                          'left': pooled.success(r), 'right': pooled.success(other),
                          'left_audit_id': r['audit_id'], 'right_audit_id': other['audit_id'],
                          'policy_type': policy, 'emotion': emotion})
    return pairs


def eci(rows, emotion, design):
    pairs = paired_rows(rows, emotion)
    result = standardized_ratio(pairs, lambda r: r['left']-r['right'], lambda r: 1, design)
    result['percentage_points'] = result['estimate']*100 if result['estimate'] is not None else None
    result['ci95_percentage_points'] = [v*100 for v in result['ci95']] if result['ci95'] else None
    result['neutral_pcr_same_pairs'] = standardized_ratio(pairs, lambda r:r['left'], lambda r:1, design)['estimate']
    result['emotion_pcr_same_pairs'] = standardized_ratio(pairs, lambda r:r['right'], lambda r:1, design)['estimate']
    result['raw_neutral_pass_emotion_fail'] = sum(r['left']==1 and r['right']==0 for r in pairs)
    result['raw_neutral_fail_emotion_pass'] = sum(r['left']==0 and r['right']==1 for r in pairs)
    return result


def lsr(rows, design):
    pairs = paired_rows(rows, 'strict_vs_ambiguous')
    result = standardized_ratio(pairs, lambda r:r['left']-r['right'], lambda r:r['left'], design)
    result['strict_pcr_same_pairs'] = standardized_ratio(pairs, lambda r:r['left'], lambda r:1, design)['estimate']
    result['ambiguous_pcr_same_pairs'] = standardized_ratio(pairs, lambda r:r['right'], lambda r:1, design)['estimate']
    return result


def bdd(rows, design):
    base = [r for r in rows if pooled.evaluable(r)]
    return {cat: standardized_ratio(base, lambda r, c=cat:int(pooled.primary_failure(r)==c),
                                   lambda r:1-pooled.success(r), design) for cat in CATEGORIES}


def fivr(rows, design):
    finals = [r for r in rows if r['final']]
    either = [r for r in finals if r['model_key']!='deepseek' or r['trace']]
    return {'final_only': standardized_ratio(finals, lambda r:int(r['final']['fact_invention']), lambda r:1, design),
            'final_or_available_trace': standardized_ratio(either, lambda r:int(r['final']['fact_invention'] or bool((r['trace'] or {}).get('fact_invention'))), lambda r:1, design),
            'cross_model_comparison': 'Use final_only; Llama and Qwen expose no trace.'}


def reasoning(rows, design):
    complete = [r for r in rows if r['final'] and r['trace']]
    valid = [r for r in complete if pooled.evaluable(r)]
    violations = [r for r in valid if not pooled.success(r)]
    return {'rai': standardized_ratio(valid, lambda r:int(not pooled.success(r) and r['trace']['trace_state']=='post_hoc_rationalization'), lambda r:1-pooled.success(r), design),
            'rti': standardized_ratio(complete, lambda r:int(r['trace']['trace_conflict']), lambda r:1, design),
            'rti_excluding_actor_delegation': standardized_ratio(complete, lambda r:int(r['trace']['trace_conflict'] and r['trace'].get('conflict_type')!='actor_delegation'), lambda r:1, design),
            'trace_states': {state: standardized_ratio(complete, lambda r,s=state:int(r['trace']['trace_state']==s), lambda r:1, design) for state in STATES},
            'raw_trace_state_counts': dict(collections.Counter(r['trace']['trace_state'] for r in complete)),
            'raw_complete_trace_final_pairs': len(complete), 'raw_reference_eligible_known_violations':len(violations)}


def tracked_input_hashes():
    inputs = [p for p in BASELINE.rglob('*') if p.is_file() and
              not any(part in ('.mpl_cache', '__pycache__') for part in p.parts)]
    inputs += list(pooled.SOURCES.values())
    inputs += [pooled.ROOT/'results/experiments/clean_local_models_v09_20261014T233610Z'/f
               for f in json.loads((BASELINE/'source_manifest.json').read_text())['snapshot_sha256']]
    return {str(p.relative_to(ROOT)):sha_file(p) for p in sorted(set(inputs))}


def summarize(rows, design, baseline):
    result = {'schema_version':'domain-standardized-metrics-v1',
              'generated_at_utc':datetime.now(timezone.utc).isoformat(),
              'source_annotations':str((BASELINE/'annotations.jsonl').relative_to(ROOT)),
              'annotation_status':baseline['annotation_status'],
              'software':{'python':sys.version.split()[0],
                          'numpy':importlib.metadata.version('numpy'),
                          'matplotlib':importlib.metadata.version('matplotlib')},
              'aggregation':{'method':'ratio of equal-domain mean numerator/denominator terms',
                             'domain_weights':{d:1/len(design.domains) for d in design.domains},
                             'normalization':'within the supported base population for each metric/contrast',
                             'conditional_metrics':'BDD and RAI condition the balanced trial population on violations; do not average domain-conditional ratios.',
                             'missing_domain':'undefined, never silently redistribute its weight'},
              'bootstrap':design.metadata(), 'coverage':baseline['coverage'], 'models':{}}
    for model in MODELS:
        sub = [r for r in rows if r['model_key']==model]
        result['models'][model] = {
            'overall':compliance(sub,design),
            'by_emotion':{e:compliance([r for r in sub if r['emotion']==e],design) for e in EMOTIONS},
            'by_policy':{p:compliance([r for r in sub if r['policy_type']==p],design) for p in POLICIES},
            'policy_emotion':{p:{e:compliance([r for r in sub if r['policy_type']==p and r['emotion']==e],design) for e in EMOTIONS} for p in POLICIES},
            'by_domain':{d:within_domain([r for r in sub if r['domain']==d],d,design) for d in design.domains},
            'eci':{e:eci(sub,e,design) for e in EMOTIONS[1:]},
            'lsr':{'all_frames':lsr(sub,design),'emotional_frames':lsr([r for r in sub if r['emotion']!='neutral'],design)},
            'bdd':bdd(sub,design),
            'fivr':{e:fivr([r for r in sub if r['emotion']==e],design) for e in EMOTIONS},
            'reasoning':reasoning(sub,design) if model=='deepseek' else None,
        }
    result['reasoning_by_emotion'] = {e:reasoning([r for r in rows if r['model_key']=='deepseek' and r['emotion']==e],design) for e in EMOTIONS}
    by_condition = collections.defaultdict(dict)
    for r in rows:
        by_condition[r['scenario_id'],r['policy_type'],r['emotion']][r['model_key']]=r
    common = [g for g in by_condition.values() if set(g)==set(MODELS) and all(pooled.evaluable(r) for r in g.values())]
    result['all_model_common_support'] = {'conditions_per_model':len(common),'models':{
        m:compliance([g[m] for g in common],design) for m in MODELS}}
    return result


def metric_entries(summary, baseline):
    """Comparable metrics with unchanged pooled estimates, definitions and raw support."""
    entries=[]
    for m,obj in summary['models'].items():
        old=baseline['models'][m]
        def add(metric,group,res,old_value,units='proportion'):
            scale=100 if units=='percentage_points' else 1
            entries.append({'model':m,'metric':metric,'group':group,'units':units,
                            'pooled_estimate':old_value,
                            'domain_balanced_estimate':None if res['estimate'] is None else scale*res['estimate'],
                            'domain_balanced_ci95':None if res['ci95'] is None else [scale*v for v in res['ci95']],
                            'change':None if res['estimate'] is None or old_value is None else scale*res['estimate']-old_value,
                            **{k:res[k] for k in ['base_observations','raw_numerator','raw_denominator','weighted_numerator_mass','weighted_denominator_mass','bootstrap_valid_draws','bootstrap_missing_support_draws','bootstrap_zero_denominator_draws']},
                            'per_domain':res['per_domain']})
        add('PCR','overall',obj['overall'],old['overall']['pcr'])
        for e in EMOTIONS:
            add('PCR',e,obj['by_emotion'][e],old['by_emotion'][e]['pcr'])
            add('FIVR_final',e,obj['fivr'][e]['final_only'],old['fivr'][e]['final_fivr'])
            add('FIVR_final_or_trace',e,obj['fivr'][e]['final_or_available_trace'],old['fivr'][e]['final_or_trace_fivr'])
        for p in POLICIES:add('CSCR',p,obj['by_policy'][p],old['by_policy'][p]['pcr'])
        for e in EMOTIONS[1:]:add('ECI',e,obj['eci'][e],old['eci'][e]['eci_percentage_points'],'percentage_points')
        for scope in ['all_frames','emotional_frames']:add('LSR',scope,obj['lsr'][scope],old['lsr_'+scope]['lsr'],'ratio')
        for cat in CATEGORIES:add('BDD',cat,obj['bdd'][cat],old['taxonomy']['bdd'][cat])
        if m=='deepseek':
            for metric in ['rai','rti','rti_excluding_actor_delegation']:
                add(metric.upper(),'all_frames',obj['reasoning'][metric],old['reasoning'][metric])
    return entries


def export(summary, baseline, rows):
    json.dumps(summary,allow_nan=False)  # Never serialize NaN/Infinity as pseudo-JSON.
    entries=metric_entries(summary,baseline)
    pooled.csv_write(HERE/'tables/metric_comparison.csv',[{k:v for k,v in r.items() if k!='per_domain'} for r in entries])
    pooled.csv_write(HERE/'tables/domain_weights_and_support.csv',[
        {'model':r['model'],'metric':r['metric'],'group':r['group'],'domain':d,**values}
        for r in entries for d,values in r['per_domain'].items()])
    pooled.csv_write(HERE/'tables/policy_emotion_compliance.csv',[
        {'model':m,'policy_type':p,'emotion':e,'pcr':res['estimate'],'ci95':res['ci95'],**res['coverage']}
        for m,obj in summary['models'].items() for p,emotions in obj['policy_emotion'].items() for e,res in emotions.items()])
    pooled.csv_write(HERE/'tables/reasoning_by_emotion.csv',[
        {'emotion':e,'metric':metric,'estimate':res['estimate'],'ci95':res['ci95'],'raw_numerator':res['raw_numerator'],'raw_denominator':res['raw_denominator'],'base_observations':res['base_observations']}
        for e,obj in summary['reasoning_by_emotion'].items() for metric,res in obj.items() if metric in ['rai','rti','rti_excluding_actor_delegation']])
    # Individual source labels are not duplicated or rewritten. This table records
    # reference eligibility and the unchanged counts, not new judge decisions.
    pooled.csv_write(HERE/'tables/coverage.csv',[
        {'model':m,'domain':d,'recorded':len(sub),'scenario_ids':len({r['scenario_id'] for r in sub}),
         'reference_excluded':sum(not r['reference_eligible'] for r in sub),
         'uncertain':sum(r['final']['compliance']=='uncertain' for r in sub),
         'evaluable':sum(pooled.evaluable(r) for r in sub)}
        for m in MODELS for d in DOMAINS
        for sub in [[r for r in rows if r['model_key']==m and r['domain']==d]]])
    pooled.save(HERE/'summary.json',summary)
    return entries


def validate(summary, rows, before, entries):
    after=tracked_input_hashes()
    assert after==before, 'A frozen source or baseline artifact changed'
    assert len(rows)==1944 and sum(bool(r['trace']) for r in rows)==648
    assert len({r['scenario_id'] for r in rows})==54
    assert sum(not r['reference_eligible'] for r in rows)==180
    assert sum(r['final']['compliance']=='uncertain' for r in rows)==11
    assert len({r['audit_id'] for r in rows})==1944
    for m in MODELS:
        sub=[r for r in rows if r['model_key']==m]
        assert len(sub)==648
        assert len({(r['scenario_id'],r['policy_type'],r['emotion']) for r in sub})==648
    assert all(not r['missing_domains'] for obj in summary['models'].values() for r in [obj['overall'],*obj['by_emotion'].values(),*obj['by_policy'].values()])
    for model,obj in summary['models'].items():
        assert abs(sum(r['estimate'] for r in obj['bdd'].values())-1)<1e-12
        assert abs(obj['overall']['estimate']-sum(r['pcr'] for r in obj['by_domain'].values())/len(DOMAINS))<1e-12
        for d,v in obj['overall']['per_domain'].items():
            assert abs(v['observation_weight']*v['base_observations']-.2)<1e-12
    assert all(r['bootstrap_valid_draws']>0 for r in entries)
    figures=list((HERE/'figures').glob('*.png'))
    assert len(figures)==7
    for p in figures:
        assert all(p.with_suffix('.'+ext).exists() for ext in ['pdf','svg','caption.txt'])
    import re
    for target in re.findall(r'\]\(([^)]+)\)',(HERE/'README.md').read_text()):
        assert (HERE/target).exists(),target
    return {'status':'passed','source_and_baseline_hashes_preserved':True,
            'source_and_baseline_files_checked':len(before),
            'final_reviews':len(rows),'trace_reviews':648,'scenarios':54,
            'reference_excluded_runs':180,'uncertain_labels':11,
            'all_five_domain_weights':.2,'bdd_sums_to_one':True,
            'seven_figure_sets_png_pdf_svg':True,'readme_links_valid':True,
            'all_numeric_results_finite':True,
            'model_or_judge_calls':0,'paper_results_md_modified':False,
            'baseline_input_sha256':before}


def main():
    before=tracked_input_hashes()
    manifest=json.loads((BASELINE/'source_manifest.json').read_text())
    for m,path in pooled.SOURCES.items():
        if sha_file(path)!=manifest['source_files'][m]['sha256']:
            raise ValueError(f'Original experiment source changed since the frozen audit: {m}')
    snapshot=ROOT/'results/experiments/clean_local_models_v09_20261014T233610Z'
    for name,digest in manifest['snapshot_sha256'].items():
        if sha_file(snapshot/name)!=digest:
            raise ValueError(f'Frozen experimental inputs changed: {name}')
    rows=pooled.consolidate()
    saved=pooled.read_jsonl(BASELINE/'annotations.jsonl')
    if rows!=saved:
        raise ValueError('Saved merged annotations differ from consolidated reviews; reconcile before reaggregation.')
    baseline=json.loads((BASELINE/'summary.json').read_text())
    for m in MODELS:
        actual=pooled.rate([r for r in rows if r['model_key']==m])
        for field in ['recorded_runs','evaluable','compliant','non_compliant','unknown','reference_excluded']:
            if actual[field]!=baseline['models'][m]['overall'][field]:
                raise ValueError(f'Baseline summary is stale relative to source annotations: {m}/{field}')
    design=StratifiedDesign(rows)
    summary=summarize(rows,design,baseline)
    entries=export(summary,baseline,rows)
    from balanced_figures import figures, write_readme
    figures(summary,baseline)
    write_readme(summary,entries)
    validation=validate(summary,rows,before,entries)
    pooled.save(HERE/'validation.json',validation)
    for m,obj in summary['models'].items():
        print(f"{m}: pooled PCR={baseline['models'][m]['overall']['pcr']:.6f}; equal-domain PCR={obj['overall']['estimate']:.6f}")
    print('Validated: original outputs, semantic labels and baseline artifacts preserved.')


if __name__=='__main__':main()
