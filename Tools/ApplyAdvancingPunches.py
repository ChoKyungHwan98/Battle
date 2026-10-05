"""Author finite stepping punches and an approach-to-attack handoff via MCP.

No PIE. Original attack clips, physical strike shapes and damage stay intact.
"""
import json
from pathlib import Path
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G
import ApplyCombatQA as Q

B, S, A = H.B, unreal.BlueprintService, unreal.AnimMontageService
ROOT = '/Game/BossArena/Boss/Animations/'
CARDS = '/Game/BossArena/Boss/AI/Actions/'
ACTION_CLASS = '/Game/BossArena/Boss/AI/BP_BossActionDefinition'
node, get, put, call = H.node, H.get, H.put, H.call
PREFIX_RATE = 1.25


def build(graph, nodes, links=(), defaults=()):
    return G.build(B, graph, nodes, links, defaults)


def make_prefix(side, steps, target_path):
    path = ROOT+f'AS_Advance_{side}_{steps}Step'
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return path
    source_path='/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Jog_Fwd'
    source=H.asset(source_path)
    clip=unreal.EditorAssetLibrary.duplicate_asset(source_path,path)
    assert clip
    print('CREATED',path)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(clip)
    frames=12 if steps==1 else 27
    length=frames/30
    tracks=list(source.get_editor_property('data_model_interface').get_bone_track_names())
    target={str(p.bone_name):p.transform for p in unreal.AnimSequenceService.get_pose_at_time(target_path,0,False)}
    sampled=[{str(p.bone_name):p.transform for p in unreal.AnimSequenceService.get_pose_at_time(source_path,f/30,False)}
             for f in range(frames+1)]
    clip.modify();clip.set_editor_property('enable_root_motion',False)
    clip.set_editor_property('force_root_lock',True)
    controller=clip.get_editor_property('controller')
    controller.open_bracket('Blend the final stepping pose into the punch entry')
    try:
        controller.set_number_of_frames(unreal.FrameNumber(frames))
        for bone in tracks:
            name=str(bone);positions=[];rotations=[];scales=[]
            for f,pose in enumerate(sampled):
                original=pose[name];goal=target[name]
                alpha=max(0,min(1,(f/30-(length-.1333333333))/.1333333333))
                alpha=alpha*alpha*(3-2*alpha)
                positions.append(original.translation+(goal.translation-original.translation)*alpha)
                rotations.append(original.rotation.slerp_quat(goal.rotation,alpha))
                scales.append(original.scale3d+(goal.scale3d-original.scale3d)*alpha)
            assert controller.set_bone_track_keys(bone,positions,rotations,scales)
    finally:
        controller.close_bracket()
    assert abs(clip.get_play_length()-length)<.001
    assert unreal.EditorAssetLibrary.save_loaded_asset(clip,False)
    print('MODIFIED matched step prefix',path,length)
    return path


