# Multiplayer compatibility

RangeLab checks the actual network connection flag, not just the game mode. There are 47 controls: 25 client-side controls remain available in multiplayer; 22 require a local simulation or server-side support. Availability does not guarantee a server accepts every action.

On entering multiplayer, the trainer stops its incompatible controls and restores stock weapon damage, magazine sizes, attack delay and reload duration from this exact executable profile. **Respawn once afterward** to receive fresh server-owned health and ammunition. The trainer does not invent replacement server values.

Close older trainers and stop overlapping manual CE freezes. Manual address records do not have compatibility guards. Server modifications can change behavior, and remote health displayed by ESP can be incomplete. ESP requires a windowed/borderless first-person view.

| Control | Multiplayer availability |
| --- | --- |
| Health lock | Offline only — Health is owned by the server. |
| Armour lock | Offline only — Armour is owned by the server. |
| Magazine lock | Offline only — The server tracks magazine ammunition; local locks cause rejected shots. |
| Reserve ammo | Offline only — The server tracks reserve ammunition. |
| Grenade supply | Offline only — The server tracks grenade inventory. |
| No recoil & kick | Client-side control; normal server rules still apply. |
| Minimum spread | Client-side control; normal server rules still apply. |
| Attack interval | Offline only — The server enforces its own attack interval. |
| Fast reload | Offline only — The server enforces reload timing and ammunition transfer. |
| Hold-to-fire conversion | Client-side control; normal server rules still apply. |
| Magazine capacity | Offline only — The server uses its own magazine sizes. |
| Shared weapon damage | Offline only — The server computes weapon damage. |
| Through-wall shots (experimental) | Offline only — Through-wall hit registration has only been implemented for local practice, not verified on remote servers. |
| Field of view | Client-side control; normal server rules still apply. |
| Scope field of view | Client-side control; normal server rules still apply. |
| Gentler falling | Offline only — The server can correct altered movement. |
| Lock view angles | Client-side control; normal server rules still apply. |
| Clear firing cooldown | Offline only — Clearing local cooldown does not clear server cooldown. |
| Stable camera | Client-side control; normal server rules still apply. |
| Auto aim — players | Client-side control; normal server rules still apply. |
| Head aim + auto shoot | Client-side control; normal server rules still apply. |
| Auto shoot | Client-side control; normal server rules still apply. |
| Crosshair trigger | Client-side control; normal server rules still apply. |
| Stationary bots | Offline only — Bot simulation edits require a local bot match. |
| Low-health bots | Offline only — Bot health edits require a local bot match. |
| Keep akimbo available | Offline only — The server validates the akimbo power-up and its expiry. |
| Reserve-fed refill | Offline only — A local refill does not reload the server magazine. |
| Instant scope settling | Client-side control; normal server rules still apply. |
| Keep sniper scoped | Client-side control; normal server rules still apply. |
| Bunny hop | Client-side control; normal server rules still apply. |
| Crouch hold | Client-side control; normal server rules still apply. |
| Keep current target | Client-side control; normal server rules still apply. |
| Nearest-target priority | Client-side control; normal server rules still apply. |
| Noclip / combat flight | Offline only — Flight needs support from a server you control. |
| Hover at current height | Offline only — Hover needs support from a server you control. |
| Through-wall player ESP | Client-side control; normal server rules still apply. |
| Animated model wall view (experimental) | Offline only — Experimental native rendering is currently supported in offline practice only. |
| Through-wall radar | Client-side control; normal server rules still apply. |
| Include teammates | Client-side control; normal server rules still apply. |
| ESP tracer lines | Client-side control; normal server rules still apply. |
| Center crosshair | Client-side control; normal server rules still apply. |
| Practice bot health | Offline only — Bot health edits require a local bot match. |
| Practice bot armour | Offline only — Bot armour edits require a local bot match. |
| Aim cone guide | Client-side control; normal server rules still apply. |
| Off-screen player bearings | Client-side control; normal server rules still apply. |
| Practice movement multiplier | Offline only — Movement multipliers need a locally controlled simulation. |
| Visual ping label | Client-side control; normal server rules still apply. |

Teleport/loadout/equip-primary actions are also offline-only. Normal game weapon selection, scope input and reloads remain available. No server bypass or server-side invulnerability is implemented.

The compatibility guards, transitions, restoration and baseline repair are covered by offline tests. The live network connection flag and stock baseline were checked. Native CE UI/timers/overlay and server acceptance of every feature have not been independently verified.
