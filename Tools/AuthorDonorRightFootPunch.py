"""Use Crunch's authored right step and weight transfer, not solved planted legs.

Unreal MCP only. Upper-body punch timing is retained. Lower body comes from
Jog_Fwd_Start; support-foot displacement supplies root motion. No leg IK bake.
"""
import math
import json
from pathlib import Path
import unreal
import vibeue
import AuthorRightFootLeftPunch as R

DONOR='/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Jog_Fwd_Start'
SEQ=R.ROOT+'AS_Left_RightFootPlant_Donor'
MONTAGE=R.ROOT+'AM_Boss_Left_RightFootPlant_Donor'
PREFIX=.65
OFFSET=PREFIX-R.CONSUMED
TRAVEL=205/1.3
SWITCH=.74
PUNCH_DONOR=.92
COLLECT_DONOR=1.15


def qangle(a,b):
    return math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(a.to_tuple(),b.to_tuple()))))))


def prepare():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    base=unreal.EditorAssetLibrary.load_asset(R.BASE)
    mp=base.get_editor_property('Montage').get_path_name().split('.')[0]
    segments=list(R.AMS.list_anim_segments(mp,0))
    source,recovery=segments[0].anim_sequence_path,segments[1].anim_sequence_path
    profile=unreal.SkeletonService.create_skeleton_profile(unreal.EditorAssetLibrary.load_asset(source).get_editor_property('skeleton').get_path_name())
    hierarchy=list(profile.bone_hierarchy); parents={str(b.bone_name):str(b.parent_bone_name) for b in hierarchy}
    upper=set()
    for bone in hierarchy:
        n=str(bone.bone_name); p=n
        while p:
            if p=='spine_01': upper.add(n);break
            p=parents[p]
    idle=R.pose(R.IDLE,0); windup=R.pose(source,R.CONSUMED)
    def donor(t): return R.pose(DONOR,t)
    def dg(t): return R.globals_for(donor(t),hierarchy)
    origin=dg(0)['foot_l'].translation.y
    pre=[(i/120,origin-dg(i/120)['foot_l'].translation.y) for i in range(round(SWITCH*120)+1)]
    pre_root=max(v for _,v in pre)
    right_pin=pre_root+dg(SWITCH)['foot_r'].translation.y
    def advance(t):
        if t<=SWITCH:
            return max(0.,max(v for s,v in pre if s<=t+1/120))
        return right_pin-dg(t)['foot_r'].translation.y
    lo,hi=SWITCH,.9
    for _ in range(18):
        mid=(lo+hi)*.5
        if advance(mid)<TRAVEL: lo=mid
        else: hi=mid
    donor_end=(lo+hi)*.5
    at_punch=dg(PUNCH_DONOR)
    left_pin=advance(PUNCH_DONOR)+at_punch['foot_l'].translation.y
    length=segments[1].start_time+segments[1].duration+OFFSET
    # The inherited compression target is 30fps; 60fps authored frames must end
    # on an even frame, or compression sees a half-frame endpoint and asserts.
    frames=2*math.ceil(length*R.FPS/2)
    keys=[];metrics=[]
    for f in range(frames+1):
        t=min(f/R.FPS,length); old_t=max(R.CONSUMED,t-OFFSET)
        if t<=PREFIX:
            punch={b:R.blend(idle[b],windup[b],R.smooth(t/PREFIX)) for b in idle}
        elif old_t<segments[1].start_time:
            punch=R.pose(source,old_t)
        else:
            punch=R.pose(recovery,min((old_t-segments[1].start_time)*segments[1].play_rate,segments[1].anim_end_pos))
        if t<=PREFIX:
            dt=t/PREFIX*donor_end
            mesh_advance=advance(dt); root_advance=min(TRAVEL,mesh_advance)
        elif t<=PREFIX+.1:
            dt=donor_end+(PUNCH_DONOR-donor_end)*(t-PREFIX)/.1
            mesh_advance=advance(dt);root_advance=TRAVEL
        else:
            dt=PUNCH_DONOR+(COLLECT_DONOR-PUNCH_DONOR)*min(1.,(t-PREFIX-.1)/.35)
            mesh_advance=left_pin-dg(dt)['foot_l'].translation.y;root_advance=TRAVEL
        lower=donor(dt)
        p=lower['pelvis'];p.translation=p.translation+unreal.Vector(0,mesh_advance-root_advance,0);lower['pelvis']=p
        # Collect the lifted trailing foot and settle into the idle stance during recovery.
        settle=R.smooth((t-(PREFIX+.45))/.6)
        if settle:
            lower={b:R.blend(lower[b],idle[b],settle) for b in lower}
        local=dict(lower)
        for b in upper: local[b]=punch[b]
        local['root']=R.transform(unreal.Vector(0,root_advance,0),unreal.Quat(0,0,0,1))
        # Preserve the punch's pelvis/torso orientation so its fist origin is unchanged.
        # Counter-transform leg roots: their WORLD poses remain the authored donor poses.
        lower_g=R.globals_for(local,hierarchy)
        pelvis=local['pelvis'];pelvis.rotation=punch['pelvis'].rotation;local['pelvis']=pelvis
        new_pelvis=R.globals_for(local,hierarchy)['pelvis']
        for bone in hierarchy:
            name=str(bone.bone_name)
            if str(bone.parent_bone_name)=='pelvis' and (name in ['thigh_l','thigh_r','hip_l','hip_r'] or name.startswith('thigh_pneu')):
                local[name]=lower_g[name].make_relative(new_pelvis)
        keys.append(local)
        g=R.globals_for(local,hierarchy)
        metrics.append({'time':f/R.FPS,'donor_time':dt,'root_y':root_advance,
            'left':g['foot_l'].translation.to_tuple(),'right':g['foot_r'].translation.to_tuple(),
            'hand':g['hand_l'].translation.to_tuple(),'pelvis':g['pelvis'].translation.to_tuple(),
            'root_compensation':mesh_advance-root_advance,'settle':settle})
    globals_rows=[R.globals_for(k,hierarchy) for k in keys]
    rotations={b:max(qangle(a[b].rotation,c[b].rotation) for a,c in zip(globals_rows,globals_rows[1:])) for b in ['pelvis','thigh_l','calf_l','thigh_r','calf_r']}
    support_error=max(abs(m['right'][1]-right_pin) for m in metrics if PREFIX<=m['time']<=PREFIX+.1)
    print('PREVIEW DONOR',{'end_source_time':donor_end,'authored_travel_cm':TRAVEL*1.3,
        'global_frame_rotation_degrees':rotations,'planted_right_y_error_cm':support_error})
    assert max(v for b,v in rotations.items() if b!='pelvis')<12,rotations
    assert support_error<.01
    assert metrics[0]['left'][1]>metrics[0]['right'][1]
    assert metrics[round(PREFIX*R.FPS)]['right'][1]>metrics[round(PREFIX*R.FPS)]['left'][1]
    return {'base':base,'source':source,'montage':mp,'profile':profile,'keys':keys,'metrics':metrics,
        'frames':frames,'length':length,'hierarchy':hierarchy,'rotations':rotations,
        'right_support_error':support_error,'donor_end':donor_end,'report_file':'right_foot_donor_authoring.json'}


