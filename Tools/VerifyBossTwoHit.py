"""Read saved two-hit data and executable graph connections. Does not run combat."""
import json
from pathlib import Path
import unreal
import vibeue
import PrepareBossTwoHit as P

B='/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'
S=unreal.BlueprintService


def run():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    asset=P.prepare()
    checks=[]
    def require(name,value):
        assert value,name
        checks.append(name)
    def nodes(g):
        return list(S.get_nodes_in_graph(B,g,0,'',False))
    def edges(g):
        return list(S.get_connections(B,g))
    def call(g,title):
        return next(n.node_id for n in nodes(g) if n.node_title.casefold().startswith(title.casefold()))
    def has(g,a,p,b,q='execute'):
        return any(e.source_node_id==a and e.source_pin_name==p and e.target_node_id==b and e.target_pin_name==q for e in edges(g))
    cdo=unreal.get_default_object(unreal.EditorAssetLibrary.load_asset(B).generated_class())
    actions=list(cdo.get_editor_property('Actions'))
    require('ten action IDs retain slot identity',[a.get_editor_property('ActionId') for a in actions]==list(range(10)))
    require('two-hit enabled',actions[9].get_editor_property('bEnabled'))
    require('two hits have two sockets damage and timing entries',all(len(actions[9].get_editor_property(k))==2 for k in ['ImpactTimes','HitSockets','HitDamages','HitWindowEnds']))
    require('original special combo retains three hits',len(actions[4].get_editor_property('ImpactTimes'))==3)
    require('cooldown capacity covers all actions',len(cdo.get_editor_property('CooldownUntil'))>=len(actions))
    g='EvaluateCombatUtility'; final=call(g,'Finalize Intent Scores')
    require('final scoring executes after complete candidate loop',has(g,'FB89A45349B453B90E78EF9ACE07A95B','Completed',final))
    require('final scoring executes before draw decision',has(g,final,'then','071BE9324A4CA14332E54AB6A9CAECD5'))
    g='BeginBossEncounter'; capacity=call(g,'Ensure Action Cooldown Capacity')
    require('encounter resizes cooldown storage before use',has(g,capacity,'then','5F5D7E4545A64485C63893AA4997A40C'))
    g='CloseActionImpact'; link=call(g,'Continue Two Hit Or Recover')
    require('link check executes only if another hit remains',has(g,'8BF00CD9482E27A9FA3687A965BA71AC','then',link))
    branch=next(e.target_node_id for e in edges(g) if e.source_node_id==link and e.source_pin_name=='then')
    require('link result controls continuation',has(g,link,'ReturnValue',branch,'Condition'))
    require('only accepted link advances hit index',has(g,branch,'then','4EF3AC2744FBF3277E19F9AE94364B44'))
    require('rejected link has no continuation exec',not any(e.source_node_id==branch and e.source_pin_name=='else' for e in edges(g)))
    require('normal last hit still enters recovery',has(g,'8BF00CD9482E27A9FA3687A965BA71AC','else','10A3C4184445981F89AB62AC385F2B3B'))
    for g,label in [('ComputeActionScore','selection range'),('ComputeActionScore','family repeat penalty'),
                    ('RecordPunchFamilyUse','record punch family'),('TransitionBossState','ordinary punch turning rules')]:
        require(label,any(n.node_title=='TwoHit: '+label for n in nodes(g)))
    # This only proves the added groups exist; the recorded graph wiring above and
    # native automation results cover execution order and decision boundaries.
    results=vibeue.exec_tool('AutomationTestToolset.AutomationTestToolset','GetTestResults')
    relevant={t['name']:t for t in results['tests']}
    for name in ['Battle.GOAP.IntentChoiceAndLink','Battle.GOAP.IntentTransitionParameters','Battle.GOAP.SelectedAttack']:
        require(name,relevant.get(name,{}).get('state')=='Success')
    env=json.loads(unreal.WorkflowService.get_environment())
    require('current native build succeeded',env['lastBuild']['status']=='succeeded' and not env['lastBuild'].get('isStale',True))
    report={'pie_run':False,'checks':checks,'asset':asset,'automation':results,'build':env['lastBuild'],
            'limits':['No live score draw or actual movement checked','No visual judgment of abort recovery','No input test of MotionLab controls']}
    path=Path(unreal.Paths.project_dir())/'Saved/VibeUE/Reports/crunch_two_hit_integration.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('VERIFIED',len(checks),'two-hit integration checks',str(path))
    return report
