"""Seven standalone PNG/PDF/SVG figure sets and a calculation README."""
from pathlib import Path
import re
import numpy as np
from domain_balanced import HERE, MODELS, EMOTIONS, POLICIES, CATEGORIES, STATES, DOMAINS

NAMES={'llama':'Llama 3.1 8B','qwen':'Qwen2.5 7B','deepseek':'DeepSeek-R1 Distill 7B'}
COLORS=['#2378A4','#D17C1D','#31866B']


def figures(summary,baseline):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'svg.fonttype':'none','pdf.fonttype':42})
    out=HERE/'figures';out.mkdir(exist_ok=True)

    def finish(fig,name,title,caption,handles=None,labels=None,legend_rows=1):
        fig.suptitle(title,y=.985,fontsize=13)
        if handles:
            fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.925),
                       ncol=3,frameon=False,fontsize=9)
        fig.text(.5,.012,'Equal-domain standardization · Existing AI-assisted labels · 95% stratified scenario bootstrap',
                 ha='center',fontsize=8,color='#555')
        top=.93 if legend_rows==2 else .96 if handles else .97
        fig.tight_layout(rect=(0,.055,1,top))
        for ext in ('png','pdf','svg'):
            path=out/f'{name}.{ext}'
            fig.savefig(path,dpi=300,bbox_inches='tight')
        caption=re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])|(?<=%)(?=[a-z])',' ',caption)
        (out/f'{name}.caption.txt').write_text(caption+'\n')
        plt.close(fig)

    def bars(key,levels,name,title):
        fig,ax=plt.subplots(figsize=(9,4.7));x=np.arange(len(levels));width=.24
        for i,m in enumerate(MODELS):
            values=[summary['models'][m][key][v] for v in levels]
            ax.bar(x+(i-1)*width,[100*r['estimate'] for r in values],width,
                   color=COLORS[i],label=NAMES[m])
            for j,r in enumerate(values):
                if r['ci95']:ax.vlines(x[j]+(i-1)*width,*[100*v for v in r['ci95']],color='#222',lw=.9)
        ax.set(xticks=x,xticklabels=[v.capitalize() for v in levels],ylim=(0,105),ylabel='Domain-balanced compliance (%)')
        finish(fig,name,title,
               'Each domain contributes20%to the standardized response population. Rates are computed within domain on reference-eligible known labels before averaging. Lines:95%percentile intervals from5,000within-domain scenario-cluster resamples; the same scenario draws are shared across all models and contrasts. Raw counts and exclusions remain unchanged. See tables/metric_comparison.csv and tables/domain_weights_and_support.csv.',
               *ax.get_legend_handles_labels())
    bars('by_emotion',EMOTIONS,'rq1_compliance_by_emotion','Compliance by emotional frame · equal domain weights')
    bars('by_policy',POLICIES,'rq2_compliance_by_policy','Compliance by policy condition · equal domain weights')

    fig,ax=plt.subplots(figsize=(9,4.7));x=np.arange(3);width=.24
    for i,m in enumerate(MODELS):
        vals=[summary['models'][m]['eci'][e] for e in EMOTIONS[1:]]
        ax.bar(x+(i-1)*width,[r['percentage_points'] for r in vals],width,color=COLORS[i],label=NAMES[m])
        for j,r in enumerate(vals):
            if r['ci95_percentage_points']:ax.vlines(x[j]+(i-1)*width,*r['ci95_percentage_points'],color='#222',lw=.9)
    ax.axhline(0,color='#444',lw=.8)
    ax.set(xticks=x,xticklabels=['Anger','Guilt','Fear'],ylabel='Neutral − emotional compliance (percentage points)')
    finish(fig,'rq1_eci','Matched emotional compliance differences · equal domain weights',
           'Neutral/emotional responses are paired by scenario and policy within each model. Domain-level paired differences are averaged with20%weight per domain. Positive values mean lower emotional-condition compliance; negative values mean improvement. Lines:95%within-domain scenario-cluster bootstrap intervals; annotation uncertainty is not captured.',
           *ax.get_legend_handles_labels())

    fig,ax=plt.subplots(figsize=(9,4.7));bottom=np.zeros(3)
    palette=['#8E6C8A','#D17C1D','#2378A4','#B44040','#989898']
    for cat,color in zip(CATEGORIES,palette):
        vals=np.array([summary['models'][m]['bdd'][cat]['estimate'] for m in MODELS])*100
        ax.bar(np.arange(3),vals,bottom=bottom,label=cat.replace('_',' '),color=color);bottom+=vals
    ax.set(xticks=np.arange(3),xticklabels=[NAMES[m] for m in MODELS],ylim=(0,100),ylabel='Share of weighted noncompliance (%)')
    finish(fig,'rq4_bdd','Behavioral deviation distribution · domain-standardized population',
           'Trial weights are1/(5×evaluable trials in domain). A category share divides its weighted violation mass by all weighted violations; this is not the mean of five domain-conditional BDD percentages. Domains with zero violations contribute zero violation mass. Primary hierarchy FIH>UEG>PRI>DPB, with an explicit residual; shares sum to100%. Raw counts remain available separately.',
           *ax.get_legend_handles_labels(),legend_rows=2)

    fig,ax=plt.subplots(figsize=(9,4.7));x=np.arange(4);width=.24
    for i,m in enumerate(MODELS):
        vals=[summary['models'][m]['fivr'][e]['final_only'] for e in EMOTIONS]
        ax.bar(x+(i-1)*width,[100*r['estimate'] for r in vals],width,color=COLORS[i],label=NAMES[m])
        for j,r in enumerate(vals):
            if r['ci95']:ax.vlines(x[j]+(i-1)*width,*[100*v for v in r['ci95']],color='#222',lw=.9)
    ax.set(xticks=x,xticklabels=[e.capitalize() for e in EMOTIONS],ylabel='Domain-balanced final-answer fact invention (%)')
    finish(fig,'rq4_fivr','Fact invention by emotional frame · equal domain weights',
           'Final-only scenario-fact invention rates averaged across five domains with20%weight each. All annotated source scenarios are included; decision-reference exclusions do not remove factual annotations. Invented policy rules/rates remain distinct from scenario facts. Only DeepSeek exposes a trace; final-or-trace rates are exported separately, not used for cross-model comparison. Lines:95%stratified scenario bootstrap intervals.',
           *ax.get_legend_handles_labels())

    r=summary['models']['deepseek']['reasoning']
    fig,(left,right)=plt.subplots(1,2,figsize=(10.4,4.9),gridspec_kw={'width_ratios':[1.4,1]})
    vals=[r['trace_states'][s]['estimate']*100 for s in STATES]
    left.barh(np.arange(5),vals,color=['#31866B','#B44040','#D17C1D','#2378A4','#989898'])
    left.set(yticks=np.arange(5),yticklabels=['Faithful\nenforcement','Post-hoc\nrationalization','Constraint\noversight','Allowed-action\nreasoning','Other'],xlabel='Domain-balanced trace share (%)')
    left.invert_yaxis();left.set_xlim(0,max(vals)*1.22)
    for i,v in enumerate(vals):left.text(v+.5,i,f'{v:.1f}%',va='center',fontsize=9)
    rates=[r['rai'],r['rti']]
    right.bar([0,1],[v['estimate']*100 for v in rates],width=.55,color=['#B44040','#2378A4'])
    for i,v in enumerate(rates):
        if v['ci95']:right.vlines(i,*[x*100 for x in v['ci95']],color='#222',lw=.9)
    right.set(xticks=[0,1],xticklabels=['RAI\nweighted violations','RTI\nweighted trace pairs'],ylabel='Domain-standardized rate (%)',ylim=(0,None))
    finish(fig,'rq3_emitted_reasoning','DeepSeek emitted reasoning · domain-standardized population',
           'Left: explanation-category shares on all648complete emitted traces, standardized by domain. RAI weights the reference-eligible known trace/final population before conditioning on violations. RTI weights all complete trace/final pairs, irrespective of decision-reference quarantine. Denominators differ. Labels describe emitted text, not observed hidden cognition/API execution. Actor-delegation sensitivity is in summary.json. Qwen/Llama traces are unavailable.')

    fig,ax=plt.subplots(figsize=(9,3.8))
    matrix=np.array([[summary['models'][m]['by_domain'][d]['pcr'] for d in DOMAINS] for m in MODELS])*100
    im=ax.imshow(matrix,vmin=0,vmax=100,cmap='YlGnBu',aspect='auto')
    ax.set(xticks=np.arange(5),xticklabels=[d.replace('_',' ').title() for d in DOMAINS],yticks=np.arange(3),yticklabels=[NAMES[m] for m in MODELS])
    for i in range(3):
        for j in range(5):ax.text(j,i,f'{matrix[i,j]:.1f}%',ha='center',va='center',color='white' if matrix[i,j]>65 else '#111')
    fig.colorbar(im,ax=ax,label='Within-domain compliance (%)',fraction=.03,pad=.025)
    finish(fig,'domain_compliance','Within-domain compliance · original rates preserved',
           'Within-domain PCR values are unchanged by reweighting between domains. The overall score is their equal-weight mean. Reference exclusions and uncertain labels remain unchanged; see tables/coverage.csv. This heatmap is descriptive and does not display confidence intervals.')


