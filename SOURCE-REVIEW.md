# Requested features and source review

Reviewed reference commit: `a535e5a2078b9aae1efb3c8ed72043edb6073afe` of [rdbo/AssaultCube-Multihack](https://github.com/rdbo/AssaultCube-Multihack). Its README targets AssaultCube **1.2.0.2**; RangeLab targets the separately fingerprinted **1.3.0.2** Windows executable. The reference is an internal DLL with native hooks; RangeLab uses an external desktop UI/overlay; two opt-in native memory patches now support offline model rendering and through-wall targeting. No reference binary was run or injected, and its code was not incorporated into this implementation. The linked forum page could not be retrieved, so its separate claims were not verified.

## What “server sided” means in the reference

The reference's own [menu source](https://github.com/rdbo/AssaultCube-Multihack/blob/a535e5a2078b9aae1efb3c8ed72043edb6073afe/src/hooks/SwapBuffers.cpp#L614-L625) says: “The hacks on this section do not work online.” `EnableServerSide` is a local settings boolean, not evidence of authority over a joined remote server.

Its [Godmode/Instakill damage hook](https://github.com/rdbo/AssaultCube-Multihack/blob/a535e5a2078b9aae1efb3c8ed72043edb6073afe/src/hooks/dodamage.cpp) changes local damage handling. Its infinite-health/armour/ammo routines write local player fields. This review does not establish a remote-server exploit, nor prove that unrelated versions/servers cannot have vulnerabilities.

## Corresponding 1.3.0.2 functions

| Reference behavior | Matching 1.3.0.2 source path | Ownership / consequence |
| --- | --- | --- |
| Local damage hook | `research/clientgame.cpp:903`, `dodamage` | Local damage/effects handler; it applies health subtraction only for its `local` path. |
| Local kill handler | `research/clientgame.cpp:938`, `dokill` | Local player/entity state; remote death notifications still arrive independently. |
| Authoritative damage/death | `research/server.cpp:1886`, `serverdamage` | Operates on server-owned client state. A copy compiled into the local executable does not control a separately running remote server. |
| Network health/death updates | `research/clients2c.cpp:710–745` | Receives server health/armour and death messages. |
| Accepted shots and reloads | `research/serverevents.h`, shot/reload event handlers | Checks server ammo/cooldowns and computes accepted damage. |
| Client reload | `research/weapon.cpp:968`, `weapon::reload` | Local reload initiation and outgoing reload request. |
| Client update hook | `research/client.cpp:375`, `c2sinfo` | Produces local-to-server updates; not remote server execution. |

Read-only disassembly also located the `onHit` reference at module RVA `0x7D0A7` and the local-server suicide-log reference at RVA `0x958CB`. They correlate with the two distinct damage paths. These are **cross-reference instruction locations, not verified function entries or ready-to-use hook points**. They were not patched or called. Context is recorded in `research/function-map-candidates.json`.

## Feature-by-feature status

| Requested feature | Current status |
| --- | --- |
| Aimbot | Player/bot aim with activation, cone, smoothing and team filters; client-side. |
| ESP Snaplines | Implemented as ESP tracer lines. |
| ESP Box / Name / Health / Armor | Implemented; each component can be toggled independently in Configuration. Remote health/armour may be incomplete. |
| Teleport | Local-practice waypoint/coordinate actions; unavailable on a joined server. |
| Custom Crosshair | Plus, dot or circle; size, gap, thickness and color preferences. |
| No Recoil | Existing client recoil/model-kick field controls. |
| Speed Hack | Local-practice movement-input multiplier; normal collision physics retained. Live gameplay still needs confirmation. |
| Triggerbot | Existing activation/alignment-based firing control. |
| Fly Hack | Existing local-practice combat-flight controller. |
| No Scope | Scope-mask removal is not implemented; the reference uses a native draw-scope hook. Scope/FOV controls are separate features. |
| Teleport Other Players | Not implemented as a remote-server action. The reference writes client entity positions; a server-side effect is not established by that write alone. |
| Bunnyhop | Existing focused-game jump requests. |
| Wallhack | External ESP plus actual animated native model-through-wall rendering are implemented. The native control is experimental and offline-only; includes teammates. See NATIVE-FEATURES.md. |
| Always Headshot | Head aim is implemented; guaranteed hit reclassification is not. The reference uses another native hook. |
| Auto Guns | Existing hold-to-fire conversion, respecting native cooldowns in multiplayer. |
| Fullbright | Not implemented; the reference invokes native lighting recalculation functions requiring a version-specific port. |
| Name Changer | Not implemented in this trainer. The reference calls the game's normal name-change routine. |
| Radar Hack | Existing external rotating player/bot radar with configurable radius and size. |
| Item Magnet | Not implemented; local item-position writes are not verified as authoritative remote pickups. |
| Ping Changer (Visual) | Overlay label only. Does not alter latency, the game's scoreboard or server information. |
| Chat Spammer | Not implemented. No chat messages have been sent during this work. |
| Godmode (Server Sided) | Not implemented for a joined server; reference menu explicitly excludes online operation. |
| Instakill (Server Sided) | Not implemented for a joined server; local weapon-damage controls remain offline-only. |
| Infinite Health / Armor / Ammo (Server Sided) | Local practice locks exist; no authoritative remote-server implementation is claimed. |
| No Gun Wait (Server Sided) | Local cooldown control exists offline; the server keeps its own cooldown. |
| Config System | Local validated JSON profiles for presets, aim options and appearance. Activation is opt-in. |
| Very Customizable | Fifteen appearance preferences plus existing aim controls and numeric feature presets. |

This is a source/implementation audit, not a claim that every requested feature has been completed or works on an arbitrary multiplayer server. The remaining native-rendering and server-owned features require separate implementation and controlled validation.
