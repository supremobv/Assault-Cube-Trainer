# Multiplayer damage investigation

Checked against the installed, fingerprint-verified AssaultCube 1.3.0.2 executable and the matching local source snapshot. The joined server's executable, configuration and modifications have not been verified. This investigation made no gameplay edits or network requests.

## Live client observations

| Field | Observed local value | Original executable value |
| --- | ---: | ---: |
| Sniper magazine contents | 50 | Server contents are not observable in this check |
| Sniper magazine capacity | 100 | 5 |
| Sniper attack delay | 25 ms | 1500 ms |
| Health / armour | 999 / 999 | Server values are not observable in this check |

Mode was Capture the Flag; the local player was alive. Original weapon values were read from the installed executable's weapon table, not inferred from the modified live table. Raw local measurements are in `research/multiplayer-stat-diagnostics.json`.

## What the stock source establishes

- `research/serverevents.h`, `processevent(client *, shotevent &)`: the server rejects a shot if its own magazine is empty or its own cooldown has not elapsed. Accepted shots consume server ammunition and establish the server's weapon delay.
- `research/serverevents.h`, reload-event processing: the server refills from its own reserve and magazine values.
- `research/weapon.cpp`, `weapon::reload` (line 968): a client whose local magazine appears full can refuse to initiate reload. Artificial magazine sizes/counts can therefore interfere with ordinary synchronization.
- `research/server.cpp`, `serverdamage` (line 1886): damage is applied to server-owned health/armour. When server health reaches zero, the server broadcasts death and sets the player's server state to dead.
- `research/clients2c.cpp` (lines 710–745): clients receive health/armour and death notifications from the server. Rewriting local health afterward does not reverse the server's death decision.

These facts support a concrete alternative to genuine opponent invulnerability: the trainer can show shots and ammunition that the server rejects. This is a plausible explanation of the observation, not a measured trace of this server's shot decisions. Reverse engineering could uncover vulnerabilities in a particular server; this source review does not prove that every server is exploit-free or identify what other players are using.

## Controlled baseline

1. In RangeLab, use Reset all. Also stop any overlapping Cheat Engine freezes/scripts.
2. Respawn to receive fresh authoritative spawn/ammunition values.
3. Keep ammo locks, magazine-size edits, attack/reload timing edits, cooldown clearing and instant refills off.
4. Test normal, paced shots and normal reloads. ESP can be tested separately because it is read-only.

If normal damage works again, local/server desynchronization was contributing. If a specific opponent still demonstrably receives accepted hits without dying, establish the server build/mods and obtain a controlled reproduction or server-side logs before attributing it to a particular exploit. This investigation does not establish whether those opponents are invulnerable.
