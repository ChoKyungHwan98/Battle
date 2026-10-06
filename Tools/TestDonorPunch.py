"""Runtime contact fixture without OS input. Fetch live objects only inside calls."""
import unreal
import json
from pathlib import Path

CARD=None
SAMPLES=[]
OBSERVER=None
START_TIME=0
START_LOCATION=None
START_HEALTH=0


def actors():
    w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    p=unreal.GameplayStatics.get_player_character(w,0)
    b=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor) if a.get_class().get_name()=='BP_Boss_Crunch_C')
    return w,b,p


def tag(name):
    result=unreal.GameplayTag();result.import_text('(TagName="'+name+'")');return result


def begin(distance):
    global START_TIME,START_LOCATION,START_HEALTH,SAMPLES,OBSERVER
    w,b,p=actors()
    unreal.GameplayStatics.set_global_time_dilation(w,.05)
    for fn in ['EvaluateCombatUtility','EvaluateUtility','FinishBossIntro','FinishBossObserve','StartActionMontage','OpenActionImpact','CloseActionImpact','FinishCombatAction']:
        unreal.SystemLibrary.clear_timer(b,fn)
    b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().montage_stop(0)
    assert b.get_editor_property('BossState').export_text()=='(TagName="Boss.Combat.Ready")'
    pm=p.get_component_by_class(unreal.CharacterMovementComponent);pm.stop_movement_immediately();pm.disable_movement()
    p.set_actor_location(unreal.Vector(0,0,92),False,False)
    ph=p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    bh=b.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    b.set_actor_location(unreal.Vector(distance,0,92+bh-ph),False,False)
    b.set_actor_rotation(unreal.Rotator(yaw=180),False)
    START_TIME=unreal.GameplayStatics.get_time_seconds(w);START_LOCATION=b.get_actor_location().to_tuple();START_HEALTH=p.get_editor_property('CurrentHealth');SAMPLES=[]
    OBSERVER=unreal.register_slate_post_tick_callback(sample)
    print('FIXTURE_PLACED',distance,b.get_editor_property('BossState').export_text())
    return 1


def sample(_):
    w,b,p=actors()
    mesh=b.get_component_by_class(unreal.SkeletalMeshComponent);anim=mesh.get_anim_instance()
    m=anim.get_current_active_montage()
    # The current Blueprint sweeps the visible hand socket, not the archived
    # hand_slide PhysicsAsset capsule used by TestApprovedDS3.
    a=z=mesh.get_socket_location('hand_l')
    cap=p.get_component_by_class(unreal.CapsuleComponent)
    SAMPLES.append({'t':unreal.GameplayStatics.get_time_seconds(w)-START_TIME,
        'boss':b.get_actor_location().to_tuple(),'player':p.get_actor_location().to_tuple(),
        'hand':mesh.get_socket_location('hand_l').to_tuple(),'foot_l':mesh.get_socket_location('foot_l').to_tuple(),
        'foot_r':mesh.get_socket_location('foot_r').to_tuple(),'hp':p.get_editor_property('CurrentHealth'),
        'state':b.get_editor_property('BossState').export_text(),'open':bool(b.get_editor_property('bPhysicalStrikeOpen')),
        'hit':bool(b.get_editor_property('bPhysicalStrikeHit')),'montage':m.get_name() if m else '',
        'montage_time':anim.montage_get_position(m) if m else 0,
        'contact_ends':[a.to_tuple(),z.to_tuple()],
        'player_visibility':str(cap.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)),
        'player_invincible':bool(p.get_editor_property('bInvincible')),
        'strike_socket':str(b.get_editor_property('PhysicalStrikeSocket')),
        'hand_radius':b.get_editor_property('PhysicalHandRadiusLocal')})


def finish(distance):
    global OBSERVER
    if OBSERVER is not None: unreal.unregister_slate_post_tick_callback(OBSERVER);OBSERVER=None
    path=Path(unreal.Paths.project_saved_dir())/f'VibeUE/Reports/donor_contact_{distance}.json'
    path.write_text(json.dumps({'distance':distance,'start_health':START_HEALTH,'samples':SAMPLES},ensure_ascii=False,indent=2),encoding='utf-8')
    print('FIXTURE_RESULT',distance,'damage',damage(),'travel',travel(),'samples',len(SAMPLES))
    return 1


def damage(): return START_HEALTH-min(s['hp'] for s in SAMPLES)
def travel(): return max(abs(s['boss'][0]-START_LOCATION[0]) for s in SAMPLES)
def montage_ok(): return int(any(s['montage']=='AM_Boss_Left_RightFootPlant_Donor' for s in SAMPLES))


def scenario(distance=550,expected_damage=110):
    module="__import__('TestDonorPunch')"
    return {'name':f'Donor foot-plant punch at {distance}cm; no OS input',
        'dependencies':['Tools/TestDonorPunch.py','Content/BossArena/Boss/Animations/AS_Left_RightFootPlant_Donor.uasset',
            'Content/BossArena/Boss/Animations/AM_Boss_Left_RightFootPlant_Donor.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset','Content/BossArena/Boss/Blueprints/BP_Boss_Crunch.uasset'],
        'steps':[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},{'action':'wait','seconds':.5},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'python_assert_number','expression':f'{module}.begin({distance})','operator':'eq','expected':1},
            {'action':'inject_key','key':'One'},
            {'action':'wait','seconds':45},
            {'action':'python_assert_number','expression':f'{module}.finish({distance})','operator':'eq','expected':1},
            {'action':'python_assert_number','expression':f'{module}.montage_ok()','operator':'eq','expected':1},
            {'action':'python_assert_number','expression':f'{module}.travel()','operator':'eq','expected':205,'tolerance':3},
            {'action':'python_assert_number','expression':f'{module}.damage()','operator':'eq','expected':expected_damage,'tolerance':.01}],
        'teardown':{'stop_pie':True}}
