"""
Inter-Annotator Agreement (IAA) Report
CoSQL NBA Spatial — IE7500 NLP Northeastern University College of Engineering - June 2026
Author: Rosalina Torres

Reports execution pass rate across all WOZ annotation pairs, and Cohen's Kappa
ONLY where it is statistically valid.

WHY THE OLD κ WAS REMOVED:
Cohen's κ requires the SAME items independently rated by TWO raters. In this
corpus each pair has exactly one auditor (Craig or Sean on disjoint subsets),
so there are zero paired observations. The previous version combined the
overall pass rate (as "observed agreement") with the two auditors' pass rates
on disjoint subsets (as marginals) — that quantity is not Cohen's κ and should
not be reported as inter-annotator agreement.

To report a real κ, doubly-annotate a subset (both auditors judge the same
pairs) and record the second judgment in the kappa_agreement column. This
script computes κ automatically once such rows exist.
"""

import pandas as pd
import os

ANNOTATION_DIR = os.path.join(os.path.dirname(__file__), 'annotation')

FILES = [
    ('Spatial Zone',              'annotation_batch_class1_spatial_zone.csv'),
    ('Temporal Scope',            'annotation_batch_class2_temporal_scope.csv'),
    ('Player/Entity',             'annotation_batch_class3_player_entity.csv'),
    ('Simple Aggregation',        'annotation_batch_class4_simple_aggregation.csv'),
    ('Comparative Aggregation',   'annotation_batch_class5_comparative_aggregation.csv'),
    ('Multi-Turn Coreference',    'annotation_batch_class6_coreference.csv'),
    ('Game/Matchup Context',      'annotation_batch_class7_game_context.csv'),
    ('Shot Characteristics',      'annotation_batch_class8_shot_characteristics.csv'),
]

BOOL_MAP = {True: 1, 'TRUE': 1, 'True': 1, False: 0, 'FALSE': 0, 'False': 0}


def load_all():
    dfs = {}
    for label, fname in FILES:
        path = os.path.join(ANNOTATION_DIR, fname)
        dfs[label] = pd.read_csv(path)
    return dfs


def cohen_kappa_paired(rater1: pd.Series, rater2: pd.Series):
    """
    Cohen's κ on PAIRED observations: both series must be 0/1 judgments of
    the SAME items, aligned by index. Returns None if fewer than 2 pairs.
    """
    n = len(rater1)
    if n < 2 or len(rater2) != n:
        return None
    po = float((rater1 == rater2).mean())
    p1, p2 = float(rater1.mean()), float(rater2.mean())
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def run_report():
    dfs = load_all()
    combined = pd.concat(dfs.values(), ignore_index=True)

    total = len(combined)
    combined['exec_int'] = combined['execution_pass'].map(BOOL_MAP)
    approved = int(combined['exec_int'].sum())
    pass_rate = approved / total

    print('=' * 60)
    print('INTER-ANNOTATOR AGREEMENT REPORT')
    print('CoSQL NBA Spatial — WOZ Annotation')
    print('=' * 60)

    print(f'\nTotal pairs:    {total}')
    print(f'Passed (exec):  {approved}  ({pass_rate * 100:.1f}%)')
    print(f'Failed (exec):  {total - approved}  (permanent API limitation)')

    print('\nPer-class breakdown:')
    print(f'  {"Query Class":<28} {"Pairs":>6}  {"Approved":>8}  {"Pass %":>7}')
    print('  ' + '-' * 52)
    for label, df in dfs.items():
        df['exec_int'] = df['execution_pass'].map(BOOL_MAP)
        n = len(df)
        a = int(df['exec_int'].sum())
        print(f'  {label:<28} {n:>6}  {a:>8}  {a/n*100:>6.1f}%')

    craig = combined[combined['state_auditor'] == 'Craig']
    sean = combined[combined['state_auditor'] == 'Sean']

    # Real Cohen's κ is only computable on doubly-annotated pairs: rows where
    # kappa_agreement holds a second, independent judgment of the same item.
    double = combined[combined['kappa_agreement'].notna()
                      & (combined['kappa_agreement'].astype(str).str.strip() != '')]
    kappa = None
    if len(double) >= 2:
        r1 = double['execution_pass'].map(BOOL_MAP)
        r2 = double['kappa_agreement'].map(BOOL_MAP)
        kappa = cohen_kappa_paired(r1, r2)

    print(f'\n{"=" * 60}')
    print("COHEN'S KAPPA (inter-annotator agreement)")
    print(f'{"=" * 60}')
    print(f'  Craig-audited pairs:  {len(craig)}')
    print(f'  Sean-audited pairs:   {len(sean)}')
    print(f'  Doubly-annotated pairs: {len(double)}')
    if kappa is not None:
        print(f'  κ = {kappa:.4f} on {len(double)} doubly-annotated pairs')
    else:
        print('  ⚠️  κ NOT COMPUTABLE: no pair has judgments from both auditors.')
        print('     Each item was audited by exactly one person, so there are no')
        print('     paired observations. To report κ, have both auditors judge a')
        print('     shared subset and record the second judgment in kappa_agreement.')

    print(f'\n{"=" * 60}')
    print('SUMMARY FOR PAPER')
    print(f'{"=" * 60}')
    print(f'  Total WOZ pairs: {total} across 8 query classes')
    print(f'  Execution verified: {approved}/{total} ({pass_rate*100:.1f}%) against live PostgreSQL (nba_spatial)')
    print(f'  Permanent limitation: 1 pair — defender column unavailable in ShotChartDetail')
    if kappa is not None:
        print(f'  Inter-annotator agreement: κ = {kappa:.2f} ({len(double)} doubly-annotated pairs)')
    else:
        print('  Inter-annotator agreement: not measurable (single-auditor protocol) —')
        print('  report the execution pass rate as a verification rate, not as agreement.')

    return {
        'total': total,
        'approved': approved,
        'pass_rate': pass_rate,
        'kappa': kappa,
        'n_double_annotated': len(double),
    }


if __name__ == '__main__':
    results = run_report()