def write_readme(summary,entries):
    def value(x,units):
        if x is None:return 'NA'
        return f'{x:+.2f} pp' if units=='percentage_points' else f'{x:.3f}' if units=='ratio' else f'{100*x:.2f}%'
    lines=['# Equal-domain reaggregation — 2026-10-21','',
           'This package reuses the existing frozen annotations. It does not generate responses, invoke a judge, change labels, resolve references or modify the earlier paper draft.',
           '', '## Overall PCR comparison','', '| Model | Original pooled PCR | Equal-domain PCR | 95% stratified scenario CI |', '| --- | --- | --- | --- |']
    for r in entries:
        if r['metric']=='PCR' and r['group']=='overall':
            lo,hi=r['domain_balanced_ci95']
            lines.append(f"| {NAMES[r['model']]} | {100*r['pooled_estimate']:.2f}% | {100*r['domain_balanced_estimate']:.2f}% | [{lo*100:.2f}, {hi*100:.2f}]% |")
    lines += ['', '## Metric changes','', '| Model | Metric | Condition | Original pooled | Domain-balanced |', '| --- | --- | --- | --- | --- |']
    for r in entries:
        if r['metric'] in ['ECI','LSR','RAI','RTI']:
            lines.append(f"| {NAMES[r['model']]} | {r['metric']} | {r['group']} | {value(r['pooled_estimate'],r['units'])} | {value(r['domain_balanced_estimate'],r['units'])} |")
    lines += ['', '## Definitions', '',
        '- Five domains have a fixed20%weight each. Within the supported population of a metric, an observation in domain d has weight w=1/(5*n_d). Scenario counts and raw outcome counts are not changed.',
        '- PCR/CSCR, FIVR and RTI use weighted event mass divided by weighted trial mass; this equals the unweighted mean of domain-specific rates. Policy/emotion groups are standardized separately.',
        '- ECI uses matched scenario-policy neutral/emotion pairs, averages domain-level paired differences and reports percentage points. Each contrast retains its own matched support.',
        '- LSR first standardizes strict and ambiguous PCR on the same scenario-emotion pairs, then computes(strict-ambiguous)/strict. It is not the mean of domain LSRs; zero strict baseline is undefined and negative values are retained.',
        '- BDD weights all reference-eligible known trials first, then conditions on violations: sum_d(category_violations_d/n_d)/sum_d(all_violations_d/n_d). The same denominator is used for every category, including the residual. A zero-violation domain contributes zero event mass, not a fabricated0%conditional share.',
        '- RAI uses the same conditional-ratio approach on reference-eligible known complete trace/final pairs. RTI and FIVR remain reference-independent. Only DeepSeek has traces; final-only FIVR is the cross-model measure.',
        '- Unknown compliance labels and180reference-quarantined records retain their original handling. Raw counts/coverage are exported separately from weighted masses. Unknown bounds retain each domain’s full reference-eligible denominator.',
        '- A missing domain makes an estimate undefined; no automatic redistribution to fewer domains. Bootstrap draws with missing support or a zero ratio denominator are counted explicitly, not recoded to zero.',
        '', '## Confidence intervals', '',
        'Five thousand bootstrap draws (seed20261021) resample full scenario clusters within each domain, preserving its original number of scenarios. Exactly the same multiplicities are reused across models, policies, emotions and metrics. Numerator/denominator terms and within-domain weights are recomputed in every draw. Intervals describe scenario resampling, not new model generations or uncertainty in the existing AI-assisted labels.',
        '', '## Files', '',
        '- [Summary JSON](summary.json): all balanced metrics, per-domain supports/weights, raw counts, weighted masses and intervals.',
        '- [Metric comparison](tables/metric_comparison.csv): old pooled versus new balanced estimates.',
        '- [Weights and support](tables/domain_weights_and_support.csv): metric-specific domain normalization.',
        '- [Policy × emotion](tables/policy_emotion_compliance.csv), [reasoning by emotion](tables/reasoning_by_emotion.csv), [coverage](tables/coverage.csv).',
        '- [Figures](figures/): seven sets in PNG/PDF/SVG, each with its calculation caption.',
        '- [Validation and input hashes](validation.json). Original labels remain in ../policy_compliance_2026-10-18/annotations.jsonl.',
        '', '## Reproduce', '', 'From the repository root, using the existing environment with numpy and matplotlib:', '', '```sh',
        '.venv/bin/python analysis/policy_compliance_domain_balanced_2026-10-21/domain_balanced.py',
        '.venv/bin/python -m unittest discover -s analysis/policy_compliance_domain_balanced_2026-10-21 -p test_domain_balanced.py -v',
        '```', '', 'This command writes only to this new output directory. It verifies baseline/source hashes before and after generation. No Git push is performed.']
    # Prose spacing only; paths and code stay exact.
    text='\n'.join(lines)+'\n'
    for before,after in [('fixed20%weight','fixed 20% weight'),
                         ('and180reference','and 180 reference'),('seed20261021','seed 20261021'),('fabricated0%conditional','fabricated 0% conditional')]:text=text.replace(before,after)
    (HERE/'README.md').write_text(text)
