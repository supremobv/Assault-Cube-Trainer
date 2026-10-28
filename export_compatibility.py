"""Generate the user-facing compatibility reference from the shared feature catalog."""
from pathlib import Path
from catalog import CONTROLS
from compatibility import OFFLINE_ONLY


def export():
    rows=['# Multiplayer compatibility','',
          'RangeLab checks the actual network connection flag, not just the game mode. '+
          f'There are {len(CONTROLS)} controls: {len(CONTROLS)-len(OFFLINE_ONLY)} client-side controls remain available in multiplayer; '+
          f'{len(OFFLINE_ONLY)} require a local simulation or server-side support. Availability does not guarantee a server accepts every action.','',
          'On entering multiplayer, the trainer stops its incompatible controls and restores stock '+
          'weapon damage, magazine sizes, attack delay and reload duration from this exact executable profile. '+
          '**Respawn once afterward** to receive fresh server-owned health and ammunition. '+
          'The trainer does not invent replacement server values.','',
          'Close older trainers and stop overlapping manual CE freezes. Manual address records '+
          'do not have compatibility guards. Server modifications can change behavior, and remote '+
          'health displayed by ESP can be incomplete. ESP requires a windowed/borderless first-person view.','',
          '| Control | Multiplayer availability |','| --- | --- |']
    for _,key,title,_,_ in CONTROLS:
        rows.append('| '+title+' | '+('Offline only — '+OFFLINE_ONLY[key] if key in OFFLINE_ONLY else 'Client-side control; normal server rules still apply.')+' |')
    rows+=['','Teleport/loadout/equip-primary actions are also offline-only. Normal game weapon selection, '+
           'scope input and reloads remain available. No server bypass or server-side invulnerability is implemented.','',
           'The compatibility guards, transitions, restoration and baseline repair are covered by offline tests. '+
           'The live network connection flag and stock baseline were checked. Native CE UI/timers/overlay '+
           'and server acceptance of every feature have not been independently verified.','']
    path=Path(__file__).parent/'MULTIPLAYER-COMPATIBILITY.md'
    path.write_text('\n'.join(rows),encoding='utf-8')
    return path


if __name__=='__main__':print(export())
