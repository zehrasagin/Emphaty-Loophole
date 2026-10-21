"""Statistical invariants with unequal domains, matched cells and missing support."""
import copy
import json
from pathlib import Path
import unittest
import numpy as np

import domain_balanced as b


def row(sid, domain, *, model='deepseek', policy='strict', emotion='neutral',
        compliant=True, eligible=True, failures=(), fi=False, state='other', conflict=False):
    return {'scenario_id':sid,'domain':domain,'model_key':model,'policy_type':policy,'emotion':emotion,
            'audit_id':f'{model}::{sid}__{policy}__{emotion}',
            'reference_eligible':eligible,
            'final':{'compliance':'uncertain' if compliant is None else 'compliant' if compliant else 'non_compliant',
                     'decision_acceptable':compliant,'failures':list(failures),'fact_invention':fi},
            'trace':{'trace_state':state,'trace_conflict':conflict,'fact_invention':False}}


def design(rows, domains=('large','small'), repeats=1000, seed=3):
    return b.StratifiedDesign(rows,domains=domains,repeats=repeats,seed=seed)


class StandardizationTests(unittest.TestCase):
    def test_domains_equal_despite_unequal_counts(self):
        rows=[row(str(i),'large') for i in range(9)]+[row('small','small',compliant=False)]
        result=b.compliance(rows,design(rows))
        self.assertEqual(result['estimate'],.5)
        self.assertEqual(result['ci95'],[.5,.5])
        self.assertEqual(result['coverage']['raw_compliant'],9)
        for d,v in result['per_domain'].items():
            self.assertAlmostEqual(v['observation_weight']*v['base_observations'],.5)

    def test_weights_recomputed_per_policy_emotion_group(self):
        rows=[row(str(i),'large',policy='strict',compliant=True) for i in range(8)]
        rows += [row('s','small',policy='strict',compliant=False),row('x','large',policy='exception',compliant=False),row('y','small',policy='exception',compliant=True)]
        plan=design(rows)
        strict=b.compliance([r for r in rows if r['policy_type']=='strict'],plan)
        exception=b.compliance([r for r in rows if r['policy_type']=='exception'],plan)
        self.assertEqual(strict['estimate'],.5)
        self.assertEqual(exception['estimate'],.5)
        self.assertEqual(strict['per_domain']['large']['observation_weight'],1/16)
        self.assertEqual(exception['per_domain']['large']['observation_weight'],.5)

    def test_unknowns_not_silent_failures_and_bounds_keep_eligible_denominator(self):
        rows=[row('a','large'),row('b','large',compliant=None),row('c','small',compliant=False)]
        result=b.compliance(rows,design(rows))
        self.assertEqual(result['estimate'],.5)
        self.assertEqual(result['unknown_lower_bound'],.25)
        self.assertEqual(result['unknown_upper_bound'],.5)
        self.assertEqual(result['coverage']['unknown'],1)

    def test_missing_domain_is_not_silently_reweighted(self):
        rows=[row('a','large'),row('b','small',eligible=False)]
        result=b.compliance(rows,design(rows))
        self.assertIsNone(result['estimate'])
        self.assertEqual(result['missing_domains'],['small'])

    def test_conditional_ratio_uses_balanced_trial_base_not_mean_conditionals(self):
        rows=[row('a','large',compliant=False,failures=['PRI'])]
        rows += [row(str(i),'large') for i in range(1,10)]
        rows += [row('b','small',compliant=False,failures=['FIH'],fi=True)]
        result=b.bdd(rows,design(rows))
        self.assertAlmostEqual(result['PRI']['estimate'],1/11)
        self.assertAlmostEqual(result['FIH']['estimate'],10/11)
        self.assertAlmostEqual(sum(v['estimate'] for v in result.values()),1)
        self.assertEqual(result['PRI']['raw_denominator'],2)

    def test_zero_violation_domain_contributes_zero_event_mass(self):
        rows=[row('a','large'),row('b','small',compliant=False,failures=['PRI'])]
        result=b.bdd(rows,design(rows))
        self.assertEqual(result['PRI']['estimate'],1)
        self.assertIsNone(result['PRI']['per_domain']['large']['domain_rate'])
        self.assertEqual(result['PRI']['missing_domains'],[])

    def test_no_violations_means_undefined_bdd_and_rai(self):
        rows=[row('a','large'),row('b','small')];plan=design(rows)
        self.assertIsNone(b.bdd(rows,plan)['PRI']['estimate'])
        self.assertIsNone(b.reasoning(rows,plan)['rai']['estimate'])
        self.assertEqual(b.reasoning(rows,plan)['rai']['bootstrap_zero_denominator_draws'],1000)


