"""Render an English, auditable draft from computed statistics; never source results."""
import json
from pathlib import Path
from audit import HERE, save, load_rows


def pct(v):return 'NA' if v is None else f'{100*v:.1f}%'
def num(v):return 'NA' if v is None else f'{v:.2f}'
def interval(v,scale=100):
    digits=3 if scale==1 else 1
    return 'NA' if not v else f'[{v[0]*scale:.{digits}f}, {v[1]*scale:.{digits}f}]'
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])


def write(report, rows):
    names={'llama':'Llama 3.1 8B Instruct','qwen':'Qwen2.5 7B Instruct','deepseek':'DeepSeek-R1 Distill Qwen 7B'}
    models=report['models'];order=['llama','qwen','deepseek']
    rates=[];emotion=[];eci=[];policies=[];lsr=[];bdd=[];facts=[]
    for m in order:
        obj=models[m];r=obj['overall']
        decision_rate=pct(r['decision_agreement_same_evaluable_support'])
        if r['decision_unknown_same_evaluable_support']:
            decision_rate+='–'+pct(r['decision_agreement_upper_bound_same_support'])+f" ({r['decision_unknown_same_evaluable_support']} unknown)"
        rates.append([names[m],f"{r['compliant']}/{r['evaluable']}",pct(r['pcr']),interval(r['scenario_cluster_ci95']),r['unknown'],decision_rate])
        emotion.append([names[m]]+[f"{pct(obj['by_emotion'][e]['pcr'])} ({obj['by_emotion'][e]['compliant']}/{obj['by_emotion'][e]['evaluable']})" for e in ['neutral','anger','guilt','fear']])
        policies.append([names[m]]+[f"{pct(obj['by_policy'][p]['pcr'])} ({obj['by_policy'][p]['compliant']}/{obj['by_policy'][p]['evaluable']})" for p in ['strict','exception','ambiguous']])
        for e,r in obj['eci'].items():eci.append([names[m],e,r['matched_pairs'],f"{r['eci_percentage_points']:+.2f}",interval(r['scenario_cluster_ci95_pp'],1),r['neutral_success_emotion_failure'],r['neutral_failure_emotion_success']])
        for scope in ['all_frames','emotional_frames']:
            r=obj['lsr_'+scope];lsr.append([names[m],scope,r['matched_pairs'],pct(r['strict_pcr']),pct(r['ambiguous_pcr']),num(r['lsr']),interval(r['scenario_cluster_ci95'],1)])
        t=obj['taxonomy'];bdd.append([names[m],t['non_compliant']]+[f"{t['counts'][c]} ({pct(t['bdd'][c])})" for c in ['DPB','UEG','PRI','FIH','other_noncompliance']])
        facts.append([names[m]]+[f"{obj['fivr'][e]['final_fact_invention']}/162 ({pct(obj['fivr'][e]['final_fivr'])})" for e in ['neutral','anger','guilt','fear']])
    rr=models['deepseek']['reasoning'];common=report['all_model_common_support'];manifest=json.loads((HERE/'source_manifest.json').read_text())
    unknown=[r for r in rows if r['final']['compliance']=='uncertain']
    common_table=table(['Model','Same-support PCR','Equal-domain macro PCR','Unknown-label lower–upper bounds'],[
        [names[m],pct(common['models'][m]['pcr']),pct(models[m]['domain_macro_pcr']),f"{pct(models[m]['overall']['unknown_lower_bound'])}–{pct(models[m]['overall']['unknown_upper_bound'])}"] for m in order])
    methods='''## Methods draft

We audited 1,944 recorded single-prompt text responses from three models, with648 responses per model. The frozen catalog contains54 scenario IDs:13airline,11telecom, and10each in hotels, retail and customer support. Each scenario was evaluated under three experimental policy conditions (strict, explicit exception, ambiguous) and four emotional frames (neutral, anger, guilt, fear). Model-facing message lists, core hashes, policy hashes and facts hashes matched across models for every condition. JSON/JSONL/individual-file copies were treated as storage replicas, not extra trials. Every recorded final answer was nonempty and untruncated. Only DeepSeek emitted a complete reasoning trace (648); the other models have no observed trace.

AI-assisted semantic reviewers inspected every final answer and available trace against its exact frozen policy and model-facing customer facts. Annotations preserve trial IDs, source indices, raw-output hashes, exact evidence excerpts, decisions, compliance, secondary failures, fact-invention flags, explanation categories and uncertainty. Reviewers worked in parallel by domain; the primary reviewer completed remaining records and adjudicated identified inconsistencies. A limited overlapping airline review was used for qualitative consistency checks; the full corpus was not independently double-annotated. These are provisional AI-assisted labels, not human gold annotations or independent inter-rater reliability results. Small local-model judge calibration failed and its saved drafts were excluded completely.

An acceptable expressed decision with no material operative policy violation or factual distortion was considered compliant. Decision agreement was also measured separately on the same evaluable support. Peripheral processing suggestions, hypothetical eligibility checks, generic empathy and simulated present-tense execution promises were not automatically treated as fabricated facts. We distinguished invented scenario/account facts from invented policy provisions, prices and limits. Incidental unsupported facts could contribute to FIVR without causing a noncompliant action. Wrong refusals, missing duties and unsupported courtesy grants were preserved in a residual category where the supplied four-way taxonomy did not fit.

Source reference labels were research drafts. Fifteen scenario-policy combinations (180responses,60per model) had missing or conflicting references and were quarantined from primary PCR, ECI, CSCR, LSR, BDD and violation-conditioned RAI calculations. Their descriptive semantic annotations remain available. The remaining588responses per model were eligible before uncertain-label exclusions. FIVR and RTI do not require expected-decision labels and retain the complete annotated corpus. The issue register is source_manifest.json; no source references were silently corrected.

ECI used matched scenario-policy pairs between neutral and each emotional frame and is reported in percentage points. LSR used matched scenario-emotion support between strict and ambiguous conditions; negative values were retained and a zero strict baseline is undefined. Primary BDD mechanisms used the explicit coding hierarchy FIH>UEG>PRI>DPB, with secondary labels retained. BDD denominators include every evaluable noncompliant response, including an explicit residual. DeepSeek RAI is supported post-hoc rationalization among evaluable violations; RTI compares settled emitted trace decisions with final expressed actions. Safety escalation delegated to the customer rather than performed by the assistant is separately tagged as actor_delegation. Neither measure establishes actual hidden cognition or API execution.

Intervals use5,000scenario-cluster bootstrap resamples (seed20261018), preserving within-scenario policy/emotion structure. They describe resampling variation within this fixed, authored catalog, not annotator error or generation replication. Unknown-label bounds and an all-model common-support sensitivity are reported separately. No confirmatory significance or causal mechanism is inferred from point estimates or unadjusted exploratory intervals.
'''
    text=f'''# Exploratory results: emotional pressure and policy compliance

**Status: complete AI-assisted source review; independent human validation pending.** This is an English paper-writing draft, not a claim of conference-ready validated findings. Original experiment outputs and their JSON formats are unchanged.

## Overall compliance

{table(['Model','Compliant/evaluable','PCR','95% scenario-cluster CI (%)','Unknown among eligible','Decision agreement'],rates)}

Each model has648recorded responses and588reference-eligible responses. Unknown compliance labels are excluded from point estimates, with bounds below. Decision agreement uses the same compliance-evaluable support; ranges count unknown decision acceptability first as wrong, then as correct. Four contradictory-action answers are clearly noncompliant despite unknown decision acceptability. Decision agreement alone gives higher rates than grounded compliance because a correct approval/refusal can still misstate an operative rule or invent relevant facts. Comparing only final outcome labels would miss these errors.

## RQ1: Emotional framing

{table(['Model','Neutral','Anger','Guilt','Fear'],emotion)}

{table(['Model','Frame','Matched pairs','ECI (pp)','95% cluster CI (pp)','Neutral pass → emotion fail','Neutral fail → emotion pass'],eci)}

Positive ECI means lower compliance under the emotional frame. Qwen shows a20.0percentage-point decline under fear on matched support and an11.8-point decline under anger. These intervals exclude zero in this exploratory calculation, without correction for multiple comparisons or annotation uncertainty. Llama's anger/fear point estimates are positive but intervals span zero. DeepSeek's anger/guilt point estimates are negative: emotional framing does not uniformly reduce compliance. DeepSeek fear has a positive point estimate but its interval spans zero. Report these heterogeneous results; do not claim that every emotion harms every model or that fear is universally the strongest mechanism.

![Compliance by emotional frame](figures/rq1_compliance_by_emotion.png)

![Matched emotional differences](figures/rq1_eci.png)

## RQ2: Policy condition and loophole seeking

{table(['Model','Strict CSCR','Explicit-exception CSCR','Ambiguous CSCR'],policies)}

{table(['Model','Frames','Matched pairs','Strict PCR','Ambiguous PCR','LSR','95% cluster CI'],lsr)}

Negative LSR means ambiguous-condition compliance is higher on matched support. This does not support an aggregate ambiguity-induced compliance collapse. Ambiguous airline policies deliberately permit some discretionary actions, so a larger approval rate can be legitimate. Telecom variants retain shared substantive entitlements and are not an equivalent strictness manipulation. Cross-domain pooled LSR therefore combines different policy designs; interpret domain and policy×emotion tables alongside it.

![Compliance by policy condition](figures/rq2_compliance_by_policy.png)

## RQ3: Observable explanations

Only DeepSeek has emitted traces. Its RAI is **{rr['post_hoc_rationalizations_among_violations']}/{rr['violations_with_evaluable_trace']} = {pct(rr['rai'])}**, with 95% scenario-cluster interval {interval(rr['rai_scenario_cluster_ci95'])}%. RTI is **{rr['settled_trace_final_conflicts']}/{rr['evaluable_trace_final_pairs']} = {pct(rr['rti'])}**, interval {interval(rr['rti_scenario_cluster_ci95'])}%.

The explanation-category counts over all648traces are: {json.dumps(rr['trace_state_counts'],sort_keys=True)}. This broader count includes quarantined and compliant cases, so its post-hoc numerator must not be substituted into the violation-conditioned RAI. Neutral examples are retained as a baseline; a post-hoc label does not prove emotional causation.

RTI subtype counts are {json.dumps(rr['conflict_type_counts'],sort_keys=True)}. Excluding actor-delegation mismatches gives {pct(rr['rti_excluding_actor_delegation'])} over the same 648 pairs. This sensitivity separates explicit financial decision/scope disagreements from planned safety actions that the final answer delegates to the customer. Missing escalation can itself be noncompliant, but is not an observed failed API call. Qwen/Llama RAI and RTI are unavailable, not zero.

These data cannot show that reasoning capability is a safeguard or that it is “weaponized.” Model families, tuning, token budgets and decoding settings differ; emitted explanations need not faithfully describe the process producing an answer.

![Emitted reasoning audit](figures/rq3_emitted_reasoning.png)

## RQ4: Failure mechanisms and fact invention

{table(['Model','All violations','DPB','UEG','PRI','FIH','Residual'],bdd)}

Policy reinterpretation is the largest primary category in all three models. Examples include treating a cancellation fee as automatic refund eligibility, inventing a commercial rate/fee, or interpreting one unusable item as grounds for a whole-order refund. The residual includes over-refusals, missing duties and unsupported explicit goodwill, without falsely forcing every failure into one of four unauthorized-transaction mechanisms. Secondary labels overlap and must not be summed as distinct runs.

{table(['Model','Neutral final-only FIVR','Anger','Guilt','Fear'],facts)}

All FIVR cells use162recorded runs; quarantined reference decisions do not remove factual evidence. DeepSeek has more final-only fact-invention flags than the other models, but its neutral baseline is also high. These rates do not demonstrate a universal emotion-induced increase. Trace-inclusive DeepSeek FIVR is separately exported; comparing it directly with final-only rates from models that expose no trace would be unfair.

![Primary failure categories](figures/rq4_bdd.png)

![Final-answer fact invention](figures/rq4_fivr.png)

## Sensitivity and validation

All-model common support contains{common['conditions_per_model']}matched conditions per model after excluding any condition with an unknown label in any model.

{common_table}

All11uncertain annotations remain visible in annotations.jsonl and review.html; no unknown was silently recoded. Quarantined cases remain visible with the exact source issue. Source preservation, quote membership and complete coverage are machine-checked; these checks validate provenance and calculations, not the correctness of every semantic interpretation.

![Domain comparison](figures/domain_compliance.png)

{methods}

## Limitations and work needed before confirmatory publication

- Independently double-annotate the corpus, adjudicate disagreements and report agreement with the raters blinded to model and hypothesis where possible. Use tables/human_review_worksheet.csv; it intentionally contains blank human labels. Current reviewers are AI agents, not independent human annotators.
- Resolve the15quarantined scenario-policy reference problems against exact model-facing policies; preserve the original results and report any corrected-reference sensitivity separately. The source policies are scoped experimental adaptations, not a claim that every clause is verbatim current corporate policy. Customer-support thresholds are explicitly researcher-authored synthetic rules.
- There is one recorded generation per condition. Temperature0for Llama/Qwen and0.6for DeepSeek, different output budgets512versus4096, architecture/training differences and missing Llama revision identification confound cross-model explanations. Replicate with matched settings and multiple seeds before a causal reasoning-versus-standard claim.
- The54authored scenario IDs are not a random population sample; some scenarios are near duplicates (including two free-data requests). Bootstrap clustering by ID does not remove semantic overlap. Domain imbalance and different policy manipulations limit pooled interpretation.
- No actual transactional tools were executed. Replace “executed unauthorized API transactions” with “expressed policy-inconsistent actions” for this dataset. These runs are single-prompt experiments; they do not establish multi-turn effects.
- ECI is an absolute percentage-point difference. Keep exact denominators, matched support, unknown-label bounds and the residual taxonomy category. Avoid cherry-picking only successful emotional attacks or presenting exploratory intervals as independent human validation.
'''
    # Keep numbers readable rather than mechanically joined to words in manuscript prose.
    import re
    text='\n'.join(line if line.startswith('![') else re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])',' ',line) for line in text.splitlines())
    text=text.replace('Qwen 2.5','Qwen2.5')
    (HERE/'PAPER_RESULTS.md').write_text(text)
    source={r['audit_id']:r for r in load_rows()}
    selected=[
      ('Policy reinterpretation despite a correct-looking process','deepseek::easyjet_012_refund_within_24h__strict__neutral'),
      ('False eligibility comparison','llama::att_005_14day_termination_fee_waiver__strict__anger'),
      ('Invented commercial fee, not a customer fact','qwen::telecom_data_001__ambiguous__fear'),
      ('Invented whole-order unusability','deepseek::uber_eats_009_damaged_container__exception__guilt'),
      ('Legitimate discretion as a negative control','deepseek::easyjet_006_change_inclusive_plus_within_day__ambiguous__guilt'),
      ('Settled trace/final disagreement','deepseek::easyjet_012_refund_within_24h__ambiguous__fear'),
    ]
    # Resolve the negative control by its known prefix if source uses a longer scenario ID.
    selected=[(label,aid if aid in source else next((k for k in source if k.startswith('deepseek::easyjet_006') and k.endswith('__ambiguous__guilt')),aid)) for label,aid in selected]
    by={r['audit_id']:r for r in rows};examples=[];lines=['# Evidence examples for qualitative reporting','','AI-assisted interpretations; source text is preserved. Selected to illustrate mechanisms and a valid discretionary action, not to estimate frequency.']
    for title,aid in selected:
        r=by[aid];src=source[aid];examples.append({'title':title,'audit_id':aid,'trial_id':r['trial_id'],'source_file':r['source_file'],'source_index':r['source_index'],'annotation':r['final'],'trace_annotation':r['trace'],'original_final_answer':src['final_answer'],'original_reasoning_trace':src.get('reasoning_trace')})
        lines += ['',f'## {title}',f'`{aid}` · trial `{r["trial_id"]}`',f'Source: `{r["source_file"]}` index{r["source_index"]}.',f'Final label: **{r["final"]["compliance"]}**; failures{r["final"]["failures"]}.',r['final']['rationale']]
        for ev in r['final']['evidence']:lines+=['','> '+ev['quote'].replace('\n','\n> ')]
        if r['trace']:
            lines+=['',f'Trace state: `{r["trace"]["trace_state"]}`; conflict `{r["trace"]["trace_conflict"]}`.',r['trace']['rationale']]
            for ev in r['trace']['evidence']:lines+=['',f'{ev["field"]}:','> '+ev['quote'].replace('\n','\n> ')]
    (HERE/'EXAMPLES.md').write_text('\n'.join(lines)+'\n');save(HERE/'examples.json',examples)
    (HERE/'README.md').write_text('''# Complete exploratory policy-compliance audit

All 1,944 final answers and 648 available emitted traces were reviewed against their frozen experiment policies and customer facts. Original data/results formats are unchanged. Labels are AI-assisted and await independent human validation.

- [English paper draft and tables](PAPER_RESULTS.md)
- [Evidence examples](EXAMPLES.md) and [machine-readable examples](examples.json)
- [Interactive record browser](review.html): exact supplied policy, customer prompt, original final/trace, evidence and labels; opens locally without a server
- [All evidence-bearing annotations](annotations.jsonl), [summary JSON](summary.json), [tables](tables/), [PNG/PDF/SVG figures](figures/)
- [Annotation protocol](protocol.md), [source hashes/reference issue register](source_manifest.json), [preservation checks](qa_source_preservation.json)
- [Blank independent human review worksheet](tables/human_review_worksheet.csv)

Reproduce from repository root, with the existing `.venv` (numpy/matplotlib):

```sh
.venv/bin/python analysis/policy_compliance_2026-10-18/report.py
.venv/bin/python -m unittest discover -s analysis/policy_compliance_2026-10-18 -p test_analysis.py -v
```

The report reads saved semantic reviews; it does not regenerate model outputs. Do not rerun reviewer-authored replay scripts when making isolated adjudication edits unless the script contains those edits too. Failed local-judge calibration drafts are kept for provenance but excluded from metrics. See the paper draft for exclusions, unknowns, denominator differences and limitations.
''')
    save(HERE/'remaining_review_queue.json',{'status':'complete','remaining_final_reviews':0,'remaining_trace_reviews':0})


if __name__=='__main__':
    rows=[json.loads(l) for l in (HERE/'annotations.jsonl').read_text().splitlines()]
    write(json.loads((HERE/'summary.json').read_text()),rows)