def make_variant(side, steps):
    base=H.asset(CARDS+'DA_Attack_'+side)
    original=base.get_editor_property('Montage')
    original_path=original.get_path_name().split('.')[0]
    first=A.list_anim_segments(original_path,0)[0]
    prefix=make_prefix(side,steps,first.anim_sequence_path)
    offset=(.4 if steps==1 else .9)/PREFIX_RATE
    path=ROOT+f'AM_Boss_Advance_{side}_{steps}Step'
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        snapshot=[(n.notify_index,n.trigger_time,n.duration) for n in A.list_notifies(original_path)]
        segments=[(s.segment_index,s.start_time) for s in A.list_anim_segments(original_path,0)]
        assert A.duplicate_montage(original_path,ROOT.rstrip('/'),path.rsplit('/',1)[-1])
        print('CREATED',path)
        for index,start in reversed(segments):
            assert A.set_segment_start_time(path,0,index,start+offset)
        assert A.add_anim_segment(path,0,prefix,0,PREFIX_RATE)>=0
        for index,start,duration in snapshot:
            assert A.set_notify_trigger_time(path,index,start+offset)
            if duration>0:
                assert A.set_notify_duration(path,index,duration)
        montage=H.asset(path)
        unreal.AnimationLibrary.add_animation_notify_track(montage,'AdvanceFootwork',unreal.LinearColor(.1,.7,1,1))
        windows=[(.06,.28,60)] if steps==1 else [(.06,.28,60),(.48,.74,60)]
        notify_class=H.asset('/Game/BossArena/Boss/Animations/ANS_BossAttackStep').generated_class()
        for start,end,distance in windows:
            notify=unreal.AnimationLibrary.add_animation_notify_state_event(
                montage,'AdvanceFootwork',start/PREFIX_RATE,(end-start)/PREFIX_RATE,notify_class)
            assert notify
            notify.set_editor_property('StepDistance',distance)
        assert A.set_blend_in(path,.12,'Cubic')
        assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
        print('MODIFIED authored step windows + shifted strike/FX',path,offset)
    card_path=CARDS+f'DA_Attack_Advance{side}_{steps}Step'
    if not unreal.EditorAssetLibrary.does_asset_exist(card_path):
        assert unreal.EditorAssetLibrary.duplicate_asset(base.get_path_name().split('.')[0],card_path)
        print('CREATED',card_path)
    card=H.asset(card_path);card.modify()
    for key in [v.variable_name for v in S.list_variables(ACTION_CLASS)]:
        card.set_editor_property(key,base.get_editor_property(key))
    delay=offset/base.get_editor_property('PlayRate')-.10
    card.set_editor_property('Montage',H.asset(path))
    card.set_editor_property('DisplayName',f'{"한 발" if steps==1 else "두 발"} → {"왼손 휘두르기" if side=="Left" else "바디 펀치"}')
    card.set_editor_property('TelegraphSeconds',.15)
    card.set_editor_property('TotalSeconds',base.get_editor_property('TotalSeconds')+delay)
    card.set_editor_property('ImpactTimes',[float(t)+delay for t in base.get_editor_property('ImpactTimes')])
    card.set_editor_property('HitWindowEnds',[float(t)+offset for t in base.get_editor_property('HitWindowEnds')])
    assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
    return card_path


