"""Generate opt-in trainer scripts plus manual CE address records; no startup Lua."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from engine import PROFILE, ROOT, LIMITS
from catalog import CONTROLS
from compatibility import OFFLINE_ONLY
from visual_settings import DEFAULTS as VISUAL_DEFAULTS,BOUNDS as VISUAL_BOUNDS


def label(key,title):return 'Trainer | '+title+(' [offline only]' if key in OFFLINE_ONLY else '')


def runtime_source():
    labels='{'+','.join('['+json.dumps(key)+']='+json.dumps(label(key,title),ensure_ascii=False) for _,key,title,_,_ in CONTROLS)+'}'
    bounds='{'+','.join('['+json.dumps(key)+']={'+str(low)+','+str(high)+'}' for key,(low,high) in LIMITS.items())+'}'
    offline='{'+','.join('['+json.dumps(k)+']='+json.dumps(v)for k,v in OFFLINE_ONLY.items())+'}'
    stock='{'+','.join('{'+','.join('['+off+']='+str(value)for off,value in fields.items())+'}'for fields in PROFILE['stock_weapon_data'])+'}'
    visual='{'+','.join('['+json.dumps(k)+']='+json.dumps(v)for k,v in VISUAL_DEFAULTS.items())+'}'
    visual_bounds='{'+','.join('['+json.dumps(k)+']={'+str(v[0])+','+str(v[1])+'}'for k,v in VISUAL_BOUNDS.items())+'}'
    return (ROOT/'ce_runtime.lua').read_text(encoding='utf-8').replace('@MD5@',PROFILE['md5']).replace('@LABELS@',labels).replace('@LIMITS@',bounds).replace('@OFFLINE@',offline).replace('@STOCK@',stock).replace('@VDEFAULTS@',visual).replace('@VBOUNDS@',visual_bounds).replace('@VISUALS@',(ROOT/'ce_visuals.lua').read_text(encoding='utf-8')).replace('@NATIVE@',(ROOT/'ce_native.lua').read_text(encoding='utf-8'))


def trainer_script(key,value):
    return '[ENABLE]\n{$lua}\nif syntaxcheck then return end\n-- RangeLab feature: '+key+'\n'+runtime_source()+f"\nRangeLabCE.enable('{key}',{value})\n"+'{$asm}\n[DISABLE]\n{$lua}\nif syntaxcheck then return end\n'+f"if RangeLabCE then RangeLabCE.disable('{key}') end\n"+'{$asm}\n'


def visual_preferences_script():
    values=',\n  '.join(key+' = '+json.dumps(value)for key,value in VISUAL_DEFAULTS.items())
    return '[ENABLE]\n{$lua}\nif syntaxcheck then return end\n'+runtime_source()+'\n-- Edit this preset, then uncheck/recheck this action to apply it.\nRangeLabCE.configureVisuals({\n  '+values+'\n})\n{$asm}\n[DISABLE]\n{$lua}\nif syntaxcheck then return end\n{$asm}\n'


def export(path=None):
    table = ET.Element('CheatTable', CheatEngineTableVersion='45')
    entries = ET.SubElement(table, 'CheatEntries')
    counter = iter(range(1, 1000))

    def group(parent, title):
        entry = ET.SubElement(parent, 'CheatEntry')
        ET.SubElement(entry, 'ID').text = str(next(counter))
        ET.SubElement(entry, 'Description').text = '"'+title+'"'
        ET.SubElement(entry, 'GroupHeader').text = '1'
        return ET.SubElement(entry, 'CheatEntries')

    def record(parent, title, kind, address, offset=None):
        entry = ET.SubElement(parent, 'CheatEntry')
        ET.SubElement(entry, 'ID').text = str(next(counter))
        ET.SubElement(entry, 'Description').text = '"'+title+'"'
        ET.SubElement(entry, 'VariableType').text = {'int': '4 Bytes', 'short': '2 Bytes', 'byte': 'Byte', 'float': 'Float'}[kind]
        ET.SubElement(entry, 'Address').text = address
        if offset is not None:
            offsets = ET.SubElement(entry, 'Offsets')
            for item in (offset if isinstance(offset, list) else [offset]):
                ET.SubElement(offsets, 'Offset').text = f'{item:X}'

    trainer=group(entries,'TRAINER CONTROLS — opt-in, defaults/presets; Alt activates aim and shooting')
    categories={}
    for category,key,title,description,default in CONTROLS:
        if category not in categories:categories[category]=group(trainer,category)
        entry=ET.SubElement(categories[category],'CheatEntry')
        ET.SubElement(entry,'ID').text=str(next(counter))
        ET.SubElement(entry,'Description').text='"'+label(key,title)+'"'
        ET.SubElement(entry,'VariableType').text='Auto Assembler Script'
        ET.SubElement(entry,'AssemblerScript').text=trainer_script(key,default if default is not None else 0)
    reset=ET.SubElement(trainer,'CheatEntry')
    ET.SubElement(reset,'ID').text=str(next(counter))
    ET.SubElement(reset,'Description').text='"Trainer | Reset all (uncheck to rearm)"'
    ET.SubElement(reset,'VariableType').text='Auto Assembler Script'
    ET.SubElement(reset,'AssemblerScript').text='[ENABLE]\n{$lua}\nif syntaxcheck then return end\nif RangeLabCE then RangeLabCE.stopAll() end\n{$asm}\n[DISABLE]\n{$lua}\nif syntaxcheck then return end\n{$asm}'
    appearance=ET.SubElement(trainer,'CheatEntry')
    ET.SubElement(appearance,'ID').text=str(next(counter))
    ET.SubElement(appearance,'Description').text='"Trainer | Visual preferences (edit preset; uncheck to reapply)"'
    ET.SubElement(appearance,'VariableType').text='Auto Assembler Script'
    ET.SubElement(appearance,'AssemblerScript').text=visual_preferences_script()

    player = group(entries, 'Player — dereference ac_client.exe+18AC00')
    root = '"ac_client.exe"+18AC00'
    for title, offset, kind in [('Health', 0xEC, 'int'), ('Armour', 0xF0, 'int'), ('X position', 4, 'float'), ('Y position', 8, 'float'), ('Z / eye position', 12, 'float'), ('Yaw', 0x34, 'float'), ('Pitch', 0x38, 'float'), ('Roll', 0x3C, 'float'), ('Air time', 0x48, 'int'), ('Selected weapon ID (inspect only)', 0xFC, 'int')]:
        record(player, title, kind, root, offset)
    record(player, 'Attack input — set 0 to release', 'byte', root, 0x204)
    record(player, 'Team', 'int', root, 0x30C)
    record(player, 'Physics state (inspect only: 0 alive, 4 editing)', 'byte', root, 0x76)
    for title,offset,kind in [('Akimbo available',0x100,'byte'),('On floor',0x5D,'byte'),('Jump request',0x5F,'byte'),('Crouch request',0x63,'byte')]:
        record(player,title,kind,root,offset)
    ammunition = group(entries, 'Ammo — weapon IDs 0 to 8')
    for index, name in enumerate(PROFILE['weapon_names']):
        sub = group(ammunition, f'{index}: {name}')
        for title, offset in [('Reserve', 0x104), ('Magazine / grenades', 0x128), ('Cooldown', 0x14C)]:
            record(sub, title, 'int', root, offset+index*4)
    camera = group(entries, 'Camera — static module offsets')
    record(camera,'Game mode ID (inspect only)','int','"ac_client.exe"+18ABF8')
    record(camera,'Network connected (inspect only: 0 local, 1 multiplayer)','int','"ac_client.exe"+18ABC8')
    record(camera, 'FOV (75 to 120)', 'float', '"ac_client.exe"+18A7CC')
    record(camera, 'Scoped FOV (5 to 60)', 'int', '"ac_client.exe"+18A834')
    record(camera, 'Sniper scoped flag (object field)', 'byte', root, [0x28,0x350])
    record(camera,'Sniper scope started (milliseconds)','int',root,[0x2C,0x350])
    record(camera,'Akimbo expiry (milliseconds)','int',root,[0x2C,0x35C])
    record(camera, 'Game milliseconds', 'int', '"ac_client.exe"+17F10C')
    actors = group(entries, 'Bot vector slots — empty slots may show ??')
    record(actors, 'Entity count (inspect only)', 'int', '"ac_client.exe"+18AC0C')
    for index in range(8):
        sub = group(actors, f'Slot {index} (check type == 1 for a local bot)')
        for title, off, kind in [('Health',0xEC,'int'),('State',0x76,'byte'),('Type',0x77,'byte'),('Team',0x30C,'int'),('Max speed (do not raise above normal)',0x44,'float'),('X',4,'float'),('Y',8,'float'),('Eye Z',12,'float'),('Head X',0x3F8,'float'),('Head Y',0x3FC,'float'),('Head Z',0x400,'float')]:
            record(sub,title,kind,'"ac_client.exe"+18AC04',[off,index*4])
    weapons = group(entries, 'Shared weapon settings — changes can affect bots too')
    for index, name in enumerate(PROFILE['weapon_names']):
        sub = group(weapons, f'{index}: {name}')
        for field, (offset, kind) in PROFILE['weapon_fields'].items():
            rva = PROFILE['weapon_table_rva']+index*PROFILE['weapon_stride']+offset
            record(sub, field.replace('_', ' ').title(), kind, f'"ac_client.exe"+{rva:X}')
    ET.SubElement(table, 'UserdefinedSymbols')
    ET.SubElement(table, 'Comments').text = (
        'RangeLab — AssaultCube 1.3.0.2, x86\n'
        'Verified executable SHA-256: '+PROFILE['sha256']+'\n'
        'Local player pointer resolved after a full game restart. Health and ammo were confirmed in the HUD.\n'
        'Attach Cheat Engine to ac_client.exe. Expand a group, edit a value, and check its box to freeze it.\n'
        'No startup Lua and no edits enabled automatically. Trainer feature checkboxes execute embedded Lua only when checked.\n'
        'Trainer scripts enforce the known executable MD5, module layout and player/weapon references. Manual records have no such guard.\n'
        'Trainer presets restore captured fields when unchecked. Manual CE changes do not automatically restore original values.\n'
        'Do not run RangeLab and CE trainer scripts on the same fields together. Uncheck all trainer scripts before changing process/table.\n'
        'Aim/auto shoot defaults: hold Alt, focus game, 35 degree cone, smoothing 4, players and bots; teammates skipped in team modes. Bunny hop: hold Space.\n'
        'Reserve-fed refill consumes reserve ammo; aiming, shooting, jumps and refills are gameplay actions and cannot be undone.\n'
        'The selected-weapon ID is for inspection; changing it alone does not update weapon-object references.\n'
        'Weapon stats are shared. Special shotgun spread/damage calculations may differ. Use for offline practice.\n'
        'Developer: Primo / supremobv.'
    )
    ET.indent(table, space='  ')
    target = Path(path) if path else ROOT/'AssaultCube-1.3.0.2.CT'
    ET.ElementTree(table).write(target, encoding='utf-8', xml_declaration=True)
    return target


if __name__ == '__main__':
    print(export())
