# Battle Unreal MCP setup

This project uses Unreal Engine 5.8's built-in `ModelContextProtocol` server and the VibeUE editor plugin. The MCP endpoint is `http://127.0.0.1:8000/mcp`. Codex reads `.codex/config.toml`; `.mcp.json` remains available for clients that use it.

VibeUE is vendored in `Plugins/VibeUE` from the upstream `5-8` branch at commit `d00b760a030eaa61360550a545995a7f94accb53` (`https://github.com/kevinpbuckley/VibeUE`). It is enabled in `Battle.uproject`. `AGENTS.md` contains VibeUE's `Content/samples/AGENTS.md.sample` in the same managed block format as `VibeUE.GenerateAgentConfig Codex`.

## Finish a new machine setup

1. Install Visual Studio's C++ tools and **.NET Framework 4.8 SDK**. UnrealBuildTool needs the latter for `SwarmInterface`.
2. Save open Unreal assets and close the editor normally before building or restarting it. The upstream `BuildAndLaunchGame.ps1` can forcibly end editor processes, so do not run it while an editor is open.
3. Build the project editor target with UE 5.8's `Engine/Build/BatchFiles/Build.bat BattleEditor Win64 Development "<absolute path to Battle.uproject>" -waitmutex`.
4. Open `Battle.uproject`. VibeUE should be enabled. The built-in MCP server is configured to auto-start on port 8000 in this machine's editor preferences.
5. In the Unreal console, run `VibeUE.GenerateAgentConfig Codex` to refresh the VibeUE block in `AGENTS.md` after updating the plugin. If needed, run `ModelContextProtocol.StartServer`.
6. From the Battle project root, run `codex mcp list`. Confirm `unreal-mcp` appears, then query its toolsets and VibeUE skills from Codex.

The local MCP server listens on loopback and is intended for same-machine use.

## Verified on this machine (2026-09-27)

- UE `5.8.2` loaded VibeUE `5.0` after the plugin compiled successfully with `RunUAT.bat BuildPlugin` for Win64.
- `codex mcp get unreal-mcp` reports the project endpoint as enabled.
- Codex discovered VibeUE toolsets and executed `execute_python_code` in the live editor.
- The editor loaded `BP_Player_Combat` and `ABP_Player_Combat`; `AnimGraphService.list_state_machines` read two state machines from the latter.
- The plugin's generated Win64 binary under `Plugins/VibeUE/Binaries` is ignored by Git. On another machine, build it from the vendored source before opening the project.
