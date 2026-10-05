"""Read-only editor validation. Does not simulate combat, start PIE, or move actors."""
import unreal
import json
from pathlib import Path

B='/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'
S=unreal.BlueprintService


def run():
    import vibeue
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    checks=[]
    def require(label, condition):
        assert condition, label
        checks.append(label)
    def plan(d=240, dot=1, forward=True, back=True, left=True, right=True, probe=False):
        return unreal.BossPositionPlanner.plan_attack_position(d,dot,180,280,.7,forward,back,left,right,probe,600)
    E=unreal.BossPositionAction
    ready=plan()
    require('already in band needs no step',ready.found and len(ready.steps)==0)
    enter=plan(500)
    require('entry rechecks facing after translation',list(enter.steps)==[E.DIRECT_APPROACH,E.FACE_TARGET])
    require('blocked entry has no imaginary route',not plan(500,forward=False).found)
    require('too close needs back step',plan(150).first_action==E.STEP_BACK)
    require('blocked back step fails',not plan(150,back=False).found)
    require('behind target requires turn',plan(dot=-1).first_action==E.FACE_TARGET)
    require('probe chooses open side',plan(left=False,probe=True).first_action==E.ORBIT_RIGHT)
    require('no open side cannot finish probe',not plan(left=False,right=False,probe=True).found)
    for d in [180,280]:
        require(f'inclusive start boundary {d}',len(plan(d).steps)==0)
    for d in [179,281,350,500,650]:
        p=plan(d)
        require(f'outside distance {d} needs real positioning',p.found and len(p.steps)>0)
    require('invalid goal rejected',not unreal.BossPositionPlanner.plan_attack_position(200,1,300,200,.7,True,True,True,True,False,600).found)
    require('nonfinite observation rejected',not plan(float('nan')).found)
    # Test a grid through the real native planner (not a Python copy of its formula).
    grid=0
    for d in [150,180,230,280,350,650]:
        for dot in [-1,0,.7,1]:
            for forward in [False,True]:
                for back in [False,True]:
                    p=plan(d,dot,forward,back)
                    expected=(d>=180 or back) and (d<=280 or forward)
                    assert p.found==expected,(d,dot,forward,back,p)
                    if d>=180 and d<=280 and dot>=.7:
                        assert len(p.steps)==0
                    grid+=1
    require('96 range/facing/path cases',grid==96)
    ns=list(S.get_nodes_in_graph(B,'ChooseCombatAction',0,'',False))
    edges=list(S.get_connections(B,'ChooseCombatAction'))
    intent=next(n.node_id for n in ns if n.node_title.startswith('Begin Selected Attack Intent'))
    require('utility calls persistent executor',any(e.target_node_id==intent and e.target_pin_name=='execute' for e in edges))
    require('old direct attack call disconnected',not any(e.target_node_id=='D6C8DBF54591DF08F662A79DF4396DD5' and e.target_pin_name=='execute' for e in edges))
    selection_edges=list(S.get_connections(B,'ComputeActionScore'))
    range_edge=next(e for e in selection_edges if e.target_node_id=='42768CC043C0F079638EBE9E98FFE705' and e.target_pin_name=='B')
    require('selection range differs from execution range',range_edge.source_node_id!='11D62E634717BD62E424E380D765A0A7')
    cdo=unreal.get_default_object(unreal.load_object(None,B).generated_class())
    require('entry selection cap 650',cdo.get_editor_property('IntentSelectionMaxDistance')==650)
    cards=cdo.get_editor_property('Actions')
    require('basic execution limits unchanged',all(cards[i].get_editor_property('MaxDistance')==350 for i in [0,1]))
    env=json.loads(unreal.WorkflowService.get_environment())
    require('real native build succeeded',env['lastBuild']['status']=='succeeded')
    report={'stage':2,'pie_run':False,'native_planner_grid_cases':grid,'checks':checks,
            'build':env['lastBuild'],
            'limits':['No movement or physical contact test','Side/back execution and two-hit routes still need later integration',
                      '350cm start band is provisional; not measured hit coverage']}
    path=Path(unreal.Paths.project_dir())/'Saved/VibeUE/Reports/crunch_intent_polish_stage2.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('VERIFIED',len(checks),'checks;',grid,'native planner cases;',str(path))
    return report
