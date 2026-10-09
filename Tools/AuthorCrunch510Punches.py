"""Crunch-only longer lunges; separate outputs, unchanged physical hand radius.

Reuse the approved punch timings and the editable Rig/Sequencer pipeline.
The rear foot follows after support transfer, instead of stretching a planted leg.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util

MODULES={}

def configure(key,travel=None):
    assert key in (1,2)
    stem='TuneCrunchLeftReach' if key==1 else 'PolishCrunchRightPunch'
    name='Crunch510Left' if key==1 else 'Crunch510Right'
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(stem+'.py'))
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    m=module
    suffix='LeftSwing510' if key==1 else 'RightCross510'
    m.BASE=common.ROOT+'/AS_Crunch_'+suffix+'_Base'
    m.SEQ=common.ROOT+'/LS_Crunch_'+suffix
    m.BAKED=common.ROOT+'/AS_Crunch_'+suffix
    m.MONTAGE=common.ROOT+'/AM_Crunch_'+suffix
    m.DISPLAY=('오른발 디딤 + 왼손' if key==1 else '오른발 디딤 + 오른손')+' · 510cm'
    m.TRAVEL=travel if travel is not None else (140. if key==1 else 155.)
    m.PEEL_START,m.TOE_OFF,m.LAND=(.04,.10,.33) if key==1 else (.02,.08,.33)
    m.BODY_START,m.BODY_END=(.16,.445) if key==1 else (.12,.425)
    m.LAND_AHEAD=120. if key==1 else 125.
    m.LEFT_ADJUST=(m.LAND,m.LAND+.18)
    m.HIP_CACHE={}
    # Foot follows into a stable rear stance; the original source foot keys do
    # not govern the support phase of this longer lunge.
    old_flat=m.flat_feet
    def flat_feet(t,source):
        feet=old_flat(t,source)
        if m.TOE_OFF<t<m.LAND:
            # Lift the heel first; forward flight follows body acceleration.
            # Sending the ankle ahead on the earlier short-step curve would
            # put it outside the leg's reachable sphere before the hips move.
            ahead=common.between(t,m.TOE_OFF+.03,m.LAND)
            feet['r'].translation.y=m.PLAN['initial']['foot_r'].translation.y+(m.PLAN['landing'].translation.y-m.PLAN['initial']['foot_r'].translation.y)*ahead
            hip_y=m.HIP_CACHE.get(round(t,6),source['thigh_r'].translation.y+m.root_at(t))
            feet['r'].translation.y=min(feet['r'].translation.y,hip_y+83.)
        phase=common.between(t,*m.LEFT_ADJUST)
        target=common.copy_transform(m.PLAN['initial']['foot_l'])
        target.translation.y+=m.TRAVEL*.78
        left=util.blend(m.PLAN['initial']['foot_l'],target,phase)
        left.translation.z+=9.*math.sin(math.pi*phase)**2
        # Keep the support stance through the punch, then return to the
        # approved idle stance at the advanced body position during recovery.
        home=common.copy_transform(source['foot_l'])
        home.translation.y+=m.root_at(t)
        left=util.blend(left,home,common.between(t,1.30,1.92 if key==1 else 2.10))
        feet['l']=left
        return feet
    m.flat_feet=flat_feet
    # The heel pushes off for support transfer, then follows its airborne foot.
    old_counter=m.toe_counter
    def toe_counter(side,t):
        if side=='l':return 1.-common.between(t,m.LAND,m.LAND+.04)
        return old_counter(side,t)
    m.toe_counter=toe_counter
    m.left_pitch=lambda t:m.curve(t,[(.25,0.),(m.LAND,16.),(m.LAND+.07,0.),(2.1,0.)])
    old_base=m.base_pose
    m.DROP_SAMPLES=[]
    def base_pose(t):
        pose=old_base(t)
        source=common.poses(m.SOURCE,t,True)
        pelvis=pose['pelvis'].multiply(pose['root'])
        m.HIP_CACHE[round(t,6)]=pose['thigh_r'].multiply(pelvis).translation.y+m.root_at(t)
        goals,_=m.foot_goals(t,source)
        drop=0.
        for side in 'lr':
            hip=pose['thigh_'+side].multiply(pelvis).translation
            hip.y+=m.root_at(t)
            offset=hip-goals[side].translation
            pp=m.PLAN['initial']
            length=(pp['thigh_'+side].translation-pp['calf_'+side].translation).length()+(pp['calf_'+side].translation-pp['foot_'+side].translation).length()
            radius=length*.972
            horizontal=offset.x*offset.x+offset.y*offset.y
            assert horizontal<radius*radius,('leg cannot reach horizontally',key,t,side)
            ceiling=math.sqrt(radius*radius-horizontal)
            drop=max(drop,offset.z-ceiling)
        # Smooth, conservative absorption around the support-transfer interval.
        # Extra margin prevents a straight knee at a compressed key boundary.
        drop=max(0.,drop)
        assert drop<40.,('excessive crouch',key,t,drop)
        if drop:
            pelvis.translation.z-=drop
            pose['pelvis']=pelvis.make_relative(pose['root'])
        m.DROP_SAMPLES.append((t,drop))
        return pose
    m.base_pose=base_pose
    MODULES[key]=m
    return m

def prepare(key,travel=None):
    common.require_editor()
    m=configure(key,travel)
    m.prepare()
    print('LONG_LUNGE',key,'travel',m.TRAVEL,'pelvis_absorption_max',max(v for _,v in m.DROP_SAMPLES))
    return m

def key_and_bake(key):
    m=MODULES[key]
    m.key_step()
    return m.bake_validate()

def integrate(key):
    common.require_editor()
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    m=MODULES[key]
    report=m.PLAN['report']
    source_card=unreal.EditorAssetLibrary.load_asset(m.SRC_CARD)
    source=source_card.get_editor_property('Montage')
    montage=util.duplicate(source.get_path_name(),m.MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks=list(montage.get_editor_property('slot_anim_tracks'))
    track=tracks[0].get_editor_property('anim_track')
    segment=list(track.get_editor_property('anim_segments'))[0]
    segment.set_editor_property('anim_reference',unreal.EditorAssetLibrary.load_asset(m.BAKED))
    segment.set_editor_property('anim_end_time',source.get_play_length())
    segment.set_editor_property('anim_play_rate',1.)
    segment.set_editor_property('cached_play_length',source.get_play_length())
    track.set_editor_property('anim_segments',[segment])
    tracks[0].set_editor_property('anim_track',track)
    montage.modify();montage.set_editor_property('slot_anim_tracks',tracks)
    unreal.AnimationLibrary.remove_animation_notify_events_by_name(montage,'ANS_BossAttackStep')
    assert unreal.AnimMontageService.set_enable_root_motion_translation(m.MONTAGE,True)
    assert unreal.AnimMontageService.set_enable_root_motion_rotation(m.MONTAGE,False)
    common.save(montage)
    expected=[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(source.get_path_name()) if n.notify_name!='ANS_BossAttackStep']
    assert expected==[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(m.MONTAGE)]
    card=unreal.EditorAssetLibrary.load_asset(m.LAB_CARD)
    previous={'montage':card.get_editor_property('Montage').get_path_name(),'max_distance':card.get_editor_property('MaxDistance')}
    card.modify();card.set_editor_property('Montage',montage);card.set_editor_property('DisplayName',m.DISPLAY)
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        card.set_editor_property(name,source_card.get_editor_property(name))
    card.set_editor_property('MaxDistance',510.)
    common.save(card)
    path=Path(unreal.Paths.project_saved_dir())/f'VibeUE/Reports/crunch_510_key{key}_20261008.json'
    report={**report,'previous_card':previous,'target_range_cm':510,'range_tuned':False,
        'sequence':m.SEQ,'animation':m.BAKED,'montage':m.MONTAGE,
        'max_absorption_cm':max(v for _,v in m.DROP_SAMPLES),'support_transfer_seconds':m.LAND,'notifies':expected}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED',m.LAB_CARD,'510cm candidate',path)
    return report
