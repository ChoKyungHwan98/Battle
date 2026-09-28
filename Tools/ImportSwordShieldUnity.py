"""Import the supplied Kubold Unity FBX sources through Unreal Editor Python.

Run one bounded phase per MCP call: install("Part1"), etc. Existing destination
assets are never overwritten. Unity scripts/controllers are not imported.
"""

import unreal
import json
from pathlib import Path

SOURCE = Path("C:/Users/Admin/Downloads/SwordShieldAnimsetPro_v1_18_UnrealSource")
BASE = "/Game/ThirdParty/Kubold/SwordShieldAnimsetPro"
SKELETON = BASE + "/Models/SK_Kubold_Dummy_Skeleton"
REPORT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "CodexImports/SwordShieldAnimsetPro_v1_18.json"


def install(phase, dry_run=False, repair_failed_phase=False):
    import vibeue
    if vibeue.exec_tool("EditorToolset.EditorAppToolset", "IsPIERunning"):
        raise RuntimeError("Stop PIE before importing")
    clips = json.loads((SOURCE / "clip_manifest.json").read_text(encoding="utf-8"))
    skeleton = unreal.EditorAssetLibrary.load_asset(SKELETON)
    if skeleton is None:
        raise RuntimeError("Import the source Dummy skeleton first")
    tasks = []
    if phase.startswith("Part"):
        index = int(phase[4:])
        filename = SOURCE / "Animations" / f"SwordShieldAnimsetPro_part{index}.fbx"
        folder = BASE + "/Animations/" + phase
        expected = [folder + "/" + filename.stem + "_" + c["take"] for c in clips if Path(c["fbx"]).name == filename.name]
        existing = [p for p in expected if unreal.EditorAssetLibrary.does_asset_exist(p)]
        if existing and len(existing) != len(expected) and not repair_failed_phase:
            raise RuntimeError("Partial phase exists; inspect before resuming: " + phase)
        plan = {"phase": phase, "source": str(filename), "expected": len(expected), "existing": len(existing), "folder": folder}
        print("PLAN:", json.dumps(plan))
        if dry_run:
            return plan
        if not existing or repair_failed_phase:
            ui = unreal.FbxImportUI()
            values = {"automated_import_should_detect_type": False, "mesh_type_to_import": unreal.FBXImportType.FBXIT_ANIMATION, "import_as_skeletal": True, "import_mesh": False, "import_animations": True, "import_materials": False, "import_textures": False, "skeleton": skeleton}
            for key, value in values.items():
                ui.set_editor_property(key, value)
            for key, value in {"convert_scene": True, "convert_scene_unit": True, "use_default_sample_rate": True, "custom_sample_rate": 30, "snap_to_closest_frame_boundary": True, "import_bone_tracks": True, "import_custom_attribute": False}.items():
                ui.anim_sequence_import_data.set_editor_property(key, value)
            task = unreal.AssetImportTask()
            for key, value in {"filename": str(filename), "destination_path": folder, "automated": True, "replace_existing": repair_failed_phase, "replace_existing_settings": repair_failed_phase, "save": False, "factory": unreal.FbxFactory(), "options": ui}.items():
                task.set_editor_property(key, value)
            tasks.append(task)
    elif phase == "Weapons":
        expected = [BASE + "/Models/SM_Kubold_" + n for n in ("Sword", "Shield")]
        print("PLAN:", phase, expected)
        if dry_run:
            return expected
        for name, destination in zip(("Sword", "Shield"), expected):
            if unreal.EditorAssetLibrary.does_asset_exist(destination):
                continue
            ui = unreal.FbxImportUI()
            for key, value in {"automated_import_should_detect_type": False, "mesh_type_to_import": unreal.FBXImportType.FBXIT_STATIC_MESH, "import_as_skeletal": False, "import_mesh": True, "import_animations": False, "import_materials": False, "import_textures": False}.items():
                ui.set_editor_property(key, value)
            for key, value in {"convert_scene": True, "convert_scene_unit": True, "combine_meshes": True, "auto_generate_collision": False}.items():
                ui.static_mesh_import_data.set_editor_property(key, value)
            task = unreal.AssetImportTask()
            for key, value in {"filename": str(SOURCE / "Models" / (name + ".FBX")), "destination_path": BASE + "/Models", "destination_name": "SM_Kubold_" + name, "automated": True, "replace_existing": False, "save": False, "factory": unreal.FbxFactory(), "options": ui}.items():
                task.set_editor_property(key, value)
            tasks.append(task)
    else:
        raise ValueError(phase)
    # Explicit legacy factory bypasses Interchange's reentrant task-graph path.
    # Texture import is disabled; images use AssetDiscoveryService separately.
    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        for task in tasks:
            for path in task.imported_object_paths:
                print("IMPORTED:", path)
    missing = [p for p in expected if not unreal.EditorAssetLibrary.does_asset_exist(p)]
    if missing:
        raise RuntimeError("Missing imports: " + str(missing))
    records = []
    for path in expected:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset is None:
            raise RuntimeError("Cannot load: " + path)
        record = {"path": path, "class": asset.get_class().get_name()}
        if isinstance(asset, unreal.AnimSequence):
            info = unreal.AnimSequenceService.get_anim_sequence_info(path)
            record.update({"duration": asset.get_editor_property("sequence_length"), "skeleton": asset.get_editor_property("skeleton").get_path_name(), "info": str(info)})
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
            raise RuntimeError("Save failed: " + path)
        records.append(record)
    unreal.EditorAssetLibrary.save_loaded_asset(skeleton)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(REPORT.read_text()) if REPORT.exists() else {"source": str(SOURCE), "destination": BASE, "phases": {}}
    report["phases"][phase] = records
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("VERIFIED:", phase, len(records), "saved assets", "REPORT:", str(REPORT))
    return records
