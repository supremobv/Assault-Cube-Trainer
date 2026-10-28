# Actual animated models and through-wall shots

These two **experimental, offline-only** controls require the fingerprinted AssaultCube 1.3.0.2 Windows x86 executable. They are separate from external ESP boxes. Both start disabled and are available in RangeLab and its generated CT table.

## Using them

1. Start an offline bot match, then connect RangeLab.
2. In **Visibility**, enable **Animated model wall view (experimental)**. It displays the game's actual textured, animated player models through walls, including their attached weapons. This first version includes teammates as well as opponents; ESP team/color/distance preferences do not filter native models.
3. In **Weapons**, enable **Through-wall shots (experimental)**. Aim normally and fire through a wall at a bot. Ammunition, spread, attack delays and damage rules remain active. The targeting ray extends to the far plane; this is not material-specific penetration or a damage multiplier. Grenade splash/collision is not changed.
4. Disable either control, choose Reset all, or disconnect to restore its original code bytes. Uncheck CT entries before closing Cheat Engine. Use only one trainer runtime at a time.

The connection guard rejects activation on a joined server and restores these features when entering multiplayer. No public-server hit registration or compatibility is claimed.

## Implementation

The existing overlay remains external and read-only. These two opt-in controls are different: they make reversible executable-memory patches in the game. They do not modify the installed EXE, install a driver, or load a downloaded cheat DLL.

The native model control changes the player-specific model radius argument to skip geometry occlusion and wraps the main player batch flush. On the game's render thread, the wrapper saves GL depth/enables, disables depth testing and depth writes for that batch, calls the original batch flush, then restores GL and CPU state. Map-model and item batches keep their original depth handling. Native textures and animation are retained; this is not a projected skeleton or body-shaped overlay.

Through-wall targeting changes the inlined depth unprojection to use the far plane and skips that camera ray's geometry clipping call. Ordinary firearm hit testing still picks the closest intersecting player along the resulting ray. It does not move enemies or rewrite their health.

| Purpose | RVA and original instruction |
| --- | --- |
| Player model radius | `0x62C79`: `movss xmm3,[ac_client.exe+15BC88]` |
| Main player batch flush | `0x56C7E`: call to `ac_client.exe+67FA0` |
| Camera depth input | `0x56BA2`: `movss xmm5,[ac_client.exe+16BA98]` |
| Camera geometry clipping | `0x56C5E`: call to `ac_client.exe+CCA80` |

All sites are module-relative, checked against complete expected instruction bytes, and protected by the existing exact executable hash/layout guards. The process is paused while installing/restoring changes. Python restores page protections and flushes the instruction cache. CE uses its auto assembler while paused. Restoration refuses to overwrite bytes unexpectedly changed by another tool and retains its journal for recovery.

Tiny executable allocations are reused during a connection and intentionally left allocated after disabling: a suspended render thread may still be returning from the wrapper. The game releases them on exit. Closing or killing a trainer without restoration can leave its patches active until the game exits.

The Python backend resolves OpenGL from the target's **x86** DLL, checks its architecture and compares exported function bytes against the loaded module. A WOW64 logical `System32` path may identify the x64 file to a 64-bit reader; the backend explicitly selects the x86 `SysWOW64` image when needed.

## Verification and limits

On October 28, 2026, the first trial crashed the game because of that x64/x86 OpenGL export mismatch. After correcting resolution and adding loaded-byte checks, a short live trial completed and restored every original instruction. In a subsequent offline bot match, Primo confirmed that **both actual bodies through walls and damaging bots through walls worked**. The timed trial restores the patches automatically; its report is in `research/native-live-verification.json`.

There are 85 passing automated tests. Native tests cover byte restoration, partial-install rollback, refusing mismatched/conflicting code, allocation reuse, multiplayer transition restoration, and identical Python/Lua machine code. The native Cheat Engine UI/assembler integration has not been exercised directly; its Lua paths use a mocked assembler in tests. Python's actual patch backend was exercised on the live game.

The implementation was traced against the installed binary and the official [model renderer](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/rendermodel.cpp), [frame rendering](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/rendergl.cpp) and [weapon code](https://github.com/assaultcube/AC/blob/v1.3.0.2/source/src/weapon.cpp). These patches are specific to the verified Windows executable, not reusable addresses for other builds.
