"""Standalone manual screenshot stitching. Requires Python 3 and Pillow."""
import json
import math
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk


def display_to_original(y, display_height, original_height):
    """Map a display boundary to an original boundary, rounding half up."""
    if display_height <= 0 or original_height <= 0:
        raise ValueError('Image dimensions must be positive')
    if not 0 <= y <= display_height:
        raise ValueError('Display coordinate outside image')
    return int(math.floor(y * original_height / display_height + 0.5))


def validate_cut(value, height, label):
    if type(value) is not int or not 0 <= value <= height:
        raise ValueError(f'{label}: cut must be an integer from 0 to {height}; got {value!r}')


def validate_masks(im, masks, label):
    if not isinstance(masks, list):
        raise ValueError(f'{label}: masks must be a list')
    for n, mask in enumerate(masks):
        for key, limit in [('x1', im.width), ('x2', im.width), ('y1', im.height), ('y2', im.height)]:
            validate_cut(mask[key], limit, f'{label} mask {n+1} {key}')
        if mask['x1'] >= mask['x2'] or mask['y1'] >= mask['y2']:
            raise ValueError(f'{label} mask {n+1}: rectangle must have positive width and height')


def masked_image(im, crop):
    validate_masks(im, crop.get('masks', []), 'Image')
    mode = 'RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB'
    result = im.convert(mode)
    for m in crop.get('masks', []):
        # Pillow box paste uses exclusive right/bottom boundaries, just like crop.
        result.paste((255,255,255,255) if mode == 'RGBA' else (255,255,255),
                     (m['x1'],m['y1'],m['x2'],m['y2']))
    return result


def split_groups(images, crops, max_height=20000):
    if type(max_height) is not int or max_height <= 0:
        raise ValueError('Maximum part height must be a positive integer')
    groups, group, height = [], [], 0
    for i, (start, end) in enumerate(intervals(images, crops)):
        h = end-start
        if group and height+h > max_height:
            groups.append(group); group, height = [], 0
        group.append(i); height += h
    if group: groups.append(group)
    return groups


def intervals(images, crops):
    if not images or len(crops) != len(images):
        raise ValueError('Project needs one crop interval per image')
    result = []
    for i, (im, crop) in enumerate(zip(images, crops)):
        if im.width != images[0].width:
            raise ValueError(f'Image {i+1}: different width; no resizing allowed')
        validate_masks(im, crop.get('masks', []), f'Image {i+1}')
        start, end = crop['start_y'], crop['end_y']
        validate_cut(start, im.height, f'Image {i+1} START')
        validate_cut(end, im.height, f'Image {i+1} END')
        if start >= end:
            raise ValueError(f'Image {i+1}: invalid region {start}:{end}; START must be less than END')
        result.append((start, end))
    return result


def default_filename(kind, now=None):
    stamp = (now or datetime.now()).strftime('%Y%m%d_%H%M')
    return f'stitched_chat_{stamp}.png' if kind == 'png' else f'manual_stitch_{stamp}.json'


def project_data(paths, images, crops):
    intervals(images, crops)
    return dict(version=2, images=[dict(path=str(Path(p).resolve()),
        width=im.width, height=im.height, **crop)
        for p, im, crop in zip(paths, images, crops)])


