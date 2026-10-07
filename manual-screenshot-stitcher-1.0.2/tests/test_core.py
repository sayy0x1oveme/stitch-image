import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import manual_stitch as tool


class CoreTests(unittest.TestCase):
    def test_coordinates(self):
        for height in (1001, 2316, 2317):
            for scale in (.25, .5, .75, 1.0):
                displayed = round(height * scale)
                for y in range(height + 1):
                    self.assertEqual(tool.display_to_original(y*displayed/height, displayed, height), y)
        with self.assertRaises(ValueError):
            tool.display_to_original(-1, 100, 400)

    def test_pixels_masks_and_splits(self):
        images = [Image.new('RGBA', (8, 12), (30+i*50, 60, 90, 120)) for i in range(3)]
        crops = [dict(start_y=2, end_y=10, masks=[]) for _ in images]
        crops[1]['masks'] = [dict(x1=1, y1=1, x2=4, y2=5)]
        before = [im.tobytes() for im in images]
        output = tool.assemble(images, crops)
        self.assertEqual(output.size, (8, 24))
        self.assertEqual(output.getpixel((1, 8)), (255, 255, 255, 255))
        self.assertEqual(output.getpixel((1, 11)), (80, 60, 90, 120))
        self.assertEqual(output.getpixel((4, 8)), (80, 60, 90, 120))
        self.assertEqual([im.tobytes() for im in images], before)
        groups = tool.split_groups(images, crops, 10)
        self.assertEqual(groups, [[0], [1], [2]])
        parts = [tool.assemble([images[i] for i in g], [crops[i] for i in g]) for g in groups]
        self.assertEqual(b''.join(im.tobytes() for im in parts), output.tobytes())

    def test_validation(self):
        image = Image.new('RGB', (8, 12))
        for start, end in ((5, 5), (8, 3), (-1, 10), (0, 13)):
            with self.assertRaises(ValueError):
                tool.intervals([image], [dict(start_y=start, end_y=end)])
        with self.assertRaises(ValueError):
            tool.intervals([image, Image.new('RGB', (9, 12))],
                           [dict(start_y=0, end_y=12)]*2)

    def test_project_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder)/'source.png'
            image = Image.new('RGB', (8, 12))
            image.save(image_path)
            crops = [dict(start_y=2, end_y=10, masks=[dict(x1=1,y1=3,x2=4,y2=6)])]
            data = tool.project_data([str(image_path)], [image], crops)
            project = Path(folder)/'project.json'
            project.write_text(json.dumps(data), encoding='utf-8')
            paths, images, reopened = tool.read_project(project)
            self.assertEqual(reopened, crops)
            self.assertEqual(images[0].size, image.size)
            self.assertEqual(Path(paths[0]), image_path)


if __name__ == '__main__':
    unittest.main()
