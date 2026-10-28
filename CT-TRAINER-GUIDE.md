# Using the RangeLab Cheat Engine trainer table

Open **AssaultCube-1.3.0.2.CT**, attach CE to the current **ac_client.exe**, and expand **TRAINER CONTROLS**.

The table contains **47 opt-in feature scripts**, Reset all and Visual preferences actions, and the manual address groups. Loading it does not execute startup Lua, enable edits, or attach to a process automatically.

## Network-server compatibility

The table checks the actual network connection flag. **22 entries are marked `[offline only]`** and reject activation in multiplayer with an explanatory error. The other 25 controls operate client-side under normal server rules. On joining a server, active incompatible entries are disabled/restored automatically. Stock weapon damage, capacities and timings are repaired on the first multiplayer activation. **Respawn once afterward** to refresh server health/ammo.

The guard applies to trainer scripts. Manual address records and another CT/app can still overwrite these fields; stop overlapping freezes. Do not interpret a manually frozen local health value as server-side invulnerability. See **[MULTIPLAYER-COMPATIBILITY.md](MULTIPLAYER-COMPATIBILITY.md)** for the full list.

## Trainer checkboxes

Check a **Trainer | ...** entry to enable its preset. Uncheck it to stop that feature and restore captured data values. **Trainer | Reset all** deactivates active trainer entries and restores pending snapshots; uncheck that action afterward to arm it for another use.

The scripts are self-contained in the CT: `ce_runtime.lua`, `ce_visuals.lua` and `ce_native.lua` are the editable generator sources, not a required external file. The scripts use CE's user-mode memory, keyboard-state and timer APIs. They check the known executable MD5, module size, player layout, and weapon references before enabling. These guards apply to the trainer scripts; the manual address records remain ordinary CE entries.

### Inputs and presets

| Feature | Default usage |
| --- | --- |
| Auto aim | Focus the game and hold **Alt**; face an enemy player or bot inside a 35° cone |
| Head aim + auto shoot | Hold **Alt**; aims at recent rendered head tags and fires when aligned |
| Auto shoot | Hold **Alt** to fire the current firearm without clicking |
| Crosshair trigger | Hold **Alt** and align the crosshair with an eligible player or bot |
| Hold-to-fire conversion | Hold **left mouse** in the game |
| Bunny hop | Hold **Space**; jumps again when grounded |
| Akimbo availability | Enable it, then use the game's pistol selection to select akimbo |
| Scope settling / scope lock | Select the sniper rifle; other weapons are unaffected |
| Crouch hold | Requests crouch until the feature is unchecked |
| Reserve-fed refill | Fills an empty magazine from existing reserves; excludes magazine/reserve locks |
| Target lock / nearest priority | Modify target selection; enable an aim mode too |
| Noclip / combat flight | W/A/S/D, Space up, Ctrl down, Shift boost; default speed 16. Uncheck returns to entry |
| Hover | Hold the height captured when enabled; excludes noclip and bunny hop |
| Through-wall player ESP | External boxes, names, HP and distance; default range 250 world units |
| Through-wall radar | Top-down player/bot dots; default radius 75 units |
| Include teammates | Include allies in ESP/radar; green allies, orange enemies |
| ESP tracer lines | Enable ESP too; draws lines to player/bot boxes |
| Center crosshair | Mint crosshair over the focused game |

The CT defaults match RangeLab's catalog: health 100, armour 100, magazines 50, reserves 120, grenades 5, camera FOV 105°, scope FOV 35°, and the documented weapon-tuning presets. To change a numeric preset, edit the final `RangeLabCE.enable('feature', value)` line in that entry's script. Supported bounds are checked. For interactive editors and activation choices, use the RangeLab desktop app instead.

CT aim options default to smoothing 4, range 250, tolerance 0.6°, enemy-team filtering, and recently rendered players and bots. Advanced users can edit the `options` defaults in `ce_runtime.lua` and regenerate the table. This rendered-target filter is not a complete map raycast.

## Reset and interaction rules

