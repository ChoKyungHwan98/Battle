"""Give ordinary punches bounded forward reach via Unreal MCP; no PIE.

Preparation and strike movement share a finite allowance. A retreat estimate is
sampled once per step; each tick clips travel before the player's body.
"""
import json
from pathlib import Path
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G

B, S, A = H.B, unreal.BlueprintService, unreal.AnimMontageService
ROOT = '/Game/BossArena/Boss/Animations/'
CARDS = '/Game/BossArena/Boss/AI/Actions/'
node, get, put, call = H.node, H.get, H.put, H.call
PREFIX_RATE = 1.25  # Restore the original heavy preparation tempo after user review.


def build(graph, nodes, links=(), defaults=()):
    return G.build(B, graph, nodes, links, defaults)


def retime_montages(preparation_only=False):
    # Keep strike/FX windows and source punch playback unchanged.
    cls = H.asset('/Game/BossArena/Boss/Animations/ANS_BossAttackStep').generated_class()
    for side, end in [('Left', .45), ('Right', .43)]:
        base = H.asset(CARDS+'DA_Attack_'+side)
        mp = base.get_editor_property('Montage').get_path_name().split('.')[0]
        montage = H.asset(mp)
        if not preparation_only:
            unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
            montage.modify()
            events = unreal.AnimationLibrary.get_animation_notify_events(montage)
            notifies = A.list_notifies(mp)
            for index, event in enumerate(events):
                if event.notify_state_class and event.notify_state_class.get_class() == cls:
                    assert A.set_notify_duration(mp,index,end-notifies[index].trigger_time)
                    event.notify_state_class.set_editor_property('StepDistance',240)
            assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
            print('MODIFIED punch travel',mp,240,end)
        for count in [1,2]:
            mp=ROOT+f'AM_Boss_Advance_{side}_{count}Step'
            montage=H.asset(mp)
            unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
            segments=A.list_anim_segments(mp,0)
            prefix=next(s for s in segments if 'AS_Advance_' in s.anim_sequence_path)
            clip_length=.4 if count==1 else .9
            old_rate=float(prefix.play_rate)
            old_offset=clip_length/old_rate
            new_offset=clip_length/PREFIX_RATE
            delta=new_offset-old_offset
            snapshot=[(n.notify_index,n.trigger_time,n.duration) for n in A.list_notifies(mp)]
            if abs(delta)>.00001:
                for seg in segments:
                    if seg.segment_index!=prefix.segment_index:
                        assert A.set_segment_start_time(mp,0,seg.segment_index,seg.start_time+delta)
                assert A.set_segment_play_rate(mp,0,prefix.segment_index,PREFIX_RATE)
                for index,start,duration in snapshot:
                    if start<old_offset-.00001:
                        ratio=old_rate/PREFIX_RATE
                        new_start,new_duration=start*ratio,duration*ratio
                    else:
                        new_start,new_duration=start+delta,duration
                    assert A.set_notify_trigger_time(mp,index,new_start)
                    if duration>0:
                        assert A.set_notify_duration(mp,index,new_duration)
                card=H.asset(CARDS+f'DA_Attack_Advance{side}_{count}Step');card.modify()
                rate=card.get_editor_property('PlayRate')
                card.set_editor_property('TotalSeconds',card.get_editor_property('TotalSeconds')+delta/rate)
                card.set_editor_property('ImpactTimes',[float(t)+delta/rate for t in card.get_editor_property('ImpactTimes')])
                card.set_editor_property('HitWindowEnds',[float(t)+delta for t in card.get_editor_property('HitWindowEnds')])
                assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
            montage.modify()
            events=unreal.AnimationLibrary.get_animation_notify_events(montage)
            notifies=A.list_notifies(mp)
            for index,event in enumerate(events):
                if event.notify_state_class and event.notify_state_class.get_class()==cls:
                    prep=notifies[index].trigger_time<new_offset-.00001
                    event.notify_state_class.set_editor_property('StepDistance',140 if prep else 240)
                    if not prep:
                        assert A.set_notify_duration(mp,index,new_offset+end-notifies[index].trigger_time)
            assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
            print('MODIFIED finite preparation + punch',mp,new_offset)


