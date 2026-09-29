"""Run in the Unreal Editor Python console to build the isolated player jab prototype.

The BBQ reference clip shows a compact guard clearly near 12 seconds, but VFX obscure
the exact punch path. This clip uses that guard/readability target and re-poses the
project's own first attack. It does not claim frame-for-frame recreation of the video.

The old attack remains untouched. This script refuses to overwrite the prototype.
"""

import unreal


SOURCE = "/Game/BossArena/Animations/Attack/AS_Attack1_1"
SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
OUTPUT_DIR = "/Game/BossArena/Player/Animation/Prototypes"
NAME = "AS_Player_Jab_BBQ_Prototype"
OUTPUT = f"{OUTPUT_DIR}/{NAME}"
FPS = 60
FRAME_COUNT = 21  # Input keys at frames 0..20; inspect saved frame rate afterward.

if unreal.EditorAssetLibrary.does_asset_exist(OUTPUT):
    raise RuntimeError(f"Prototype already exists: {OUTPUT}")

service = unreal.AnimSequenceService
guard = {p.bone_name: p.transform for p in service.get_pose_at_time(SOURCE, 0.42, False)}
chamber = {p.bone_name: p.transform for p in service.get_pose_at_time(SOURCE, 0.00, False)}
contact = {p.bone_name: p.transform for p in service.get_pose_at_time(SOURCE, 0.32, False)}
names = list(service.get_animated_bones(SOURCE))
if len(names) < 80 or not all(name in guard and name in chamber and name in contact for name in names):
    raise RuntimeError("Source pose tracks are incomplete")

# Deliberate timing: a tiny chamber, a sharp extension at frame 8, then an
# immediate recoil. The original punch holds its extended shape much longer.
reach = [0.0, 0.0, 0.0, 0.0, 0.08, 0.27, 0.62, 0.94, 1.0, 0.97,
         0.76, 0.48, 0.22, 0.07, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
chamber_amount = [0.0, 0.12, 0.32, 0.27, 0.13] + [0.0] * 16


def impact_weight(name):
    # Left lead hand is the jab. The right hand stays near the face. By
    # keeping legs almost still, the stance reads as planted from game camera.
    if name == "pelvis":
        return 0.20
    if name.startswith("spine_"):
        return 0.65
    if name.startswith(("neck_", "head")):
        return 0.16
    if name.startswith(("clavicle_l", "upperarm_l", "lowerarm_l", "hand_l")):
        return 1.0
    if name.startswith(("clavicle_r", "upperarm_r", "lowerarm_r", "hand_r")):
        return 0.38
    return 0.0


def chamber_weight(name):
    if name.startswith(("clavicle_l", "upperarm_l", "lowerarm_l", "hand_l")):
        return 0.55
    if name.startswith("spine_"):
        return 0.20
    return 0.0


tracks = []
for name in names:
    track = unreal.BoneTrackData()
    track.bone_name = name
    frames = []
    for frame in range(FRAME_COUNT):
        base = guard[name]
        pose = base.lerp(chamber[name], chamber_amount[frame] * chamber_weight(name))
        pose = pose.lerp(contact[name], reach[frame] * impact_weight(name))
        if name == "root":
            pose = chamber[name]  # Keep root motion at zero in the prototype.
        key = unreal.AnimKeyframe()
        key.frame = frame
        key.time = frame / FPS
        key.position = pose.translation
        key.rotation = pose.rotation
        key.scale = pose.scale3d
        frames.append(key)
    track.keyframes = frames
    tracks.append(track)

created = service.create_anim_sequence(
    SKELETON, NAME, OUTPUT_DIR, (FRAME_COUNT - 1) / FPS, FPS, tracks
)
if not created:
    raise RuntimeError("Unreal rejected the new AnimSequence; inspect the editor log")
actual_bones = list(service.get_animated_bones(created))
if len(actual_bones) < 80:
    raise RuntimeError(f"Only {len(actual_bones)} bone tracks were written")
if not unreal.EditorAssetLibrary.save_asset(created, only_if_is_dirty=False):
    raise RuntimeError("Could not save the prototype")
info = service.get_anim_sequence_info(created)
print(
    f"CREATED: {created}; bones={len(actual_bones)}; input_keys={FRAME_COUNT}; "
    f"stored_frames={info.frame_count}; stored_fps={info.frame_rate:.1f}; "
    f"seconds={info.duration:.3f}"
)