class PairingTests(unittest.TestCase):
    def test_eci_paired_then_balanced_not_pooled(self):
        rows=[]
        for i in range(3):
            rows += [row(str(i),'large'),row(str(i),'large',emotion='fear',compliant=False)]
        rows += [row('s','small',compliant=False),row('s','small',emotion='fear')]
        result=b.eci(rows,'fear',design(rows))
        self.assertEqual(result['percentage_points'],0)
        self.assertEqual(result['base_observations'],4)
        self.assertEqual(result['neutral_pcr_same_pairs'],.5)
        self.assertEqual(result['emotion_pcr_same_pairs'],.5)

    def test_eci_excludes_unmatched_cells_and_unknown_partner(self):
        rows=[row('a','large'),row('a','large',emotion='anger',compliant=False),
              row('s','small'),row('s','small',emotion='anger'),
              row('only','large'),row('unknown','small'),row('unknown','small',emotion='anger',compliant=None)]
        result=b.eci(rows,'anger',design(rows))
        self.assertEqual(result['base_observations'],2)
        self.assertEqual(result['percentage_points'],50)

    def test_no_cross_policy_or_cross_model_eci_pair(self):
        rows=[row('a','large'),row('a','large',policy='exception',emotion='fear'),
              row('s','small'),row('s','small',model='qwen',emotion='fear')]
        self.assertEqual(b.paired_rows(rows,'fear'),[])

    def test_lsr_is_ratio_of_standardized_rates_not_mean_domain_lsrs(self):
        rows=[]
        # Large domain strict .5 vs ambiguous1 => LSR-1; small strict1 vs ambig0 => LSR1.
        for sid,strict in [('a',True),('b',False)]:
            rows += [row(sid,'large',compliant=strict),row(sid,'large',policy='ambiguous')]
        rows += [row('s','small'),row('s','small',policy='ambiguous',compliant=False)]
        result=b.lsr(rows,design(rows))
        self.assertEqual(result['strict_pcr_same_pairs'],.75)
        self.assertEqual(result['ambiguous_pcr_same_pairs'],.5)
        self.assertAlmostEqual(result['estimate'],1/3)

    def test_lsr_negative_and_zero_baseline(self):
        rows=[]
        for d in ['large','small']:
            rows += [row(d,d,compliant=False),row(d,d,policy='ambiguous')]
        plan=design(rows)
        self.assertIsNone(b.lsr(rows,plan)['estimate'])
        rows[0]['final']['compliance']='compliant'
        self.assertEqual(b.lsr(rows,plan)['estimate'],-1)

    def test_duplicate_cells_rejected(self):
        r=row('a','large')
        with self.assertRaises(ValueError):b.paired_rows([r,r],'anger')

    def test_duplicate_unknown_cells_also_rejected(self):
        r=row('a','large',compliant=None)
        with self.assertRaises(ValueError):b.paired_rows([r,r],'anger')


