"""Classify changes without treating model text as operator intent."""
def changes(previous,current):
    return {'controlled_restart':any(previous[f]!=current[f] for f in ('target','sandbox','integrations')),
            'fleet_reconcile':previous['fleet']['counts']!=current['fleet']['counts'],
            'goals_changed':previous['goals']!=current['goals'],'budget_reload':previous['budget']!=current['budget'],
            'rules_tightened':previous['rules']!=current['rules']}
