import os
import sys
import json
from pathlib import Path

# Windowed executables have no console streams. Keep diagnostic prints harmless.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

import manual_stitch as tool

if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
    report = Path(sys.argv[2])
    try:
        images = [tool.Image.new('RGBA', (8, 20), (40, 80, 120, 160)) for _ in range(2)]
        crops = [dict(start_y=2, end_y=18, masks=[dict(x1=1,y1=5,x2=4,y2=8)]),
                 dict(start_y=3, end_y=15, masks=[])]
        output = tool.assemble(images, crops)
        assert output.size == (8, 28)
        assert output.getpixel((1,3)) == (255,255,255,255)
        assert output.getpixel((4,3)) == (40,80,120,160)
        assert tool.display_to_original(100,400,1600) == 400
        assert tool.split_groups(images,crops,20) == [[0],[1]]
        root = tool.tk.Tk()
        root.withdraw()
        app = tool.App(root)
        app.install(['A.png','B.png'],images,crops)
        app.mask_button.invoke()
        assert app.mask_mode()
        app.crop_button.invoke()
        assert not app.mask_mode()
        root.update()
        app.views[1].remove_button.invoke()
        assert len(app.images) == 1
        root.destroy()
        report.write_text(json.dumps(dict(ok=True,checks=['bundled Pillow','pixel assembly','opaque masks','coordinates','split groups','bundled Tcl/Tk GUI','mode buttons','image removal'])),encoding='utf-8')
    except Exception:
        import traceback
        report.write_text(traceback.format_exc(),encoding='utf-8')
        sys.exit(1)
else:
    root = tool.tk.Tk()
    app = tool.App(root)
    app.build_label.config(text='Manual Screenshot Stitcher 1.0.2 | Standalone Windows app')
    root.mainloop()