def read_project(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    version = data.get('version', 1)
    if version not in (1, 2):
        raise ValueError('Unsupported project version')
    records = data['images']
    paths = [str((Path(path).parent / Path(r['path'] if version == 2 else r)).resolve()) for r in records]
    images = load_images(paths)
    crops = [dict(start_y=0, end_y=im.height) for im in images]
    if version == 1:
        if data['sizes'] != [[im.width, im.height] for im in images]:
            raise ValueError('Source image dimensions changed since project save')
        seams = data['seams']
        if len(seams) != len(images)-1:
            raise ValueError('Incorrect seam count')
        for i, seam in enumerate(seams):
            if seam['a_index'] != i or seam['b_index'] != i+1:
                raise ValueError(f'Pair {i+1}: incorrect indices')
            crops[i]['end_y'] = seam['a_cut_y']
            crops[i+1]['start_y'] = seam['b_cut_y']
    else:
        for i, (record, im) in enumerate(zip(records, images)):
            if (record['width'], record['height']) != im.size:
                raise ValueError(f'Image {i+1}: source dimensions changed')
            crops[i] = dict(start_y=record['start_y'], end_y=record['end_y'], masks=record.get('masks', []))
    intervals(images, crops)
    return paths, images, crops


def assemble(images, crops):
    regions = intervals(images, crops)
    # Lossless channel expansion only; no geometry resampling or color conversion.
    mode = 'RGBA' if any('A' in im.getbands() or 'transparency' in im.info for im in images) else 'RGB'
    out = Image.new(mode, (images[0].width, sum(b-a for a,b in regions)))
    y = 0
    for i, (im, (start, end)) in enumerate(zip(images, regions)):
        crop = masked_image(im, crops[i]).crop((0, start, im.width, end))
        if crop.mode != mode:
            crop = crop.convert(mode)
        out.paste(crop, (0, y))  # No alpha mask: preserve RGBA values exactly.
        y += end-start
    return out


def load_images(paths):
    images = []
    for path in paths:
        with Image.open(path) as im:
            if im.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P', '1'):
                raise ValueError(f'{path}: unsupported mode {im.mode}; use an 8-bit screenshot')
            im.load()
            images.append(im.copy())
    if not images:
        raise ValueError('Select at least one image')
    if any(im.width != images[0].width for im in images):
        raise ValueError('Screenshots have different widths. They will not be resized.')
    return images


class ImageView(ttk.Frame):
    def __init__(self, parent, app, side):
        super().__init__(parent)
        self.app, self.side = app, side
        self.im = None
        self.mask_drag_active = False
        self.mask_anchor = None
        self.mask_end = None
        self.selected_mask = None
        self.highlight = None
        self.dragging = None
        heading = ttk.Frame(self)
        heading.pack(fill='x')
        self.title = ttk.Label(heading)
        self.title.pack(side='left', fill='x', expand=True)
        self.remove_button = ttk.Button(heading, text='Remove Image',
            command=lambda: self.app.remove_image(self.app.index+self.side))
        self.remove_button.pack(side='right', padx=3)
        self.details = ttk.Label(self)
        self.details.pack(fill='x')
        self.values = {}
        for key, label in [('start_y', 'START'), ('end_y', 'END')]:
            row = ttk.Frame(self)
            row.pack(fill='x')
            ttk.Label(row, text=label + ' Y:').pack(side='left')
            value = self.values[key] = tk.StringVar()
            entry = ttk.Entry(row, textvariable=value, width=10)
            entry.pack(side='left')
            entry.bind('<Return>', lambda e, k=key: self.apply_entry(k))
            ttk.Button(row, text='Set ' + label.title(), command=lambda k=key: self.apply_entry(k)).pack(side='left')
        self.hint = ttk.Label(self, text='Left: START | Right: END | Shift-drag: white mask\nClick mask: select | Delete: remove | Ctrl+Z: undo')
        self.hint.pack(fill='x')
        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(frame, background='#222', highlightthickness=2, highlightbackground='#444', highlightcolor='#444')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        bar = ttk.Scrollbar(frame, orient='vertical', command=self.canvas.yview)
        bar.grid(row=0, column=1, sticky='ns')
        hbar = ttk.Scrollbar(frame, orient='horizontal', command=self.canvas.xview)
        hbar.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        self.canvas.configure(yscrollcommand=bar.set, xscrollcommand=hbar.set)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<Button-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.right_click)
        self.canvas.bind('<B3-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-3>', lambda e: setattr(self, 'dragging', None))
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Leave>', lambda e: self.canvas.delete('guide'))
        for key in ('<Delete>', '<BackSpace>'):
            self.canvas.bind(key, self.delete_mask)
        self.canvas.bind('<Control-z>', lambda e: self.app.undo_mask())
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta/120), 'units'))

    def apply_entry(self, key):
        try:
            self.app.set_cut(self.side, key, int(self.values[key].get()))
        except ValueError as exc:
            messagebox.showerror('Invalid crop', str(exc))
        return 'break'

    def point(self, event):
        if self.im is None: return None
        # The image is anchored at canvas (0,0); canvasx/y include scroll offsets.
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if not 0 <= x <= self.dw or not 0 <= y <= self.dh: return None
        return (display_to_original(x,self.dw,self.im.width),
                display_to_original(y,self.dh,self.im.height))

    def press(self, event):
        self.canvas.focus_set()
        self.dragging = None
        self.mask_anchor = None
        self.mask_drag_active = False
        shift_active = self.app.mask_mode(event.state)
        print(f'LEFT PRESS shift_active={shift_active} mode={"MASK" if shift_active else "CROP"} event.state={event.state}', flush=True)
        point = self.point(event)
        if point is None: return 'break'
        if shift_active:
            self.mask_drag_active = True
            self.app.update_mode()
            self.app.feedback('MASK: selecting area...')
            self.mask_anchor = self.mask_end = point
            self.selected_mask = None
            self.line()
            self.draw_proposed_mask()
            return 'break'
        masks = self.app.crops[self.app.index+self.side].get('masks', [])
        hit = next((i for i in range(len(masks)-1,-1,-1)
                    if masks[i]['x1'] <= point[0] < masks[i]['x2'] and masks[i]['y1'] <= point[1] < masks[i]['y2']), None)
        if hit is not None:
            for view in self.app.views: view.selected_mask = None
            self.selected_mask = hit
            for view in self.app.views: view.line()
            self.app.feedback('Mask selected — Delete / Backspace to remove')
            return 'break'
        self.selected_mask = None
        self.dragging = 'start_y'
        self.drag(event)
        return 'break'

    def right_click(self, event):
        if self.mask_drag_active: return 'break'
        self.canvas.focus_set()
        self.dragging = 'end_y'
        self.drag(event)
        return 'break'

    def drag(self, event):
        point = self.point(event)
        if point is None: return 'break'
        if self.mask_drag_active:
            self.mask_end = point
            self.draw_proposed_mask()
        elif self.dragging is not None:
            try:
                self.app.set_cut(self.side, self.dragging, point[1])
                self.highlight = self.dragging
                self.line()
                self.app.feedback(f'{"START" if self.dragging == "start_y" else "END"} set to Y={point[1]}')
            except ValueError as exc:
                self.app.feedback(str(exc))
        return 'break'

    def draw_proposed_mask(self):
        self.canvas.delete('proposed_mask')
        if self.mask_anchor is None: return
        x1,y1 = self.mask_anchor; x2,y2 = self.mask_end
        self.canvas.create_rectangle(x1*self.dw/self.im.width,y1*self.dh/self.im.height,
            x2*self.dw/self.im.width,y2*self.dh/self.im.height,
            outline='#ffd34e',width=3,fill='white',stipple='gray50',tags='proposed_mask')
        self.canvas.tag_raise('proposed_mask')

    def release(self, event):
        if self.mask_drag_active:
            end = self.point(event) or self.mask_end
            x1,x2 = sorted((self.mask_anchor[0],end[0]))
            y1,y2 = sorted((self.mask_anchor[1],end[1]))
            self.mask_drag_active = False
            self.mask_anchor = self.mask_end = None
            self.canvas.delete('proposed_mask')
            if x1 < x2 and y1 < y2:
                self.app.add_mask(self.app.index+self.side,dict(x1=x1,y1=y1,x2=x2,y2=y2))
            else: self.app.feedback('Mask ignored: drag a rectangle with positive width and height')
        self.dragging = None
        self.app.update_mode()
        return 'break'

    def cancel_mask(self):
        active = self.mask_drag_active
        self.mask_drag_active = False
        self.mask_anchor = self.mask_end = self.dragging = None
        self.canvas.delete('proposed_mask')
        return active

    def delete_mask(self, event=None):
        if self.selected_mask is not None:
            self.app.delete_mask(self.app.index+self.side,self.selected_mask)
            self.selected_mask = None
            self.line()
        return 'break'

    def hover(self, event):
        self.canvas.delete('guide')
        point = self.point(event)
        if point is None: return
        y = point[1]*self.dh/self.im.height
        self.canvas.create_line(0,y,self.dw,y,fill='#99b5c2',dash=(3,5),tags='guide')
        self.canvas.create_text(6,y,anchor='sw',text=f'Y: {point[1]}',fill='#99b5c2',tags='guide')

    def draw(self):
        if self.im is None: return
        scale = self.app.zoom.get()
        factor = min(1.0, max(1, self.canvas.winfo_width()-4)/self.im.width) if scale == 'Fit width' else float(scale.rstrip('%'))/100
        self.dw, self.dh = max(1, round(self.im.width*factor)), max(1, round(self.im.height*factor))
        self.photo = ImageTk.PhotoImage(self.im.resize((self.dw, self.dh), Image.Resampling.LANCZOS))
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
        # Extra border space keeps the exact END=height boundary reachable.
        self.canvas.configure(scrollregion=(0, -24, self.dw, self.dh+24))
        self.line()
        self.draw_proposed_mask()

    def line(self):
        if self.im is None or not hasattr(self, 'dh'): return
        crop = self.app.crops[self.app.index+self.side]
        self.details.config(text=f'{self.im.width} × {self.im.height} | KEPT: {crop["end_y"]-crop["start_y"]} px | Masks: {len(crop.get("masks", []))}')
        self.canvas.delete('crop_overlay')
        for i,m in enumerate(crop.get('masks', [])):
            self.canvas.create_rectangle(m['x1']*self.dw/self.im.width,m['y1']*self.dh/self.im.height,
                m['x2']*self.dw/self.im.width,m['y2']*self.dh/self.im.height,fill='white',
                outline='', width=0, tags='crop_overlay')
        ys = {k: crop[k]*self.dh/self.im.height for k in ('start_y','end_y')}
        for a,b in [(0,ys['start_y']), (ys['end_y'],self.dh)]:
            self.canvas.create_rectangle(0,a,self.dw,b,fill='black',stipple='gray50',outline='',tags='crop_overlay')
        for key,label,color in [('start_y','START','#36ee9b'),('end_y','END','#ff6868')]:
            self.values[key].set(str(crop[key]))
            y = ys[key]
            self.canvas.create_line(0,y,self.dw,y,fill=color,width=5 if self.highlight==key else 3,
                dash=() if key=='start_y' else (8,4), tags=('crop_overlay',key))
            self.canvas.create_text(8,y,anchor='nw' if key=='start_y' else 'sw',
                text=f'{label} Y={crop[key]}',fill=color,tags=('crop_overlay',key))