def budget():
    g='ConfigureAdvancingPunch'
    incoming=next(c for c in S.get_connections(B,g)
                  if c.target_node_id=='BBDE41B74A2B534B715EC4AA47FDAB10' and c.target_pin_name=='Value')
    if incoming.source_node_id=='A72253CE47AF300C52341F82B9C0C403':
        ids=build(g,[get('Count','AttackAdvanceStepCount'),call('CountFloat','KismetMathLibrary','Conv_IntToDouble'),
            call('StepBudget','KismetMathLibrary','Multiply_DoubleDouble'),
            call('PunchBudgetMaximum','KismetMathLibrary','Add_DoubleDouble')],[
            ('Count.AttackAdvanceStepCount','CountFloat.InInt'),('CountFloat.ReturnValue','StepBudget.A'),
            ('StepBudget.ReturnValue','PunchBudgetMaximum.A')],[
            ('StepBudget','B',140),('PunchBudgetMaximum','B',240)])
        assert S.disconnect_pin(B,g,'BBDE41B74A2B534B715EC4AA47FDAB10','Value')
        assert S.connect_nodes(B,g,ids['PunchBudgetMaximum'],'ReturnValue','BBDE41B74A2B534B715EC4AA47FDAB10','Value')
        # An unlinked standing variant previously skipped budget assignment.
        for ident in ['5A88A56A4C7D9063A7F12887908A9180','2A5F337A43F5FEEAA4ACE48DDEC2967C']:
            assert S.disconnect_pin(B,g,ident,'then')
            assert S.connect_nodes(B,g,ident,'then','35F7769642553C67E5C2D4BD55069DEA','execute')
    assert S.set_node_pin_value(B,g,'BBDE41B74A2B534B715EC4AA47FDAB10','Max','520')


def reach():
    g='BeginAttackStep'
    H.variable(B,'PunchRetreatAllowance','real',0)
    if not any('PunchRetreatAllowance' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('Action','ActiveAction'),
            node('ID','member_get',**{'class':'/Game/BossArena/Boss/AI/BP_BossActionDefinition','member':'ActionId'}),
            call('Left','KismetMathLibrary','EqualEqual_IntInt'),call('Right','KismetMathLibrary','EqualEqual_IntInt'),
            call('Ordinary','KismetMathLibrary','BooleanOR'),get('Player','ObservedPlayer'),
            call('Velocity','Actor','GetVelocity'),call('Forward','Actor','GetActorForwardVector'),
            call('Outward','KismetMathLibrary','Dot_VectorVector'),call('BoundSpeed','KismetMathLibrary','FClamp'),
            call('Lead','KismetMathLibrary','FClamp'),call('Predict','KismetMathLibrary','Multiply_DoubleDouble'),
            call('EligiblePrediction','KismetMathLibrary','SelectFloat'),put('Allowance','PunchRetreatAllowance'),
            get('RecordedAllowance','PunchRetreatAllowance'),call('ReachRoom','KismetMathLibrary','Add_DoubleDouble')],[
            ('Action.ActiveAction','ID.self'),('ID.ActionId','Left.A'),('ID.ActionId','Right.A'),
            ('Left.ReturnValue','Ordinary.A'),('Right.ReturnValue','Ordinary.B'),
            ('Player.ObservedPlayer','Velocity.self'),('Velocity.ReturnValue','Outward.A'),
            ('Forward.ReturnValue','Outward.B'),('Outward.ReturnValue','BoundSpeed.Value'),
            ('611ADA0E40BBCCCE91C395ACD37F4A1E.ReturnValue','Lead.Value'),
            ('BoundSpeed.ReturnValue','Predict.A'),('Lead.ReturnValue','Predict.B'),
            ('Predict.ReturnValue','EligiblePrediction.A'),('Ordinary.ReturnValue','EligiblePrediction.bPickA'),
            ('EligiblePrediction.ReturnValue','Allowance.PunchRetreatAllowance'),
            ('668C274D4A8DB3701A71DCB13DFCEE8A.ReturnValue','ReachRoom.A'),
            ('RecordedAllowance.PunchRetreatAllowance','ReachRoom.B')],[
            ('Left','B',0),('Right','B',1),('BoundSpeed','Min',0),('BoundSpeed','Max',450),
            ('Lead','Min',0),('Lead','Max',.35),('EligiblePrediction','B',0)])
        assert S.disconnect_pin(B,g,'D24B8FF642204FBB18FA3BB96D2CA4A4','B')
        assert S.connect_nodes(B,g,ids['ReachRoom'],'ReturnValue','D24B8FF642204FBB18FA3BB96D2CA4A4','B')
        assert S.disconnect_pin(B,g,'12FD688143170C76D867CFA6196AFD47','bPickA')
        assert S.connect_nodes(B,g,ids['Ordinary'],'ReturnValue','12FD688143170C76D867CFA6196AFD47','bPickA')
        gate=next(c.source_node_id for c in S.get_connections(B,g)
                  if c.target_node_id=='CD70EBBC445398FB20E6179B42F35E1E' and c.target_pin_name=='execute')
        assert S.disconnect_pin(B,g,gate,'then')
        assert S.connect_nodes(B,g,gate,'then',ids['Allowance'],'execute')
        assert S.connect_nodes(B,g,ids['Allowance'],'then','CD70EBBC445398FB20E6179B42F35E1E','execute')
        assert S.add_comment_around_nodes(B,g,'PunchRetreatAllowance: snapshot outward travel',list(ids.values()))
    assert S.set_node_pin_value(B,g,'A88FB45F49363C29E3726B9E252E28F0','Max','240')


