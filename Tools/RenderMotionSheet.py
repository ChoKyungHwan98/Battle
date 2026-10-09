"""Render stick-figure review sheets from CrunchMotionSheet.dump JSON (needs Pillow).

usage: python RenderMotionSheet.py out.png t0,t1,... a.json [b.json ...]
Each JSON becomes two rows: side view (forward = right) and top view (forward = up).
Left limbs red, right limbs blue, spine black.
"""
import json
import sys
from PIL import Image, ImageDraw

W, H_SIDE, H_TOP = 250, 190, 190
Y0, Y1 = -150., 270.          # forward range shown in the side view (cm)
SCALE = W/(Y1-Y0)
LEFT, RIGHT, MID = (200,40,40), (40,80,210), (30,30,30)


def chain(side):
    arm = ['spine_03','clavicle_'+side,'upperarm_'+side,'lowerarm_'+side,'hand_'+side]
    leg = ['pelvis','thigh_'+side,'calf_'+side,'foot_'+side,'ball_'+side]
    return arm, leg


def nearest(frames, t):
    return min(frames, key=lambda f: abs(f['t']-t))


def draw_panel(draw, ox, oy, frame, top):
    def pt(name):
        x, y, z = frame[name]
        if top:
            return ox+W/2-x*SCALE, oy+H_TOP-20-(y-Y0)*SCALE*.42
        return ox+(y-Y0)*SCALE, oy+H_SIDE-12-z*SCALE
    if not top:
        floor = oy+H_SIDE-12-20.5*SCALE
        draw.line([ox, floor, ox+W, floor], fill=(170,170,170))
        for mark in range(-100, 251, 50):
            x = ox+(mark-Y0)*SCALE
            draw.line([x, floor, x, floor+4], fill=(120,120,120))
    spine = ['pelvis','spine_01','spine_02','spine_03','neck_01','head']
    order = [('r', RIGHT), ('l', LEFT)]
    for side, color in order:
        arm, leg = chain(side)
        for names in (arm, leg):
            if top and names is arm:
                names = arm[1:]
            draw.line([pt(n) for n in names], fill=color, width=3)
        for n in ('foot_'+side, 'hand_'+side):
            x, y = pt(n)
            draw.ellipse([x-3, y-3, x+3, y+3], fill=color)
    if top:
        draw.line([pt('thigh_r'), pt('thigh_l')], fill=MID, width=3)
        draw.line([pt('clavicle_r'), pt('clavicle_l')], fill=(120,120,120), width=2)
    else:
        draw.line([pt(n) for n in spine], fill=MID, width=3)
    x, y = pt('root')
    draw.rectangle([x-2, y-2, x+2, y+2], outline=(0,150,0))
    draw.text((ox+4, oy+3), '%.2f' % frame['t'], fill=(0,0,0))


def main():
    out, times = sys.argv[1], [float(t) for t in sys.argv[2].split(',')]
    paths = sys.argv[3:]
    row_h = H_SIDE+H_TOP+18
    image = Image.new('RGB', (W*len(times), row_h*len(paths)), (255,255,255))
    draw = ImageDraw.Draw(image)
    for row, path in enumerate(paths):
        data = json.load(open(path, encoding='utf-8'))
        oy = row*row_h
        draw.text((4, oy+row_h-14), data['animation'].rsplit('/', 1)[1], fill=(0,0,0))
        for col, t in enumerate(times):
            frame = nearest(data['frames'], t)
            draw_panel(draw, col*W, oy, frame, False)
            draw_panel(draw, col*W, oy+H_SIDE, frame, True)
            draw.line([col*W, oy, col*W, oy+row_h], fill=(220,220,220))
        draw.line([0, oy+row_h-1, image.width, oy+row_h-1], fill=(0,0,0))
    image.save(out)
    print(out)


main()
