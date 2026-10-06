"""Author a lab-only right-foot plant and left swing. Unreal MCP only; no PIE.

Local bone keys are solved from component-space foot anchors. Animation root +Y
owns travel; the old manual attack-step notify is not copied to this montage.
"""
import math
import json
from pathlib import Path
import unreal
import vibeue

ROOT = '/Game/BossArena/Boss/Animations/'
SEQ = ROOT+'AS_Left_RightFootPlant'
MONTAGE = ROOT+'AM_Boss_Left_RightFootPlant'
CARD = '/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant'
BASE = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Left'
IDLE = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Idle_Combat'
FPS = 60
PREFIX, CONSUMED = .5, .3
OFFSET = PREFIX-CONSUMED
TRAVEL = 110/1.3  # Animation-space cm; placed scale 1.3 => authored 110cm.
ASS, AMS = unreal.AnimSequenceService, unreal.AnimMontageService


def smooth(a):
    a = max(0., min(1., a))
    return a*a*(3-2*a)


def pose(path, t):
    return {str(p.bone_name): p.transform for p in ASS.get_pose_at_time(path, t, False)}


def transform(location, rotation=None, scale=None):
    value=unreal.Transform()
    value.translation=location
    if rotation is not None: value.rotation=rotation
    if scale is not None: value.scale3d=scale
    return value


def blend(a, b, weight):
    return transform(location=a.translation+(b.translation-a.translation)*weight,
        rotation=a.rotation.slerp_quat(b.rotation,weight),
        scale=a.scale3d+(b.scale3d-a.scale3d)*weight)


def globals_for(local, hierarchy):
    result = {}
    for bone in hierarchy:
        name, parent = str(bone.bone_name), str(bone.parent_bone_name)
        result[name] = local[name].multiply(result[parent]) if parent else local[name]
    return result


def length(v):
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


def unit(v):
    return v/max(length(v),1e-8)


def dot(a,b):
    return a.x*b.x+a.y*b.y+a.z*b.z


def cross(a,b):
    return unreal.Vector(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x)


def between(a,b):
    a,b = unit(a),unit(b)
    d = dot(a,b)
    if d < -.99999:
        axis = unit(cross(a,unreal.Vector(0,0,1)))
        return unreal.Quat(axis.x,axis.y,axis.z,0)
    c = cross(a,b)
    return unreal.Quat(c.x,c.y,c.z,1+d).normalized()


def solve_leg(local, hierarchy, parents, side, target):
    g = globals_for(local,hierarchy)
    thigh,calf,foot = ['thigh_'+side,'calf_'+side,'foot_'+side]
    h,k,f = [g[b].translation for b in [thigh,calf,foot]]
    a,b = length(k-h),length(f-k)
    delta = target.translation-h
    d = length(delta)
    assert abs(a-b)+.001 < d < a+b-.001, (side,d,a+b)
    axis = unit(delta)
    pole = k-h-axis*dot(k-h,axis)
    if length(pole) < .001:
        pole = unreal.Vector(0,1,0)-axis*dot(unreal.Vector(0,1,0),axis)
    along = (a*a-b*b+d*d)/(2*d)
    knee = h+axis*along+unit(pole)*math.sqrt(max(0.,a*a-along*along))
    rotated = transform(location=h,
        rotation=between(k-h,knee-h).multiply(g[thigh].rotation),scale=g[thigh].scale3d)
    local[thigh] = rotated.make_relative(g[parents[thigh]])
    g = globals_for(local,hierarchy)
    rotated = transform(location=g[calf].translation,
        rotation=between(g[foot].translation-g[calf].translation,
                         target.translation-g[calf].translation).multiply(g[calf].rotation),
        scale=g[calf].scale3d)
    local[calf] = rotated.make_relative(g[parents[calf]])
    g = globals_for(local,hierarchy)
    rotated = transform(location=g[foot].translation,rotation=target.rotation,scale=g[foot].scale3d)
    local[foot] = rotated.make_relative(g[parents[foot]])
    error = length(globals_for(local,hierarchy)[foot].translation-target.translation)
    assert error < .01, (side,error)
    return error