def apply(plan):
    saved=(R.SEQ,R.MONTAGE,R.OFFSET,R.PREFIX,R.TRAVEL)
    R.SEQ,R.MONTAGE,R.OFFSET,R.PREFIX,R.TRAVEL=SEQ,MONTAGE,OFFSET,PREFIX,TRAVEL
    try: R.apply(plan)
    finally: R.SEQ,R.MONTAGE,R.OFFSET,R.PREFIX,R.TRAVEL=saved
    card=unreal.EditorAssetLibrary.load_asset(R.CARD)
    card.modify();card.set_editor_property('MinDistance',345);card.set_editor_property('MaxDistance',550)
    card.set_editor_property('DisplayName','오른발 디딤 → 왼손 · 550cm 목표')
    assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
    report={'sequence':SEQ,'montage':MONTAGE,'card':R.CARD,'goal_reach_cm':550,'authored_travel_cm':205,
        'source_lower_body':DONOR,'global_frame_rotation_degrees':plan['rotations'],
        'planted_right_y_error_cm':plan['right_support_error'],'metrics':plan['metrics'],
        'arena_unchanged':True,'actual_contact_verified':False}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/right_foot_donor_polish.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED',R.CARD,'goal 345..550; accepted prototype sequence preserved')
    return str(path)