def configure_pattern():
    for name,kind,value in [('AttackAdvanceStepCount','int',0),('AttackEntryDistance','real',0),
                            ('AttackAdvanceBudget','real',0),('ApproachAttackHandoffDistance','real',400)]:
        H.variable(B,name,kind,value)
    refs={f'Advance{side}{count}':make_variant(side,count) for side in ['Left','Right'] for count in [1,2]}
    refs.update({'StandingLeft':CARDS+'DA_Attack_Left','StandingRight':CARDS+'DA_Attack_Right'})
    variables={v.variable_name for v in S.list_variables(B)}
    for name,path in refs.items():
        if name not in variables:
            pin_type=unreal.BlueprintEditorLibrary.get_member_variable_type(H.asset(B),'ActiveAction')
            assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(B),name,pin_type)
            print('ADDED',name)
        assert S.set_variable_default_value(B,name,H.asset(path).get_path_name())
    H.function(B,'ConfigureAdvancingPunch')
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))
    g='ConfigureAdvancingPunch'
    if Q.empty_body(B,g):
        nodes=[put('ResetCount','AttackAdvanceStepCount'),put('ResetBudget','AttackAdvanceBudget'),
               get('Player','ObservedPlayer'),call('Valid','KismetSystemLibrary','IsValid'),node('PlayerGate','branch'),
               call('Distance','Actor','GetHorizontalDistanceTo'),put('EntryDistance','AttackEntryDistance'),
               put('LiveDistance','UtilityDistance'),get('Action','ActiveAction'),
               node('ID','member_get',**{'class':ACTION_CLASS,'member':'ActionId'}),
               call('IsLeft','KismetMathLibrary','EqualEqual_IntInt'),node('LeftGate','branch'),
               call('IsRight','KismetMathLibrary','EqualEqual_IntInt'),node('RightGate','branch'),
               get('Entry','AttackEntryDistance'),put('Budget','AttackAdvanceBudget'),
               call('Room','KismetMathLibrary','Subtract_DoubleDouble'),call('BoundBudget','KismetMathLibrary','FClamp'),
               get('Selected','ActiveAction'),node('Name','member_get',**{'class':ACTION_CLASS,'member':'DisplayName'}),
               put('Label','UtilityChoice'),call('Log',B,'RecordCombatQA')]
        links=[(G.entry(B,g)+'.then','ResetCount.execute'),('ResetCount.then','ResetBudget.execute'),
               ('ResetBudget.then','PlayerGate.execute'),('Player.ObservedPlayer','Valid.Object'),
               ('Valid.ReturnValue','PlayerGate.Condition'),('PlayerGate.then','EntryDistance.execute'),
               ('Player.ObservedPlayer','Distance.OtherActor'),('Distance.ReturnValue','EntryDistance.AttackEntryDistance'),
               ('EntryDistance.then','LiveDistance.execute'),('EntryDistance.Output_Get','LiveDistance.UtilityDistance'),
               ('LiveDistance.then','LeftGate.execute'),('Action.ActiveAction','ID.self'),
               ('ID.ActionId','IsLeft.A'),('IsLeft.ReturnValue','LeftGate.Condition'),
               ('LeftGate.else','RightGate.execute'),('ID.ActionId','IsRight.A'),('IsRight.ReturnValue','RightGate.Condition'),
               ('Entry.AttackEntryDistance','Room.A'),('Room.ReturnValue','BoundBudget.Value'),
               ('BoundBudget.ReturnValue','Budget.AttackAdvanceBudget'),('Budget.then','Label.execute'),
               ('Selected.ActiveAction','Name.self'),('Name.DisplayName','Label.UtilityChoice'),
               ('Label.then','Log.execute')]
        defaults=[('ResetCount','AttackAdvanceStepCount',0),('ResetBudget','AttackAdvanceBudget',0),
                  ('IsLeft','B',0),('IsRight','B',1),('Room','B',195),('BoundBudget','Min',0),
                  ('BoundBudget','Max',165),('Log','Event','attack_pattern')]
        for side,gate,advance,two in [('Left','LeftGate',225,300),('Right','RightGate',225,260)]:
            nodes += [call(side+'Advance','KismetMathLibrary','Greater_DoubleDouble'),node(side+'AdvanceGate','branch'),
                      call(side+'Two','KismetMathLibrary','Greater_DoubleDouble'),node(side+'TwoGate','branch')]
            links += [(gate+'.then',side+'AdvanceGate.execute'),('Entry.AttackEntryDistance',side+'Advance.A'),
                      (side+'Advance.ReturnValue',side+'AdvanceGate.Condition'),(side+'AdvanceGate.then',side+'TwoGate.execute'),
                      ('Entry.AttackEntryDistance',side+'Two.A'),(side+'Two.ReturnValue',side+'TwoGate.Condition')]
            defaults += [(side+'Advance','B',advance),(side+'Two','B',two)]
            for count,src in [(0,side+'AdvanceGate.else'),(1,side+'TwoGate.else'),(2,side+'TwoGate.then')]:
                key=side+str(count); variable='Standing'+side if count==0 else 'Advance'+side+str(count)
                nodes += [get(key+'Card',variable),put(key+'Select','ActiveAction'),put(key+'Count','AttackAdvanceStepCount')]
                links += [(src,key+'Select.execute'),(key+'Card.'+variable,key+'Select.ActiveAction'),
                          (key+'Select.then',key+'Count.execute')]
                if count:
                    links += [(key+'Count.then','Budget.execute')]
                else:
                    links += [(key+'Count.then','Label.execute')]
                defaults += [(key+'Count','AttackAdvanceStepCount',count)]
        build(g,nodes,links,defaults)
    # Bind the complete pattern before any HFSM timing or montage reads.
    if not any(n.node_title.startswith('Configure Advancing Punch')
               for n in S.get_nodes_in_graph(B,'BeginCombatAction',0,'',False)):
        Q.hook(B,'BeginCombatAction','764E2CFC44444A34E762FEB8B3C9C6CB','then','ConfigureAdvancingPunch')


def repair_pattern_dispatch():
    # A rejected duplicate ref in the first build left the distance gates valid,
    # but overwrote the two action-family gates. Repair only those missing gates.
    g='ConfigureAdvancingPunch';cons=S.get_connections(B,g)
    if sum(c.source_node_title=='Equal (Integer)' and c.target_pin_name=='Condition' for c in cons)==2:
        return
    ids=build(g,[node('LeftFamily','branch'),node('RightFamily','branch')],[
        ('E952105E45FE1B6B3307BBB8E04E0949.ReturnValue','LeftFamily.Condition'),
        ('B48F265544B91F442C4C1AB242A45507.ReturnValue','RightFamily.Condition'),
        ('LeftFamily.then','4C6114E64B1AC35432E30594713A974B.execute'),
        ('LeftFamily.else','RightFamily.execute'),
        ('RightFamily.then','83AA24BB409C588D596CC4B420264465.execute')])
    assert S.disconnect_pin(B,g,'6C6B50994C031A59E35153B99FD50D9E','then')
    assert S.connect_nodes(B,g,'6C6B50994C031A59E35153B99FD50D9E','then',ids['LeftFamily'],'execute')
    print('MODIFIED restored Left/Right action-family dispatch without replacing the graph')


