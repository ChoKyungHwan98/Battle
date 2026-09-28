"""Repair the live AnimBP locomotion path and use a valid 2D BlendSpace grid.

Run once inside Unreal Editor through execute_python_code. Source BlendSpace
and the first SwordShield BlendSpace are preserved for comparison/rollback.
"""
import unreal
import vibeue

A='/Game/BossArena/Player/Animation/ABP_Player_Combat'
B='/Game/BossArena/Player/Animation/SwordShield'
SOURCE='/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run'
DEST=B+'/BS_SwordShield_8Dir_Runtime'

assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
if not unreal.EditorAssetLibrary.does_asset_exist(DEST):
    assert unreal.EditorAssetLibrary.duplicate_asset(SOURCE,DEST)
    print('CREATED:',DEST)
bs=unreal.load_asset(DEST)
samples=bs.get_editor_property('sample_data')
assert len(samples)==27,len(samples)

walk={-180:('Sword_WalkBwd',1),-135:('Sword_StrafeLeft135',5),
      -90:('Sword_StrafeLeft',1),-45:('Sword_StrafeLeft45',5),
        0:('Sword_WalkFwd',1),45:('Sword_StrafeRight45',5),
       90:('Sword_StrafeRight',1),135:('Sword_StrafeRight135',5),
      180:('Sword_WalkBwd',1)}
run={-180:('Sword_RunBwd',1),-135:('Sword_RunStrafeLeft135',5),
     -90:('Sword_StrafeRunLeft',1),-45:('Sword_RunStrafeLeft45',5),
       0:('Sword_RunFwd',1),45:('Sword_RunStrafeRight45',5),
      90:('Sword_StrafeRunRight',1),135:('Sword_RunStrafeRight135',5),
     180:('Sword_RunBwd',1)}

for i,sample in enumerate(samples):
    value=sample.get_editor_property('sample_value')
    angle, speed=int(round(value.x)),int(round(value.y))
    if speed==0:
        name,part='Sword_Idle',1
    elif speed==300:
        name,part=walk[angle]
    elif speed==600:
        name,part=run[angle]
    else:
        raise ValueError((i,angle,speed))
    clip=B+'/Sequences/Q_SwordShieldAnimsetPro_part%d_%s'%(part,name)
    anim=unreal.load_asset(clip)
    assert anim,clip
    sample.set_editor_property('animation',anim)
    if speed==600:
        sample.set_editor_property('rate_scale',1.15)
    samples[i]=sample
bs.set_editor_property('sample_data',samples)
assert all(s.get_editor_property('animation').get_path_name().startswith(B) for s in bs.get_editor_property('sample_data'))
assert unreal.EditorAssetLibrary.save_asset(DEST)
print('MODIFIED:',DEST,'27 valid-grid sample references')

ag=unreal.AnimGraphService
idle='2D2942B34EC2FFFFDD1C499DAB66A458'
moving='BAD6C3BB4442EFF4F242D89329E2C52C'
assert ag.set_sequence_player_asset(A,'Idle',idle,B+'/Sequences/Q_SwordShieldAnimsetPro_part1_Sword_Idle')
assert ag.set_blend_space_asset(A,'Walk / Run',moving,DEST)
unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(A))
assert unreal.EditorAssetLibrary.save_asset(A)
print('MODIFIED:',A,'live Idle and Walk / Run state nodes')
