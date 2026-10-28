# AssaultCube 1.3.0.2 — verified address profile

Target: `ac_client.exe`, 32-bit Windows build.

SHA-256: `5b588e6ff7710fa0170553506a50bfa14750ccb438a154e4ea0e0b1ba621cefb`

The trainer checks that hash before connecting. These are offsets for this executable, not universal addresses for every AssaultCube release.

## Restart check

| Measurement | Before restart | After restart |
| --- | --- | --- |
| Process ID | 8516 | 5644 |
| Module base | `0x00400000` | `0x00400000` |
| Player object | `0x0066D448` | `0x009179F0` |
| Player root | `ac_client.exe + 0x18AC00` | Same offset |
| Health | 100 | 100 |
| Weapon table RVA | `0x16BCC0` | Same offset |

The heap address changed. The trainer reads the pointer stored at `module base + 0x18AC00`, then adds the appropriate player-field offset. It never saves the old heap address as its permanent target.

Example health address:

```text
player = read_u32(module_base + 0x18AC00)
health_address = player + 0xEC
```

In Cheat Engine, enter address `"ac_client.exe"+18AC00`, enable the pointer option, and use offset `EC`. The exported table already contains that chain.

## Player structure

All offsets in this table are relative to the dereferenced player object.

| Field | Offset | Type |
| --- | --- | --- |
| X / Y / eye Z | `04` / `08` / `0C` | Float |
| Velocity X / Y / Z | `10` / `14` / `18` | Float |
| Interpolation delta | `1C` / `20` / `24` | Float |
| Interpolation foot position | `28` / `2C` / `30` | Float |
| Yaw / pitch / roll | `34` / `38` / `3C` | Float |
| Maximum speed | `44` | Float; inspect only |
| Time in air | `48` | 4-byte integer |
| Eye height | `50` | Float |
| Player state | `76` | Byte; 0 means alive |
| Health / armour | `EC` / `F0` | 4-byte integer |
| Selected weapon ID | `FC` | 4-byte integer; inspect only |
| Reserve ammo array | `104 + weapon_id × 4` | 4-byte integer |
| Magazine array | `128 + weapon_id × 4` | 4-byte integer |
| Grenade count | `144` | 4-byte integer; magazine slot 7 |
| Cooldown array | `14C + weapon_id × 4` | 4-byte integer |
| Player name | `205` | Null-terminated string |
| Weapon object pointers | `33C + weapon_id × 4` | 32-bit pointer |

Weapon IDs: 0 knife, 1 pistol, 2 carbine, 3 shotgun, 4 SMG, 5 sniper, 6 assault rifle, 7 grenades, 8 akimbo.

## Shared weapon definitions

Base: `ac_client.exe + 0x16BCC0`. Each definition occupies `0x68` bytes.

```text
field_address = module_base + 0x16BCC0 + weapon_id * 0x68 + field_offset
```

The weapon object's `+0x0C` info pointer was checked against this formula for all nine weapons. The object's `+0x08` owner pointer matched the local player.

| Setting | Offset within definition | Type |
| --- | --- | --- |
| Reload duration | `46` | 2-byte signed integer |
| Attack interval | `48` | 2-byte signed integer |
| Damage | `4A` | 2-byte signed integer |
| Spread | `52` | 2-byte signed integer |
| Recoil | `54` | 2-byte signed integer |
| Magazine capacity | `56` | 2-byte signed integer |
| Model kick rotation / back | `58` / `5A` | 2-byte signed integer |
| Recoil base / maximum | `5E` / `60` | 2-byte signed integer |
| Automatic-fire flag | `66` | Byte |

These definitions are shared, so changing them can affect bots using the same weapons. Shotgun spread and damage include special calculations. The damage control excludes shotgun rather than claiming the same multiplier works on it.

## Camera globals

| Setting | Module-relative address | Type |
| --- | --- | --- |
| Camera field of view | `ac_client.exe + 18A7CC` | Float, normal console range 75–120 |
| Scoped field of view | `ac_client.exe + 18A834` | 4-byte integer, normal range 5–60 |

The FOV addresses were traced from the executable's `fov` variable registration and cross-checked against source and live defaults of 90 and 50.

## What was actually verified

- Health was changed from 100 to 125; the user confirmed 125 appeared in the HUD. It was restored to 100.
- Assault-rifle ammo was changed to 31 magazine / 77 reserve; the user confirmed the display and magazine consumption while firing. The temporary values were restored.
- A full game restart changed the player object's heap address while the same pointer root resolved valid player data.
- All 16 trainer toggles passed live field read-back and restoration checks. This verifies field writes and reset behavior, not every individual combat, fall-physics, or camera effect.
- A two-unit lift changed the live Z coordinate; returning to the saved marker restored the original position. Replenish-loadout writes were checked and the temporary loadout values restored.
- Automated tests use fake memory to check re-resolution, stale-pointer avoidance, restoration failures, value bounds, teleport interpolation, GUI behavior, and CE-table script coverage, Lua preset execution, restoration and fingerprint rejection.

A single successful restart does not guarantee compatibility with a different binary, game update, or platform. The build fingerprint deliberately limits this profile.

## Combat update

