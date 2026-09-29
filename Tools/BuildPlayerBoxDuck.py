"""Build directional lock-on boxing duck prototypes in Unreal Editor Python.

The supplied BBQ clip provides the compact guard and quick close-range rhythm,
but does not show a clean, measurable duck trajectory. These prototypes retime
the project's existing directional dodge and blend its lower body with the
player jab's guard. Existing dodge assets and Blueprints are untouched.
"""

import unreal


SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
GUARD = "/Game/BossArena/Player/Animation/Prototypes/AS_Player_Jab_BBQ_Prototype"
SOURCE_DIR = "/Game/BossArena/Animations/Dodge"
OUTPUT_DIR = "/Game/BossArena/Player/Animation/Prototypes"
FPS = 30
SOURCE_TIMES = (0.0, 0.05, 0.14, 0.23, 0.31, 0.40, 0.43,
                0.50, 0.58, 0.68, 0.76, 0.82, 0.87, 0.90)
DIRECTIONS = {
    "Right": "A_INP_Dodge_01_IdleFwdRt_90",
    "Left": "A_INP_Dodge_01_IdleFwdLt_90",
    "FwdRight45": "A_INP_Dodge_01_IdleFwdRt_45",
    "FwdLeft45": "A_INP_Dodge_01_IdleFwdLt_45",
    "FwdToRight": "A_INP_Dodge_01_IdleFwd_toRight",
    "FwdToLeft": "A_INP_Dodge_01_IdleFwd_toLeft",
}


def source_weight(bone):
    if bone == "root" or bone.startswith(("ik_", "vb_")):
        return 0.0
    if bone == "pelvis":
        return 0.78
    if bone.startswith("spine_"):
        return 0.68
    if bone.startswith(("neck_", "head")):
        return 0.35
    if bone.startswith(("thigh_", "calf_", "foot_", "ball_")):
        return 0.62
    # Keep both fists high by retaining the jab prototype's guard arm pose.
    return 0.0


svc = unreal.AnimSequenceService
guard = {p.bone_name: p.transform for p in svc.get_pose_at_time(GUARD, 0.0, False)}

for side, source_name in DIRECTIONS.items():
    source = f"{SOURCE_DIR}/{source_name}"
    name = f"AS_Player_BoxDuck_{side}_Prototype"
    output = f"{OUTPUT_DIR}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(output):
        print(f"PRESERVED {output}")
        continue
    names = list(svc.get_animated_bones(source))
    samples = [{p.bone_name: p.transform for p in svc.get_pose_at_time(source, t, False)}
               for t in SOURCE_TIMES]
    if len(names) < 80 or any(name not in guard or any(name not in s for s in samples)
                              for name in names):
        raise RuntimeError(f"Incomplete source or guard tracks: {source}")

    tracks = []
    for bone in names:
        track = unreal.BoneTrackData()
        track.bone_name = bone
        keys = []
        for frame, sample in enumerate(samples):
            pose = guard[bone].lerp(sample[bone], source_weight(bone))
            key = unreal.AnimKeyframe()
            key.frame = frame
            key.time = frame / FPS
            key.position = pose.translation
            key.rotation = pose.rotation
            key.scale = pose.scale3d
            keys.append(key)
        track.keyframes = keys
        tracks.append(track)

    result = svc.create_anim_sequence(
        SKELETON, name, OUTPUT_DIR, (len(SOURCE_TIMES) - 1) / FPS, FPS, tracks)
    if not result:
        raise RuntimeError(f"Could not create {output}")
    if not unreal.EditorAssetLibrary.save_asset(result, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {result}")
    info = svc.get_anim_sequence_info(result)
    print(f"CREATED {result}: {info.duration:.3f}s, {info.frame_count} frames, "
          f"{len(svc.get_animated_bones(result))} tracks")