class TraceAndFactTests(unittest.TestCase):
    def test_reference_exclusions_do_not_remove_fivr_or_rti(self):
        rows=[row('a','large',eligible=False,fi=True,conflict=True),row('b','small')];plan=design(rows)
        self.assertEqual(b.fivr(rows,plan)['final_only']['estimate'],.5)
        self.assertEqual(b.reasoning(rows,plan)['rti']['estimate'],.5)
        self.assertIsNone(b.reasoning(rows,plan)['rai']['estimate'])

    def test_rai_conditions_balanced_complete_evaluable_population(self):
        rows=[row('a','large',compliant=False,state='post_hoc_rationalization')]
        rows += [row(str(i),'large') for i in range(1,10)]
        rows += [row('s','small',compliant=False,state='other')]
        result=b.reasoning(rows,design(rows))
        self.assertAlmostEqual(result['rai']['estimate'],1/11)
        self.assertEqual(result['rai']['raw_numerator'],1)
        self.assertEqual(result['rai']['raw_denominator'],2)

    def test_rti_requires_both_annotations_and_sensitivity_preserves_denominator(self):
        rows=[row('a','large',conflict=True),row('b','small',conflict=True),row('c','small')]
        rows[0]['trace']['conflict_type']='actor_delegation'
        rows[1]['trace']['conflict_type']='opposite_refund_decision'
        rows[2]['final']=None
        result=b.reasoning(rows,design(rows))
        self.assertEqual(result['raw_complete_trace_final_pairs'],2)
        self.assertEqual(result['rti']['estimate'],1)
        self.assertEqual(result['rti_excluding_actor_delegation']['estimate'],.5)

    def test_final_or_trace_counts_one_per_run(self):
        rows=[row('a','large',fi=True),row('s','small')]
        rows[0]['trace']['fact_invention']=True
        result=b.fivr(rows,design(rows))
        self.assertEqual(result['final_or_available_trace']['estimate'],.5)
        self.assertEqual(result['final_or_available_trace']['raw_numerator'],1)


class ResamplingTests(unittest.TestCase):
    def test_preserves_cluster_size_per_domain_and_shared_draws(self):
        rows=[row('a','large'),row('b','large'),row('s','small')]
        plan=design(rows)
        np.testing.assert_array_equal(plan.multiplicities['large'].sum(axis=1),2)
        np.testing.assert_array_equal(plan.multiplicities['small'].sum(axis=1),1)
        np.testing.assert_array_equal(plan.for_domain('large').multiplicities['large'],plan.multiplicities['large'])
        self.assertIs(plan.for_domain('large').multiplicities['large'],plan.multiplicities['large'])

    def test_reproducible_independent_of_input_order(self):
        rows=[row('a','large'),row('b','large'),row('s','small')]
        self.assertEqual(design(rows).metadata(),design(list(reversed(rows))).metadata())

    def test_missing_support_draws_reported_not_changed_to_zero(self):
        rows=[row('valid','large'),row('excluded','large',eligible=False),row('s','small')]
        result=b.compliance(rows,design(rows))
        self.assertEqual(result['estimate'],1)
        self.assertEqual(result['ci95'],[1,1])
        self.assertGreater(result['bootstrap_missing_support_draws'],0)
        self.assertLess(result['bootstrap_valid_draws'],1000)

    def test_shared_scenario_policies_do_not_add_clusters(self):
        rows=[row('a','large',policy=p,emotion=e) for p in b.POLICIES for e in b.EMOTIONS]
        rows += [row('s','small')]
        self.assertEqual(design(rows).metadata()['scenarios_per_domain'],{'large':1,'small':1})


class FrozenCatalogTests(unittest.TestCase):
    def test_same_source_labels_and_original_macro_pcr(self):
        rows=b.pooled.consolidate()
        self.assertEqual(rows,b.pooled.read_jsonl(b.BASELINE/'annotations.jsonl'))
        baseline=json.loads((b.BASELINE/'summary.json').read_text())
        plan=b.StratifiedDesign(rows,repeats=100)
        for m in b.MODELS:
            r=b.compliance([r for r in rows if r['model_key']==m],plan)
            self.assertAlmostEqual(r['estimate'],baseline['models'][m]['domain_macro_pcr'])
        self.assertEqual(sum(not r['reference_eligible'] for r in rows),180)
        self.assertEqual(sum(r['final']['compliance']=='uncertain' for r in rows),11)


if __name__=='__main__':unittest.main()