| Field | Address / offset | Type |
| --- | --- | --- |
| Player attack input | `[player root] + 204` | Byte |
| Player team | `[player root] + 30C` | Integer |
| Other-entity vector buffer | `ac_client.exe + 18AC04` | 32-bit pointer |
| Vector capacity / count | `18AC08` / `18AC0C` | Integer |
| Current game milliseconds | `ac_client.exe + 17F10C` | Integer |
| Entity last rendered | `entity + E4` | Integer |
| Entity type / state | `entity + 77` / `entity + 76` | Byte |
| Rendered head XYZ | `entity + 3F8 / 3FC / 400` | Float |
| Sniper object | `[player root] + 350` | 32-bit pointer |
| Sniper scoped flag | `sniper object + 28` | Byte |

The last-rendered clock was traced from the model renderer's stores to the entity's `+E4` field. Rendered head coordinates were observed changing to valid world coordinates when a bot was brought into view. Aim uses exact local-bot type, state, health, team, range, angular-cone, and recent-render checks. The recent-render filter is not a full map raycast.

Controlled live tests exercised repeated auto-shoot and hold-to-fire shots, bot acquisition/angle writes, scope state at 20°, and two sniper shots that increased local frags by four. Offline tests cover key release, lost focus, trigger alignment, conflicting aim/fire modes, and bot-value restoration. See the research JSON files for the recorded measurements.

## Source references

- [Player and weapon structures](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/entity.h)
- [Weapon definitions](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/server.h)
- [Weapon behavior](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/weapon.cpp)
- [FOV variables and rendering](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/rendergl.cpp)
- [Movement and fall calculations](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/physics.cpp)

Maximum-speed editing is intentionally absent: this build contains a movement check that can invalidate the player reference when that value is increased. No bypass was added.

## Free flight and external visibility update

`[ac_client.exe + 18AC00] + 76` is the one-byte physics state: 0 alive, 4 editing. The original flight implementation used state 4, which disables combat. Combat flight now keeps state 0, integrates W/A/S/D/Space/Ctrl movement using elapsed time, and writes origin/foot/interpolation/velocity data. It does not modify the max-speed field or executable instructions. Unchecking returns a living player to the captured entry point. See the source's [weapon state checks](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/weapon.cpp) and [physics implementation](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/physics.cpp).

ESP projects bot body origins and eye heights using local first-person yaw, pitch, roll and horizontal FOV, matching the transformation in [rendergl.cpp](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/rendergl.cpp). It deliberately ignores occlusion and stale rendered head tags. The radar uses horizontal relative positions rotated by local yaw. These visuals read the same validated bot vector; they do not write bot render state or patch executable instructions.

The CE renderer uses documented CE form, paintbox, canvas, local-memory and local Windows-call APIs from [celua.txt](https://github.com/cheat-engine/cheat-engine/blob/master/Cheat%20Engine/bin/celua.txt). Native CE overlay rendering remains unverified; Lua 5.3 logic and mocked UI calls are covered by tests.

## Mode and multiplayer entities

`ac_client.exe + 0x18ABF8` is the 32-bit game-mode value. It was identified from this executable's `gamemode` variable registration: registration code at VA `0x409060` passes VA `0x58ABF8` as storage, then stores the initializer result there. Its live value 5 matched Capture the Flag. Mode IDs/team flags follow versioned `protocol.h`; team modes are 0, 4, 5, 7, 11, 13, 14, 16, 17, 20, 21.

The vector at `module + 18AC04` contains both type-0 network players and type-1 bots. The old bot-only type check was the cause of missing multiplayer ESP. Visibility and aim now accept both, skip the local player pointer and non-player types, and apply mode-aware team rules. Bot-stat edits still enumerate only type 1. Read-only multiplayer verification is recorded in `research/multiplayer-verification.json`.

## Network connection and protocol baseline

`ac_client.exe + 0x18ABC8` is the read-only 32-bit `connected` console variable. Registration at VA `0x408B60` passes storage VA `0x58ABC8`, then saves the initializer result there. The matching `client.cpp` sets it to 1 after an ENet connection succeeds and to 0 during disconnect. Values other than 0/1 pause compatibility handling instead of guessing that the session is local.

`profile.json` includes original weapon fields read from the fingerprinted executable: short offsets 46 (reload), 48 (attack interval), 4A (damage), 56 (capacity). These four shared fields for all nine weapons are restored on entering multiplayer. This is a client baseline repair, not a server-state edit. It does not write guessed player health/ammo or bypass server validation. Evidence is in `research/multiplayer-compatibility-verification.json`.

## Reference damage-path mapping

A source/disassembly review of the old 1.2.0.2 reference and current 1.3.0.2 build is in `SOURCE-REVIEW.md`. Distinct current cross-references were found at RVA `0x7D0A7` (client `onHit`) and `0x958CB` (local server suicide/death logging). These are candidate instruction sites associated with damage paths, not verified callable function entries. No native damage hook was installed. The reference's own UI states its server-sided section does not work online.

Practice movement multiplier writes signed movement bytes at player offsets 74/75, within a bounded 1–5 multiplier; it leaves the max-speed field unchanged. Generated movement is released on focus loss/reset. Player armour at F0 is now included in read-only visual snapshots. Visual ping writes no game field.

## Native wall feature sites

The optional native controls use four fully checked instructions at RVAs `0x62C79`, `0x56C7E`, `0x56BA2`, and `0x56C5E`. They are distinct from the earlier unverified damage-function candidates. See [NATIVE-FEATURES.md](NATIVE-FEATURES.md) for originals, restoration, exact-build guards and offline test results.
