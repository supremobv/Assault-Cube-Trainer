"""Validated overlay preferences. Values never write game memory."""
import re

DEFAULTS={'esp_boxes':True,'esp_names':True,'esp_health':True,'esp_armour':True,'esp_distance':True,
          'enemy_color':'#FFAF70','ally_color':'#74E2C7','crosshair_color':'#74E2C7',
          'crosshair_style':'plus','crosshair_size':10,'crosshair_gap':4,'crosshair_width':2,
          'esp_line_width':2,'esp_text_size':9,'radar_size':180}
BOUNDS={'crosshair_size':(2,40),'crosshair_gap':(0,20),'crosshair_width':(1,6),
        'esp_line_width':(1,5),'esp_text_size':(7,20),'radar_size':(120,320)}


def validate(options):
    if not isinstance(options,dict) or set(options)-set(DEFAULTS):raise ValueError('Unknown visual setting.')
    result=dict(DEFAULTS)
    for key,value in options.items():
        if key in BOUNDS:
            low,high=BOUNDS[key]
            if type(value)is not int or not low<=value<=high:raise ValueError(f'{key} must be an integer from {low} to {high}.')
        elif key.startswith('esp_'):
            if type(value)is not bool:raise ValueError(f'{key} must be true or false.')
        elif key.endswith('_color'):
            if not isinstance(value,str)or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError('Colors use #RRGGBB format.')
            value=value.upper()
        elif key=='crosshair_style' and value not in ('plus','dot','circle'):raise ValueError('Unknown crosshair style.')
        result[key]=value
    return result