def prepare():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    base = unreal.EditorAssetLibrary.load_asset(BASE)
    mp = base.get_editor_property('Montage').get_path_name().split('.')[0]
    segments = list(AMS.list_anim_segments(mp,0))
    assert len(segments)==2 and segments[0].anim_start_pos==0
    source, recovery = segments[0].anim_sequence_path,segments[1].anim_sequence_path
    skeleton = unreal.EditorAssetLibrary.load_asset(source).get_editor_property('skeleton').get_path_name()
    profile = unreal.SkeletonService.create_skeleton_profile(skeleton)
    assert profile.is_valid
    hierarchy = list(profile.bone_hierarchy)
    parents = {str(b.bone_name):str(b.parent_bone_name) for b in hierarchy}
    idle = pose(IDLE,0)
    idle_global = globals_for(idle,hierarchy)
    windup = pose(source,CONSUMED)
    old_length = segments[1].start_time+segments[1].duration
    new_length = old_length+OFFSET
    frames = math.ceil(new_length*FPS)
    keys, metrics = [], []
    for frame in range(frames+1):
        t = min(frame/FPS,new_length)
        old_t = max(CONSUMED,t-OFFSET)
        if t <= PREFIX:
            local = {b:blend(idle[b],windup[b],smooth(t/PREFIX)) for b in idle}
        elif old_t < segments[1].start_time:
            local = pose(source,old_t)
        else:
            local = pose(recovery,min((old_t-segments[1].start_time)*segments[1].play_rate,
                                      segments[1].anim_end_pos))
        travel = TRAVEL*smooth((t-.12)/(PREFIX-.12))
        local['root'] = transform(location=unreal.Vector(0,travel,0),rotation=unreal.Quat(0,0,0,1))
        # A right-lead plant needs stable hips; retain the source torso turn above them.
        old_global=globals_for(local,hierarchy)
        p=local['pelvis']; p.rotation=idle['pelvis'].rotation.slerp_quat(p.rotation,.3); local['pelvis']=p
        stable_global=globals_for(local,hierarchy)
        spine=local['spine_01']
        spine.rotation=old_global['spine_01'].make_relative(stable_global[parents['spine_01']]).rotation
        local['spine_01']=spine
        global_pose = globals_for(local,hierarchy)
        targets = {}
        for side in ['l','r']:
            start = idle_global['foot_'+side]
            if side=='l':
                target = transform(location=start.translation,rotation=start.rotation)
                collect_start,collect_end = 1.45+OFFSET,1.8+OFFSET
            else:
                alpha = smooth((t-.06)/(PREFIX-.06))
                target = transform(location=unreal.Vector(start.translation.x,
                    start.translation.y+(116-start.translation.y)*alpha,
                    start.translation.z+26*math.sin(math.pi*alpha)),rotation=start.rotation)
                collect_start,collect_end = 1.8+OFFSET,new_length
            collect = smooth((t-collect_start)/(collect_end-collect_start))
            if collect>0:
                goal = global_pose['foot_'+side]
                target = blend(target,goal,collect)
                target.translation = target.translation+unreal.Vector(0,0,18*math.sin(math.pi*collect))
            targets[side] = target
        # Keep both knees within their original bone lengths, with a shared crouch.
        # The original left-lead punch carries its pelvis beyond the new support feet.
        # Keep weight over the planted stance instead of forcing a deep squat.
        global_pose=globals_for(local,hierarchy)
        support_y=(targets['l'].translation.y+targets['r'].translation.y)*.5+15
        excess=max(0.,global_pose['pelvis'].translation.y-support_y)
        if excess:
            p=local['pelvis']; p.translation=p.translation-unreal.Vector(0,excess,0); local['pelvis']=p
        drop = 0.
        for _ in range(41):
            global_pose = globals_for(local,hierarchy)
            fits = True
            for side in ['l','r']:
                h,k,f = [global_pose[b+'_'+side].translation for b in ['thigh','calf','foot']]
                if length(targets[side].translation-h) >= length(k-h)+length(f-k)-.5:
                    fits = False
            if fits: break
            p=local['pelvis']; p.translation=p.translation-unreal.Vector(0,0,1); local['pelvis']=p; drop+=1
        assert fits, ('Leg reach exceeds safe range',frame)
        errors = [solve_leg(local,hierarchy,parents,side,targets[side]) for side in ['l','r']]
        keys.append(local)
        g=globals_for(local,hierarchy)
        metrics.append({'time':frame/FPS,'root_y':travel,'pelvis_drop':drop,
            'left':g['foot_l'].translation.to_tuple(),'right':g['foot_r'].translation.to_tuple(),
            'error':max(errors)})
    print('PREVIEW authored root travel',round(TRAVEL,3),'local cm; right foot leads at plant;',
          'max crouch',max(m['pelvis_drop'] for m in metrics),'cm; max IK error',max(m['error'] for m in metrics))
    assert metrics[0]['left'][1]>metrics[0]['right'][1]
    assert metrics[int(PREFIX*FPS)]['right'][1]>metrics[int(PREFIX*FPS)]['left'][1]
    assert max(length(unreal.Vector(*m['left'])-idle_global['foot_l'].translation)
               for m in metrics[:int((1.45+OFFSET)*FPS)+1]) < .01
    return {'base':base,'source':source,'montage':mp,'profile':profile,'keys':keys,'metrics':metrics,
            'frames':frames,'length':new_length,'hierarchy':hierarchy}