def finite_step_budget():
    g='BeginAttackStep'
    if any('AttackAdvanceBudget' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    ids=build(g,[get('Player','ObservedPlayer'),call('Gap','Actor','GetHorizontalDistanceTo'),
        call('Room','KismetMathLibrary','Subtract_DoubleDouble'),call('SafeRoom','KismetMathLibrary','FMax'),
        call('Requested','KismetMathLibrary','FMin'),get('Count','AttackAdvanceStepCount'),
        call('Advance','KismetMathLibrary','Greater_IntInt'),get('Budget','AttackAdvanceBudget'),
        call('Allowed','KismetMathLibrary','FMin'),call('DistanceChoice','KismetMathLibrary','SelectFloat'),
        call('LeftOver','KismetMathLibrary','Subtract_DoubleDouble'),call('Nonnegative','KismetMathLibrary','FMax'),
        put('BudgetRemaining','AttackAdvanceBudget')], [
        ('Player.ObservedPlayer','Gap.OtherActor'),('Gap.ReturnValue','Room.A'),('Room.ReturnValue','SafeRoom.A'),
        (G.entry(B,g)+'.Distance','Requested.A'),('SafeRoom.ReturnValue','Requested.B'),
        ('Count.AttackAdvanceStepCount','Advance.A'),('Requested.ReturnValue','Allowed.A'),
        ('Budget.AttackAdvanceBudget','Allowed.B'),('Allowed.ReturnValue','DistanceChoice.A'),
        ('Requested.ReturnValue','DistanceChoice.B'),('Advance.ReturnValue','DistanceChoice.bPickA'),
        ('Budget.AttackAdvanceBudget','LeftOver.A'),('CD70EBBC445398FB20E6179B42F35E1E.Output_Get','LeftOver.B'),
        ('LeftOver.ReturnValue','Nonnegative.A'),('Nonnegative.ReturnValue','BudgetRemaining.AttackAdvanceBudget')], [
        ('Room','B',175),('SafeRoom','B',0),('Advance','B',0),('Nonnegative','B',0)])
    assert S.disconnect_pin(B,g,'A88FB45F49363C29E3726B9E252E28F0','Value')
    assert S.connect_nodes(B,g,ids['DistanceChoice'],'ReturnValue','A88FB45F49363C29E3726B9E252E28F0','Value')
    assert S.disconnect_pin(B,g,'CD70EBBC445398FB20E6179B42F35E1E','then')
    assert S.connect_nodes(B,g,'CD70EBBC445398FB20E6179B42F35E1E','then',ids['BudgetRemaining'],'execute')
    assert S.connect_nodes(B,g,ids['BudgetRemaining'],'then','1DA39B2746C79E0E94241F92A4B44302','execute')
    Q.hook(B,g,'FA67DB014855133FD45719B002DEE6FE','then','RecordCombatQA','attack_step_begin')
    terminal=next(n.node_id for n in S.get_nodes_in_graph(B,'EndAttackStep',0,'',False) if n.node_title=='Set bAttackStepActive')
    Q.hook(B,'EndAttackStep',terminal,'then','RecordCombatQA','attack_step_end')


def approach_handoff():
    g='EvaluateCombatUtility'
    if not any('ApproachAttackHandoffDistance' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('Distance','UtilityDistance'),get('Handoff','ApproachAttackHandoffDistance'),
            call('Within','KismetMathLibrary','LessEqual_DoubleDouble'),node('AttackRangeGate','branch'),
            call('FinishApproach',B,'CompleteCombatApproach')], [
            ('BD195DEB47CB6D9AFDB93A907F354FF1.then','AttackRangeGate.execute'),
            ('Distance.UtilityDistance','Within.A'),('Handoff.ApproachAttackHandoffDistance','Within.B'),
            ('Within.ReturnValue','AttackRangeGate.Condition'),('AttackRangeGate.then','FinishApproach.execute'),
            ('FinishApproach.then','1A9456F448BE579CBA199E81C9CB3CC2.execute')], [('FinishApproach','Arrived','false')])
    H.variable(B,'ApproachMaxDuration','real',2)
    # A far approach timeout may reconsider Approach and Dash together. It must
    # not suppress Approach for one second and force Dash to become the only card.
    cooldown_graph='CompleteCombatApproach'
    if not any(n.node_title=='Select Float' for n in S.get_nodes_in_graph(B,cooldown_graph,0,'',False)
               if any(c.target_node_id=='112919AF40D76270A0C52AA2D16A63E6' and c.source_node_id==n.node_id
                      for c in S.get_connections(B,cooldown_graph))):
        ids=build(cooldown_graph,[call('CooldownDuration','KismetMathLibrary','SelectFloat')], [
            (G.entry(B,cooldown_graph)+'.Arrived','CooldownDuration.bPickA'),
            ('CooldownDuration.ReturnValue','112919AF40D76270A0C52AA2D16A63E6.B')], [
            ('CooldownDuration','A',1),('CooldownDuration','B',0)])
    # Handoff still suppresses a repeated Approach selection inside the attack
    # band. Unlike Arrived=True, this does not recursively evaluate Utility.
    cons=S.get_connections(B,g)
    finish=next(n.node_id for n in S.get_nodes_in_graph(B,g,0,'',False)
                if n.node_title.startswith('Complete Combat Approach'))
    if not any(c.source_node_id==finish and c.target_node_title=='Set ApproachCooldownUntil' for c in cons):
        ids=build(g,[call('Now','GameplayStatics','GetTimeSeconds'),call('Cooldown','KismetMathLibrary','Add_DoubleDouble'),
            put('HoldApproach','ApproachCooldownUntil')], [
            ('Now.ReturnValue','Cooldown.A'),('Cooldown.ReturnValue','HoldApproach.ApproachCooldownUntil')], [('Cooldown','B',1)])
        assert S.disconnect_pin(B,g,finish,'then')
        assert S.connect_nodes(B,g,finish,'then',ids['HoldApproach'],'execute')
        assert S.connect_nodes(B,g,ids['HoldApproach'],'then','1A9456F448BE579CBA199E81C9CB3CC2','execute')
    # A short probe remains possible up close; it must not swallow the footwork band.
    assert S.set_node_pin_value(B,'MaybeGoapProbe','7AD799D34C8BF7828608AC87E8C28819','B','225')
    for side,max_distance in [('Left',400),('Right',350)]:
        card=H.asset(CARDS+'DA_Attack_'+side);card.modify()
        card.set_editor_property('MaxDistance',max_distance)
        assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
        print('MODIFIED attack selection range',side,max_distance)


