"""Connect boxing duck clips to ten lock-on directions.

Run in Unreal Editor Python with PIE stopped. Existing dodge clips remain in the
project as rollback sources. Shift mappings, roll clips, and DodgePlayRate stay
unchanged. The montage blend pins are shared with the free roll.
"""

import unreal


PLAYER = "/Game/BossArena/Player/Blueprints/BP_Player_Combat"
GRAPH = "TryEnterDodge"
OUTPUT_DIR = "/Game/BossArena/Player/Animation/Prototypes"
SLOTS = (
    ("CBDC4CC841ACAF3C9AA756A84182DC0C", "A", "A_INP_Dodge_01_IdleFwdRt_45", "FwdRight45"),
    ("CBDC4CC841ACAF3C9AA756A84182DC0C", "B", "A_INP_Dodge_01_IdleFwdLt_45", "FwdLeft45"),
    ("78D51E5D40C2757E7A7A5AB719AA6B0E", "A", "A_INP_Dodge_01_IdleFwdRt_90", "Right"),
    ("78D51E5D40C2757E7A7A5AB719AA6B0E", "B", "A_INP_Dodge_01_IdleFwdLt_90", "Left"),
    ("3D5560934E5C6F097A97BC817AD3CE98", "A", "A_INP_Dodge_01_IdleBwdRt_135", "Right"),
    ("3D5560934E5C6F097A97BC817AD3CE98", "B", "A_INP_Dodge_01_IdleBwdLt_135", "Left"),
    ("1172D09C45AC82EFDB320C8DA2DF1D77", "A", "A_INP_Dodge_01_IdleFwd_toRight", "FwdToRight"),
    ("1172D09C45AC82EFDB320C8DA2DF1D77", "B", "A_INP_Dodge_01_IdleFwd_toLeft", "FwdToLeft"),
    ("10F0642642B1A26D6E2FC7835939D8CD", "A", "A_INP_Dodge_01_IdleBwd_toRight", "Right"),
    ("10F0642642B1A26D6E2FC7835939D8CD", "B", "A_INP_Dodge_01_IdleBwd_toLeft", "Left"),
)

for node_id, pin_name, original_name, side in SLOTS:
    target_name = f"AS_Player_BoxDuck_{side}_Prototype"
    target = f"{OUTPUT_DIR}/{target_name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(target):
        raise RuntimeError(f"Missing sequence: {target}")
    value = f"{target}.{target_name}"
    pin = next((x for x in unreal.BlueprintService.get_node_pins(PLAYER, GRAPH, node_id)
                if x.pin_name == pin_name and x.is_input), None)
    if pin is None:
        raise RuntimeError(f"Missing pin {node_id}.{pin_name}")
    old = str(pin.default_object)
    if old == value:
        print(f"VERIFIED {node_id}.{pin_name} -> {target_name}")
        continue
    if f"/{original_name}.{original_name}" not in old:
        raise RuntimeError(f"Unexpected source for {node_id}.{pin_name}: {old}")
    if not unreal.BlueprintService.set_node_pin_value(PLAYER, GRAPH, node_id, pin_name, value):
        raise RuntimeError(f"Could not wire {node_id}.{pin_name}")
    print(f"MODIFIED {PLAYER} {node_id}.{pin_name}: {original_name} -> {target_name}")

play_nodes = unreal.BlueprintService.get_nodes_in_graph(
    PLAYER, GRAPH, 0, "Play Slot Animation as Dynamic Montage", False
)
if len(play_nodes) != 1:
    raise RuntimeError(f"Expected one dodge dynamic montage node, found {len(play_nodes)}")
play_id = play_nodes[0].node_id
for pin_name, value in (("BlendInTime", "0.025"), ("BlendOutTime", "0.06")):
    if not unreal.BlueprintService.set_node_pin_value(PLAYER, GRAPH, play_id, pin_name, value):
        raise RuntimeError(f"Could not set {pin_name}")
    print(f"MODIFIED {PLAYER} {play_id}.{pin_name} = {value}")

compiled = unreal.BlueprintService.compile_blueprint(PLAYER)
print("COMPILE", compiled.success, compiled.num_errors, compiled.num_warnings,
      list(compiled.errors), list(compiled.warnings))
if not compiled.success or compiled.num_errors:
    raise RuntimeError("Player Blueprint failed to compile")

bp = unreal.EditorAssetLibrary.load_asset(PLAYER)
cdo = unreal.get_default_object(bp.generated_class())
for name, value in (("DodgeDistance", 130.0),
                    ("DodgeMoveWindow", 0.75),
                    ("DodgeRecoveryRatio", 0.75)):
    before = cdo.get_editor_property(name)
    cdo.set_editor_property(name, value)
    print(f"MODIFIED {PLAYER} {name}: {before} -> {value}")
if not unreal.EditorAssetLibrary.save_asset(PLAYER, only_if_is_dirty=False):
    raise RuntimeError("Could not save player Blueprint")

for name, wanted in (("DodgeDistance", 130.0),
                     ("DodgeMoveWindow", 0.75),
                     ("DodgeRecoveryRatio", 0.75),
                     ("DodgePlayRate", 1.05)):
    actual = cdo.get_editor_property(name)
    if abs(actual - wanted) > 1e-5:
        raise RuntimeError(f"Unexpected {name}: {actual} (wanted {wanted})")
print("VERIFIED player dodge variables and preserved DodgePlayRate")
