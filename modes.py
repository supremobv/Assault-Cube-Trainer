"""Mode IDs and team semantics from the verified 1.3.0.2 protocol.h."""
TEAM_MODES={0,4,5,7,11,13,14,16,17,20,21}
BOT_MODES={7,8,12,18,19,20,21}
NAMES=('Team deathmatch','Co-op edit','Deathmatch','Survivor','Team survivor','Capture the flag',
       'Pistol frenzy','Bot team deathmatch','Bot deathmatch','Last Swiss standing',
       'One shot one kill','Team one shot one kill','Bot one shot one kill','Hunt the flag',
       'Team keep the flag','Keep the flag','Team pistol frenzy','Team Last Swiss standing',
       'Bot pistol frenzy','Bot Last Swiss standing','Bot team survivor','Bot team one shot one kill')


def describe(mode):
    return {'id':mode,'name':NAMES[mode] if 0<=mode<len(NAMES) else 'Demo' if mode==-1 else f'Unknown mode {mode}',
            'teams':mode in TEAM_MODES,'bots':mode in BOT_MODES}


def allied(local_team,other_team,team_mode):
    return bool(team_mode and local_team in (0,1) and other_team==local_team)