def body_clearance():
    g='AdvanceAttackStep'
    incoming=next(c for c in S.get_connections(B,g)
                  if c.target_node_id=='32E0E13F470C773B8203139C0864EB5D' and c.target_pin_name=='B')
    if incoming.source_node_id!='556BBE144B3205261C7028A472C5CFDC':
        return
    ids=build(g,[get('Player','ObservedPlayer'),call('TargetPos','Actor','K2_GetActorLocation'),
        call('BossPos','Actor','K2_GetActorLocation'),call('Difference','KismetMathLibrary','Subtract_VectorVector'),
        get('Direction','AttackStepDirection'),call('Ahead','KismetMathLibrary','Dot_VectorVector'),
        call('PunchFrontRoom','KismetMathLibrary','Subtract_DoubleDouble'),call('Nonnegative','KismetMathLibrary','FMax'),
        call('BoundDelta','KismetMathLibrary','FMin'),get('Action','ActiveAction'),
        node('ID','member_get',**{'class':'/Game/BossArena/Boss/AI/BP_BossActionDefinition','member':'ActionId'}),
        call('Left','KismetMathLibrary','EqualEqual_IntInt'),call('Right','KismetMathLibrary','EqualEqual_IntInt'),
        call('Ordinary','KismetMathLibrary','BooleanOR'),call('ChooseDelta','KismetMathLibrary','SelectFloat')],[
        ('Player.ObservedPlayer','TargetPos.self'),('TargetPos.ReturnValue','Difference.A'),
        ('BossPos.ReturnValue','Difference.B'),('Difference.ReturnValue','Ahead.A'),
        ('Direction.AttackStepDirection','Ahead.B'),('Ahead.ReturnValue','PunchFrontRoom.A'),
        ('PunchFrontRoom.ReturnValue','Nonnegative.A'),('Nonnegative.ReturnValue','BoundDelta.B'),
        ('556BBE144B3205261C7028A472C5CFDC.ReturnValue','BoundDelta.A'),
        ('Action.ActiveAction','ID.self'),('ID.ActionId','Left.A'),('ID.ActionId','Right.A'),
        ('Left.ReturnValue','Ordinary.A'),('Right.ReturnValue','Ordinary.B'),
        ('BoundDelta.ReturnValue','ChooseDelta.A'),('556BBE144B3205261C7028A472C5CFDC.ReturnValue','ChooseDelta.B'),
        ('Ordinary.ReturnValue','ChooseDelta.bPickA')],[
        ('PunchFrontRoom','B',175),('Nonnegative','B',0),('Left','B',0),('Right','B',1)])
    assert S.disconnect_pin(B,g,'32E0E13F470C773B8203139C0864EB5D','B')
    assert S.connect_nodes(B,g,ids['ChooseDelta'],'ReturnValue','32E0E13F470C773B8203139C0864EB5D','B')


def qa():
    g='RecordCombatQA'
    if any('PunchRetreatAllowance' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    write='7351315649F7330AF5C248810231A881'
    before=next(c for c in S.get_connections(B,g) if c.target_node_id==write and c.target_pin_name=='InString')
    ids=build(g,[get('Allowance','PunchRetreatAllowance'),get('Requested','AttackStepDistance'),
        call('AddAllowance','KismetStringLibrary','BuildString_Double'),call('AddRequest','KismetStringLibrary','BuildString_Double')],[
        (before.source_node_id+'.'+before.source_pin_name,'AddAllowance.AppendTo'),
        ('Allowance.PunchRetreatAllowance','AddAllowance.InDouble'),('AddAllowance.ReturnValue','AddRequest.AppendTo'),
        ('Requested.AttackStepDistance','AddRequest.InDouble')],[
        ('AddAllowance','Prefix','|retreat_allowance='),('AddRequest','Prefix','|step_distance=')])
    assert S.disconnect_pin(B,g,write,'InString')
    assert S.connect_nodes(B,g,ids['AddRequest'],'ReturnValue',write,'InString')
    assert S.add_comment_around_nodes(B,g,'PunchRetreatAllowance: QA fields',list(ids.values()))


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    if 'bPunchFootSync' in {v.variable_name for v in S.list_variables(B)}:
        raise RuntimeError('Archived generic punch travel: use ApplyPunchFootSync.py to retain the measured foot timing.')
    budget();reach();body_clearance();qa();retime_montages()
    result=S.compile_blueprint(B)
    assert result.success and not result.errors and not result.warnings,(result.errors,result.warnings)
    print('COMPILED',B,'errors=0 warnings=0')
    assert unreal.EditorAssetLibrary.save_asset(B)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==H.asset(B).generated_class():
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
            print('MODIFIED placed capsule Visibility Ignore',actor.get_path_name())
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('SAVED forward reach; no PIE')


if __name__=='__main__':
    apply()