- Use **one trainer runtime at a time**. Disconnect RangeLab before using CE trainer scripts, and uncheck CE scripts before using RangeLab.
- Stop manual CE freezes that overlap trainer-owned fields.
- Conflicting trainer entries are deactivated together: aim versus view lock, alternative firing modes, and reserve-fed refill versus ammo locks.
- Uncheck all scripts before restarting the game, reattaching CE, changing process, or replacing the table.
- After a script error, automatic updates pause. Uncheck affected controls or use Reset all to retry restoration, then re-enable once the game is ready.
- Generated attack and jump requests are released when appropriate. Shots, score changes, consumed reserve ammo, and camera movements are gameplay actions and cannot be undone by a reset.
- Bot controls affect valid local bot entities. Same-team bots are excluded by default.

## Visibility and free flight

Use windowed or borderless first-person play for the overlay. Visibility uses a transparent, click-through window owned by CE. It calls local Windows APIs to track the game client rectangle without taking focus; it does not execute code inside AssaultCube. It hides on focus loss and reset. Exclusive fullscreen and native CE display behavior need confirmation on your setup. ESP projects body positions; it does not change wall textures. Occlusion and recent-render filtering are deliberately ignored for visuals, while aim retains its separate filters.

Combat flight now keeps normal alive state and does not suppress firing. It writes desired position/interpolation fields, leaving weapon state alone. Uncheck/Reset all returns a living player to the entry point. Death or a changed player root stops flight. Fixed bindings: W/A/S/D, Space, Ctrl, Shift; numeric preset is speed (1–50, default 16). Normal physics can cause jitter, and servers can correct movement. Local gun compatibility is covered by simulated tests; live confirmation remains needed.

ESP, radar, bearings and aim enumerate network players plus bots. Team modes hide teammates by default, while free-for-all ignores stored team numbers. Include teammates changes visual filtering; the aim team option is separate. Bot-edit features remain bot-only. Remote health may be stale; server-controlled health/ammo/damage/movement cannot be guaranteed by local edits.

Practice bot health and armour are new numeric presets; bot-health lock excludes low-health bots. Aim cone guide and off-screen player bearings are new visual presets. Spectator/death cameras are not tracked; respawn for first-person alignment.

## Validation limits

The Python application, catalog coverage, XML structure, Lua syntax/feature presets, fingerprint rejection, restoration, and input-release behavior are tested automatically. Lua tests run with mocked CE APIs and byte-accurate fake memory.

The Lua implementation was also exercised against the real game through a CE-compatible memory adapter. Health/restoration, akimbo, scope lock/settling, reserve-fed refill, crouch movement and jumping were checked. **Native CE UI checkbox activation and its timer scheduling have not been directly exercised**, and the new CE overlay has only been exercised with mocked UI/Windows APIs, because CE window automation was unavailable in this session. Report the specific Lua/AA error if CE behaves differently.

## Regenerate the table

```powershell
.\.venv\Scripts\python.exe export_ce_table.py
```

`catalog.py` is shared by the app and CT generator. The test suite verifies every catalog/engine control has exactly one matching feature script, preventing silent omissions in later updates.

## Appearance and added controls

The Visual preferences AA action configures independent ESP box/name/health/armour/distance display, crosshair style/color/size/gap/thickness, ESP colors/text size/line width and radar size. Edit its final `RangeLabCE.configureVisuals` block, then uncheck/recheck to apply. These preferences do not write game memory. See **CONFIGURATION-GUIDE.md** for details. Desktop JSON profiles are separate from CT presets.

Practice movement multiplier is offline-only and uses W/A/S/D input; releasing focus or disabling releases generated movement. The visual ping number is an overlay label only, not the scoreboard ping or a network change.

## Native wall controls

The Visibility group now includes **Animated model wall view (experimental)** and Weapons includes **Through-wall shots (experimental)**. Both require an offline match. Unlike the existing ESP overlay, these two entries execute a small native wrapper or patch game instructions in memory. They restore on disabling/reset; uncheck them before closing CE. The native model view includes teammates and retains real textures/animations. See [NATIVE-FEATURES.md](NATIVE-FEATURES.md) for exact behavior and the native CE validation limit.
