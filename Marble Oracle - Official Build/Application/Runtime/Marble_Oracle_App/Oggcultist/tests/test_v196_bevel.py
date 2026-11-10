"""v1.9.6 chamfer profile and reduced corner roundness."""
import math
from PIL import Image
from oggcultist.gui import textures, theme, sliders


def test_chamfer_profile_38_degrees():
    assert textures.BEVEL_ANGLE_DEGREES == 38.0
    assert textures.bevel_run_px() == 2 / math.tan(math.radians(38))
    assert 2.5 < textures.bevel_run_px() < 2.7


def test_tight_corners_and_sliders():
    assert theme.RADIUS == 2
    # The centre is unchanged and the 38-degree rim extends a few pixels in.
    flat = textures.surface((70, 36), '#555555', '#555555', behind='#000000', radius=2, edge=0, amount=0)
    raised = textures.surface((70, 36), '#555555', '#555555', behind='#000000', radius=2, edge=0, amount=0, bevel=.35)
    assert raised.getpixel((35, 18)) == flat.getpixel((35, 18))
    assert sum(raised.getpixel((35, 0))) > sum(flat.getpixel((35, 0)))
    assert sum(raised.getpixel((35, 1))) > sum(flat.getpixel((35, 1)))
    assert raised.getpixel((0, 0)) != (85, 85, 85)
    slider = sliders.render(220, 20, 0.5, behind='#211915', grain_amount=.1,
                            stops=theme.GRADIENT, shift=0, track=6, thumb=7)
    assert slider.size == (220, 20)