def apply(plan):
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    dirty = {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    assert not {SEQ,MONTAGE,CARD,BASE}.intersection(dirty)
    # Separate assets preserve the current stationary punch and source clips.
    clip = unreal.EditorAssetLibrary.load_asset(SEQ) if unreal.EditorAssetLibrary.does_asset_exist(SEQ) else unreal.EditorAssetLibrary.duplicate_asset(plan['source'],SEQ)
    assert clip
    print('CREATED_OR_UPDATED',SEQ)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(clip)
    tracks = list(clip.get_editor_property('data_model_interface').get_bone_track_names())
    # Preview the proposed local rotations/translations before writing any keys.
    for frame in [0,12,24,30,42,60]:
        original = pose(SEQ,min(frame/FPS,clip.get_play_length()))
        deltas=[]
        for bone in ['pelvis','spine_01','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']:
            goal,old=plan['keys'][frame][bone],original[bone]
            delta=goal.rotation.multiply(old.rotation.inversed())
            deltas.append(unreal.BoneDelta(bone_name=bone,rotation_delta=delta.rotator(),
                translation_delta=goal.translation-old.translation))
        result=ASS.preview_pose_delta(SEQ,deltas,'local',frame)
        assert result and result.success
        validation=ASS.validate_pose(SEQ,False)
        ASS.cancel_preview(SEQ)
        assert validation and validation.is_valid, list(validation.violation_messages)
    clip.modify()
    clip.set_editor_property('enable_root_motion',True)
    clip.set_editor_property('force_root_lock',False)
    clip.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    ctl=clip.get_editor_property('controller')
    ctl.open_bracket('Right-foot plant, pinned support feet, original left arm motion')
    try:
        ctl.set_frame_rate(unreal.FrameRate(FPS,1))
        ctl.set_number_of_frames(unreal.FrameNumber(plan['frames']))
        for bone in tracks:
            transforms=[p[str(bone)] for p in plan['keys']]
            assert ctl.set_bone_track_keys(bone,[p.translation for p in transforms],
                [p.rotation for p in transforms],[p.scale3d for p in transforms])
    finally:
        ctl.close_bracket()
    assert unreal.EditorAssetLibrary.save_loaded_asset(clip,False)
    # New single-sequence montage retains the base physical/FX notify classes.
    if not unreal.EditorAssetLibrary.does_asset_exist(MONTAGE):
        assert AMS.create_montage_from_animation(SEQ,ROOT.rstrip('/'),MONTAGE.rsplit('/',1)[-1])
        print('CREATED',MONTAGE)
        assert AMS.set_slot_name(MONTAGE,0,'UpperBody')
        montage=unreal.EditorAssetLibrary.load_asset(MONTAGE)
        # Clear inherited sequence notifies on the new sequence only, if any.
        assert not AMS.list_notifies(MONTAGE)
        unreal.AnimationLibrary.add_animation_notify_track(montage,'ContactFX',unreal.LinearColor(1,.4,.1,1))
        particle = next(o for o in unreal.ObjectIterator(unreal.AnimNotifyState)
                        if o.get_outer()==plan['base'].get_editor_property('Montage') and 'ScaledParticle' in o.get_name())
        for name,start,duration,cls in [('FistFire',.106667+OFFSET,.843333,particle.get_class()),
                ('PhysicalStrike0',.346667+OFFSET,.14,
                 unreal.EditorAssetLibrary.load_asset(ROOT+'Notifies/ANS_PhysicalStrike_0').generated_class())]:
            obj=unreal.AnimationLibrary.add_animation_notify_state_event(montage,'ContactFX',start,duration,cls)
            assert obj
            if name=='FistFire':
                for prop in ['FXScale','MatchSocket','MatchTemplate']:
                    obj.set_editor_property(prop,particle.get_editor_property(prop))
        assert AMS.set_blend_in(MONTAGE,.1,'Cubic')
        assert AMS.set_blend_out(MONTAGE,.16,'Cubic')
        assert AMS.set_enable_root_motion_translation(MONTAGE,True)
        assert AMS.set_enable_root_motion_rotation(MONTAGE,False)
    montage=unreal.EditorAssetLibrary.load_asset(MONTAGE)
    assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
    card=unreal.EditorAssetLibrary.load_asset(CARD) if unreal.EditorAssetLibrary.does_asset_exist(CARD) else unreal.EditorAssetLibrary.duplicate_asset(BASE,CARD)
    assert card
    card.modify();card.set_editor_property('Montage',montage)
    card.set_editor_property('DisplayName','오른발 디딤 → 왼손 휘두르기 · 랩 비교')
    rate=plan['base'].get_editor_property('PlayRate')
    card.set_editor_property('ImpactTimes',[t+OFFSET/rate for t in plan['base'].get_editor_property('ImpactTimes')])
    card.set_editor_property('HitWindowEnds',[t+OFFSET for t in plan['base'].get_editor_property('HitWindowEnds')])
    card.set_editor_property('TotalSeconds',clip.get_play_length()/rate+plan['base'].get_editor_property('TelegraphSeconds')+.05)
    card.set_editor_property('DashMaxDistance',0)
    assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
    print('MODIFIED',CARD,'original action ID and damage; retimed contact/FX; root owns travel')
    report={'sequence':SEQ,'montage':MONTAGE,'card':CARD,'prefix_source_seconds':PREFIX,
        'consumed_original_windup_seconds':CONSUMED,'authored_travel_local_cm':TRAVEL,
        'authored_travel_at_scale_1_3_cm':110,'contact_window_montage':[.346667+OFFSET,.486667+OFFSET],
        'metrics':plan['metrics'],'gameplay_verified':False,'arena_unchanged':True}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/right_foot_left_punch_20261006.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return str(path)