def qa_fields():
    g='RecordCombatQA'
    if any('AttackAdvanceStepCount' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    write='7351315649F7330AF5C248810231A881'
    before=next(c for c in S.get_connections(B,g) if c.target_node_id==write and c.target_pin_name=='InString')
    ids=build(g,[get('Count','AttackAdvanceStepCount'),get('Distance','AttackEntryDistance'),get('Budget','AttackAdvanceBudget'),
        call('AddCount','KismetStringLibrary','BuildString_Int'),call('AddDistance','KismetStringLibrary','BuildString_Double'),
        call('AddBudget','KismetStringLibrary','BuildString_Double')], [
        (before.source_node_id+'.'+before.source_pin_name,'AddCount.AppendTo'),
        ('Count.AttackAdvanceStepCount','AddCount.InInt'),('AddCount.ReturnValue','AddDistance.AppendTo'),
        ('Distance.AttackEntryDistance','AddDistance.InDouble'),('AddDistance.ReturnValue','AddBudget.AppendTo'),
        ('Budget.AttackAdvanceBudget','AddBudget.InDouble')], [
        ('AddCount','Prefix','|advance_steps='),('AddDistance','Prefix','|entry_distance='),('AddBudget','Prefix','|advance_budget=')])
    assert S.disconnect_pin(B,g,write,'InString')
    assert S.connect_nodes(B,g,ids['AddBudget'],'ReturnValue',write,'InString')


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    if 'bPunchFootSync' in {v.variable_name for v in S.list_variables(B)}:
        raise RuntimeError('Archived Jog-prefix authoring: use ApplyPunchFootSync.py for the current ordinary punch policy.')
    configure_pattern();repair_pattern_dispatch();finite_step_budget();approach_handoff();qa_fields()
    r=S.compile_blueprint(B)
    print('COMPILE',r.success,list(r.errors),list(r.warnings));assert r.success and not r.warnings
    cdo=unreal.get_default_object(H.asset(B).generated_class())
    for name in ['AdvanceLeft1','AdvanceLeft2','AdvanceRight1','AdvanceRight2','StandingLeft','StandingRight']:
        assert cdo.get_editor_property(name)
    assert unreal.EditorAssetLibrary.save_asset(B)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==H.asset(B).generated_class():
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('SAVED advancing punch policy; no PIE performed')


if __name__=='__main__':
    apply()