class App:
    def __init__(self, root):
        self.root = root
        root.title('Manual Screenshot Stitcher')
        root.geometry('1200x850')
        self.paths, self.images, self.crops = [], [], []
        self.shift_pressed = False
        self.manual_mode = None  # None: temporary Shift mode; CROP/MASK: GUI override
        self.shift_keys = set()
        self.focus_check = None
        self.last_save_dir = None
        self.mask_history = []
        self.feedback_timer = None
        self.index, self.project, self.dirty = 0, None, False
        toolbar = ttk.Frame(root)
        toolbar.pack(fill='x')
        for label, command in [('Select Screenshots', self.select), ('Open Project', self.open), ('Save Project', self.save), ('Change Order', self.reorder)]:
            ttk.Button(toolbar, text=label, command=command).pack(side='left', padx=3, pady=5)
        self.max_part_height = tk.StringVar(value='20000')
        ttk.Label(toolbar,text='Max PNG height:').pack(side='left')
        ttk.Entry(toolbar,textvariable=self.max_part_height,width=8).pack(side='left')
        self.zoom = tk.StringVar(value='Fit width')
        box = ttk.Combobox(toolbar, textvariable=self.zoom, values=['Fit width','25%','50%','75%','100%'], state='readonly', width=10)
        box.pack(side='right')
        box.bind('<<ComboboxSelected>>', lambda e: [v.draw() for v in self.views])
        self.mode_label = tk.Label(root, anchor='w', padx=8, pady=8,
            font=('Segoe UI', 12, 'bold'))
        self.mode_label.pack(fill='x', padx=6, pady=3)
        mode_buttons = ttk.Frame(root)
        mode_buttons.pack(fill='x', padx=6)
        self.crop_button = ttk.Button(mode_buttons, text='CROP Mode', command=lambda: self.set_mode('CROP'))
        self.crop_button.pack(side='left', padx=3, pady=3)
        self.mask_button = ttk.Button(mode_buttons, text='MASK Mode', command=lambda: self.set_mode('MASK'))
        self.mask_button.pack(side='left', padx=3, pady=3)
        ttk.Button(mode_buttons, text='Use Shift (Auto)', command=lambda: self.set_mode(None)).pack(side='left', padx=3, pady=3)
        ttk.Label(mode_buttons, text='CROP / MASK buttons override Shift; Auto restores Shift-drag.').pack(side='left', padx=6)
        self.build_label = ttk.Label(root, text=f'Manual stitch v5 | Running: {Path(__file__).resolve()}')
        self.build_label.pack(fill='x', padx=6)
        self.status = ttk.Label(root, text='Select screenshots or open a project.')
        self.status.pack(fill='x', padx=6)
        panel = ttk.Frame(root)
        panel.pack(fill='both', expand=True)
        self.views = [ImageView(panel, self, side) for side in (0, 1)]
        for view in self.views:
            view.pack(side='left', fill='both', expand=True, padx=4)
        footer = ttk.Frame(root)
        footer.pack(fill='x')
        for label, command in [('Previous Pair',lambda:self.navigate(-1)), ('Next Pair',lambda:self.navigate(1)), ('Reset',self.reset), ('Preview Seam',self.preview), ('Confirm & Next',self.confirm), ('Build Final Image',self.build)]:
            ttk.Button(footer,text=label,command=command).pack(side='left',padx=3,pady=6)
        for key, command in [('<Left>',lambda:self.navigate(-1)),('<Right>',lambda:self.navigate(1)),('<Return>',self.confirm),('p',self.preview),('r',self.reset)]:
            root.bind(key, lambda e, c=command: c() if not isinstance(e.widget,(ttk.Entry,ttk.Combobox)) else None)
        root.bind('<Control-z>', lambda e: self.undo_mask() if not isinstance(e.widget,ttk.Entry) else None)
        # The first bindtag observes keys before Entry/Canvas classes or shortcuts
        # can consume them. bind_all also covers other application toplevels.
        self.key_tag = f'ManualStitchKeys_{id(self)}'
        def observe(tag, sequence, handler):
            if tag == 'all':
                callback = lambda e: None if self.key_tag in e.widget.bindtags() else handler(e)
            else:
                callback = handler
            root.bind_class(tag, sequence, callback, add='+')
        for tag in (self.key_tag, 'all'):
            observe(tag, '<KeyPress>', self.debug_key_press)
            observe(tag, '<KeyRelease>', self.debug_key_release)
            for key in ('Shift_L', 'Shift_R'):
                observe(tag, f'<KeyPress-{key}>', self.shift_down)
                observe(tag, f'<KeyRelease-{key}>', self.shift_up)
        self.add_key_tag(root)
        root.bind_all('<Escape>', self.cancel_mask_drag, add='+')
        root.bind_all('<FocusOut>', self.focus_out, add='+')
        self.update_mode()
        # Establish keyboard focus on launch, before the first canvas click.
        root.after_idle(root.focus_set)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def add_key_tag(self, widget):
        tags = widget.bindtags()
        if self.key_tag not in tags:
            widget.bindtags((self.key_tag,) + tags)
        for child in widget.winfo_children(): self.add_key_tag(child)

    def log_key(self, event, action):
        # Tk chooses the most specific binding on a tag, so Shift handlers log too.
        print(f'KEY {action}: keysym={event.keysym} keycode={getattr(event, "keycode", "?")} '
              f'state={getattr(event, "state", "?")} focus={self.root.focus_get()}', flush=True)

    def debug_key_press(self, event):
        self.log_key(event, 'PRESS')
        if event.keysym in ('Shift_L', 'Shift_R', 'Shift'):
            self.shift_down(event, logged=True)

    def debug_key_release(self, event):
        self.log_key(event, 'RELEASE')
        if event.keysym in ('Shift_L', 'Shift_R', 'Shift'):
            self.shift_up(event, logged=True)

    def shift_down(self, event, logged=False):
        if not logged: self.log_key(event, 'PRESS')
        self.shift_keys.add(event.keysym)
        if not self.shift_pressed:
            print('SHIFT DOWN detected -> MASK MODE', flush=True)
        self.shift_pressed = True
        self.update_mode()

    def shift_up(self, event, logged=False):
        if not logged: self.log_key(event, 'RELEASE')
        self.shift_keys.discard(event.keysym)
        self.shift_pressed = bool(self.shift_keys)
        if not self.shift_pressed:
            print('SHIFT UP detected -> CROP MODE', flush=True)
        self.update_mode()

    def mask_mode(self, mouse_state=0):
        if self.manual_mode is not None:
            return self.manual_mode == 'MASK'
        return self.shift_pressed or bool(mouse_state & 0x0001) or any(v.mask_drag_active for v in self.views)

    def set_mode(self, mode):
        if mode not in (None, 'CROP', 'MASK'): raise ValueError('Unknown mode')
        for view in self.views: view.cancel_mask()
        # Clear stale modifier bookkeeping whenever the user explicitly switches.
        self.shift_keys.clear()
        self.shift_pressed = False
        self.manual_mode = mode
        self.update_mode()
        self.feedback('Mode: ' + (mode if mode else 'AUTO — hold Shift to mask'))

    def update_mode(self):
        mask = self.mask_mode()
        shift = 'DOWN' if self.shift_pressed else 'UP'
        source = 'AUTO / Shift' if self.manual_mode is None else 'MANUAL'
        if mask:
            self.mode_label.config(text=f'MODE: MASK | {source} | Shift: {shift} | Left-drag: create white mask',
                                   bg='#ffe6a3', fg='#593800')
        else:
            self.mode_label.config(text=f'MODE: CROP | {source} | Shift: {shift} | Left click: START | Right click: END',
                                   bg='#e5edf5', fg='#183044')
        for view in self.views:
            view.canvas.config(cursor='crosshair' if mask else '',
                highlightbackground='#e4a321' if mask else '#444',
                highlightcolor='#e4a321' if mask else '#444')

    def cancel_mask_drag(self, event=None):
        cancelled = False
        for view in self.views:
            cancelled = view.cancel_mask() or cancelled
        if cancelled: self.feedback('MASK: unfinished selection cancelled')
        self.update_mode()
        return 'break'

    def focus_out(self, event):
        # Moving focus between the two canvases/entries must not reset Shift.
        # Losing application focus must reset it: key release may occur elsewhere.
        if self.focus_check is not None: self.root.after_cancel(self.focus_check)
        self.focus_check = self.root.after_idle(self.check_focus)

    def check_focus(self):
        self.focus_check = None
        if self.root.focus_displayof() is None:
            self.shift_keys.clear()
            if self.shift_pressed: print('FOCUS LOST -> CROP MODE', flush=True)
            self.shift_pressed = False
            self.cancel_mask_drag()

    def discard(self):
        return not self.dirty or messagebox.askyesno('Unsaved edits','Discard unsaved project edits?')

    def install(self, paths, images, crops, project=None):
        intervals(images, crops)
        self.paths, self.images, self.crops = paths, images, crops
        self.mask_history = []
        for crop in crops: crop.setdefault('masks', [])
        for view in self.views:
            view.selected_mask = None
            view.cancel_mask()
        self.project, self.index, self.dirty = project, 0, False
        self.show()

    def select(self):
        if not self.discard(): return
        paths = filedialog.askopenfilenames(filetypes=[('Screenshots','*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff'),('All files','*.*')])
        if not paths: return
        try:
            paths = sorted(paths, key=lambda p:(Path(p).name.casefold(),p))
            images = load_images(paths)
            self.install(list(paths), images, [dict(start_y=0,end_y=im.height) for im in images])
            self.dirty = True
        except Exception as exc: messagebox.showerror('Cannot load screenshots',str(exc))

    def show(self):
        count = max(1, len(self.images)-1)
        self.status.config(text=f'{len(self.images)} images | Pair {self.index+1} / {count} | Independent image crops; green START / red END' if self.images else 'No images remaining. Select screenshots or open a project.')
        for offset, view in enumerate(self.views):
            i = self.index + offset
            view.im = self.images[i] if i < len(self.images) else None
            view.remove_button.config(state='normal' if view.im is not None else 'disabled')
            if view.im is None:
                view.canvas.delete('all'); view.title.config(text=''); view.details.config(text='')
                for value in view.values.values(): value.set('')
            else:
                view.title.config(text=Path(self.paths[i]).name)
                view.draw()

    def set_cut(self, side, key, value):
        i = self.index + side
        if i >= len(self.images): return
        if key not in ('start_y', 'end_y'): raise ValueError('Unknown crop boundary')
        candidate = dict(self.crops[i], **{key: value})
        try:
            intervals([self.images[i]], [candidate])
        except ValueError as exc:
            raise ValueError(f'Screenshot {i+1} ({Path(self.paths[i]).name}): {exc}') from exc
        if candidate != self.crops[i]:
            self.crops[i] = candidate
            self.dirty = True
        for view in self.views: view.line()

    def remove_image(self, i):
        if not 0 <= i < len(self.images): return
        name = Path(self.paths[i]).name
        for view in self.views:
            view.selected_mask = None
            view.cancel_mask()
        # All three lists describe the same ordered images. Remove one aligned
        # record, retaining every remaining image's exact crop and mask values.
        del self.paths[i]
        del self.images[i]
        del self.crops[i]
        self.mask_history.clear()  # Old undo entries refer to pre-removal indices.
        self.index = min(self.index, max(0,len(self.images)-2))
        self.dirty = True
        self.show()
        self.update_mode()
        self.feedback(f'Removed from project: {name} — original file retained')

    def navigate(self, delta):
        if self.images:
            for view in self.views:
                view.selected_mask = None
                view.cancel_mask()
            self.index = max(0, min(max(0,len(self.images)-2), self.index+delta))
            self.show()

    def reset(self):
        for i in range(self.index, min(self.index+2, len(self.images))):
            self.crops[i] = dict(start_y=0, end_y=self.images[i].height, masks=self.crops[i].get('masks', []))
        self.dirty = True
        self.show()

    def confirm(self):
        if not self.images: return
        try:
            intervals(self.images, self.crops)
            self.navigate(1)
        except ValueError as exc: messagebox.showerror('Invalid crop', str(exc))

    def preview(self):
        if len(self.images) < 2: return
        try:
            regions = intervals(self.images, self.crops)
            start, a_end = regions[self.index]
            b_start, end = regions[self.index+1]
            a,b = [masked_image(self.images[i], self.crops[i]) for i in (self.index,self.index+1)]
            top = a.crop((0,max(start,a_end-500),a.width,a_end))
            bottom = b.crop((0,b_start,b.width,min(end,b_start+500)))
            original = Image.new('RGBA',(a.width,top.height+bottom.height))
            original.paste(top.convert('RGBA'),(0,0))
            original.paste(bottom.convert('RGBA'),(0,top.height))
            window = tk.Toplevel(self.root)
            window.title(f'Seam {self.index+1} — original pixels, 100% preview')
            ttk.Label(window,text=f'Exact join: A Y={a_end} / B Y={b_start}; red line is an overlay only').pack()
            canvas = tk.Canvas(window,width=min(a.width,1000),height=min(original.height,700))
            canvas.pack(side='left',fill='both',expand=True)
            bar = ttk.Scrollbar(window,command=canvas.yview)
            bar.pack(side='right',fill='y')
            hbar = ttk.Scrollbar(window,orient='horizontal',command=canvas.xview)
            hbar.pack(side='bottom',fill='x')
            canvas.configure(yscrollcommand=bar.set,xscrollcommand=hbar.set,scrollregion=(0,0,original.width,original.height))
            canvas.photo = ImageTk.PhotoImage(original)
            canvas.create_image(0,0,anchor='nw',image=canvas.photo)
            canvas.create_line(0,top.height,a.width,top.height,fill='red',width=1)
        except Exception as exc: messagebox.showerror('Cannot preview',str(exc))

    def feedback(self, text):
        if self.feedback_timer is not None:
            self.root.after_cancel(self.feedback_timer)
        self.status.config(text=text)
        self.feedback_timer = self.root.after(3500, self.restore_status)

    def restore_status(self):
        self.feedback_timer = None
        self.status.config(text=f'Pair {self.index+1} / {max(1,len(self.images)-1)} | Left: START | Right: END | Shift-drag: mask')

    def add_mask(self, i, mask):
        validate_masks(self.images[i], [mask], f'Image {i+1}')
        masks = self.crops[i].setdefault('masks', [])
        self.mask_history.append(('add', i, len(masks), dict(mask)))
        masks.append(dict(mask))
        self.dirty = True
        for view in self.views: view.line()
        self.feedback(f'Mask added: ({mask["x1"]}, {mask["y1"]}) - ({mask["x2"]}, {mask["y2"]})')

    def delete_mask(self, i, n):
        mask = self.crops[i]['masks'].pop(n)
        self.mask_history.append(('delete', i, n, dict(mask)))
        self.dirty = True
        for view in self.views: view.selected_mask = None; view.line()
        self.feedback('Mask deleted')

    def undo_mask(self):
        if not self.mask_history: return 'break'
        action,i,n,mask = self.mask_history.pop()
        if action == 'add': self.crops[i]['masks'].pop(n)
        else: self.crops[i]['masks'].insert(n,mask)
        self.dirty = True
        for view in self.views: view.selected_mask = None; view.line()
        self.feedback(f'Mask {action} undone on screenshot {i+1}')
        return 'break'

    def save_options(self, kind):
        return dict(initialfile=default_filename(kind),
                    **({'initialdir': self.last_save_dir} if self.last_save_dir else {}))

    def save(self):
        if not self.images: return False
        path = filedialog.asksaveasfilename(**self.save_options('json'), defaultextension='.json', filetypes=[('Project','*.json')])
        if not path: return False
        try:
            if Path(path).resolve() in [Path(p).resolve() for p in self.paths]:
                raise ValueError('Project must not overwrite a source screenshot')
            Path(path).write_text(json.dumps(project_data(self.paths,self.images,self.crops),indent=2),encoding='utf-8')
            self.project,self.dirty = path,False
            self.last_save_dir = str(Path(path).parent)
            return True
        except Exception as exc: messagebox.showerror('Cannot save',str(exc)); return False

    def open(self):
        if not self.discard(): return
        path = filedialog.askopenfilename(filetypes=[('Project','*.json')])
        if not path: return
        try:
            self.install(*read_project(path), project=path)
        except Exception as exc: messagebox.showerror('Cannot open project',str(exc))

    def reorder(self):
        if not self.images: return
        window = tk.Toplevel(self.root)
        window.title('Screenshot order / removal')
        window.transient(self.root)
        window.grab_set()
        order = list(range(len(self.images)))
        listing = tk.Listbox(window,width=90,height=18)
        listing.pack()
        def refresh(selected=0):
            listing.delete(0,'end')
            for i in order: listing.insert('end',Path(self.paths[i]).name)
            if order: listing.selection_set(min(selected,len(order)-1))
        def move(delta):
            selection = listing.curselection()
            if not selection: return
            i = selection[0]; j = i+delta
            if 0 <= j < len(order): order[i],order[j] = order[j],order[i]; refresh(j)
        def remove_selected():
            selection = listing.curselection()
            if selection:
                del order[selection[0]]
                refresh(selection[0])
        def apply():
            if not order:
                while self.images: self.remove_image(len(self.images)-1)
                window.destroy()
                return
            if order != list(range(len(order))):
                paths = [self.paths[i] for i in order]; images = [self.images[i] for i in order]
                crops = [dict(self.crops[i]) for i in order]
                self.install(paths,images,crops)
                self.dirty = True
            window.destroy()
        refresh()
        for label,cmd in [('Up',lambda:move(-1)),('Down',lambda:move(1)),('Remove Selected',remove_selected),('Apply Order',apply)]: ttk.Button(window,text=label,command=cmd).pack(side='left')

    def build(self):
        if not self.images: return
        try:
            regions = intervals(self.images,self.crops)
            total = sum(b-a for a,b in regions)
            groups = split_groups(self.images,self.crops,int(self.max_part_height.get()))
            export_images, export_crops = list(self.images), [dict(c, masks=[dict(m) for m in c.get('masks',[])]) for c in self.crops]
            summary = '\n'.join(f'Image {i+1:03d}: {Path(p).name}\n  original height = {im.height}; used region = {a}:{b}; output height = {b-a}' for i,(p,im,(a,b)) in enumerate(zip(self.paths,self.images,regions)))
            summary += f'\n\nFinal width: {self.images[0].width}\nFinal height: {total}\nScreenshots: {len(self.images)}'
            summary += f'\nPNG parts: {len(groups)} (whole crops; an oversized crop stays in its own part)'
            print(summary)
            window = tk.Toplevel(self.root); window.title('Final crop summary')
            text = tk.Text(window,width=100,height=25,wrap='word'); text.pack(fill='both',expand=True)
            text.insert('1.0',summary); text.config(state='disabled')
            def export():
                path = filedialog.asksaveasfilename(**self.save_options('png'),defaultextension='.png',filetypes=[('PNG','*.png')],parent=window)
                if not path: return
                if Path(path).resolve() in [Path(p).resolve() for p in self.paths]:
                    messagebox.showerror('Invalid output','Output must not overwrite a source screenshot.',parent=window); return
                try:
                    target = Path(path)
                    targets = [target] if len(groups)==1 else [target.with_name(f'{target.stem}_part{n+1:03d}.png') for n in range(len(groups))]
                    if any(t.resolve() in [Path(p).resolve() for p in self.paths] for t in targets):
                        raise ValueError('A part filename would overwrite a source screenshot')
                    if len(groups)>1 and any(t.exists() for t in targets):
                        if not messagebox.askyesno('Overwrite parts','Some output parts already exist. Overwrite them?',parent=window): return
                    for target, group in zip(targets,groups):
                        assemble([export_images[i] for i in group],[export_crops[i] for i in group]).save(target,format='PNG')
                    self.last_save_dir = str(Path(path).parent)
                    messagebox.showinfo('Image saved',f'Saved {len(targets)} PNG file(s) in {Path(path).parent}\n{export_images[0].width} × {total} total pixels',parent=window)
                    window.destroy()
                except Exception as exc: messagebox.showerror('Cannot build',str(exc),parent=window)
            ttk.Button(window,text='Save PNG',command=export).pack(pady=6)
        except Exception as exc: messagebox.showerror('Cannot build',str(exc))

    def close(self):
        if self.discard(): self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
