#!/usr/bin/env python3
"""
Frame Composer - Utilities for composing visual elements into frames.

Provides functions for drawing shapes, text, emojis, and compositing elements
together to create animation frames.
"""

from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def create_blank_frame(
    width: int, height: int, color: tuple[int, int, int] = (255, 255, 255)
) -> Image.Image:
    """
    Create a blank frame with solid color background.

    Args:
        width: Frame width
        height: Frame height
        color: RGB color tuple (default: white)

    Returns:
        PIL Image
    """
    return Image.new("RGB", (width, height), color)


def draw_circle(
    frame: Image.Image,
    center: tuple[int, int],
    radius: int,
    fill_color: Optional[tuple[int, int, int]] = None,
    outline_color: Optional[tuple[int, int, int]] = None,
    outline_width: int = 1,
) -> Image.Image:
    """
    Draw a circle on a frame.

    Args:
        frame: PIL Image to draw on
        center: (x, y) center position
        radius: Circle radius
        fill_color: RGB fill color (None for no fill)
        outline_color: RGB outline color (None for no outline)
        outline_width: Outline width in pixels

    Returns:
        Modified frame
    """
    draw = ImageDraw.Draw(frame)
    x, y = center
    bbox = [x - radius, y - radius, x + radius, y + radius]
    draw.ellipse(bbox, fill=fill_color, outline=outline_color, width=outline_width)
    return frame


def draw_text(
    frame: Image.Image,
    text: str,
    position: tuple[int, int],
    color: tuple[int, int, int] = (0, 0, 0),
    centered: bool = False,
) -> Image.Image:
    """
    Draw text on a frame.

    Args:
        frame: PIL Image to draw on
        text: Text to draw
        position: (x, y) position (top-left unless centered=True)
        color: RGB text color
        centered: If True, center text at position

    Returns:
        Modified frame
    """
    draw = ImageDraw.Draw(frame)

    # Uses Pillow's default font.
    # If the font should be changed for the emoji, add additional logic here.
    font = ImageFont.load_default()

    if centered:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = position[0] - text_width // 2
        y = position[1] - text_height // 2
        position = (x, y)

    draw.text(position, text, fill=color, font=font)
    return frame


def create_gradient_background(
    width: int,
    height: int,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> Image.Image:
    """
    Create a vertical gradient background.

    Args:
        width: Frame width
        height: Frame height
        top_color: RGB color at top
        bottom_color: RGB color at bottom

    Returns:
        PIL Image with gradient
    """
    frame = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(frame)

    # Calculate color step for each row
    r1, g1, b1 = top_color
    r2, g2, b2 = bottom_color

    for y in range(height):
        # Interpolate color
        ratio = y / height
        r = int(r1 * (1 - ratio) + r2 * ratio)
        g = int(g1 * (1 - ratio) + g2 * ratio)
        b = int(b1 * (1 - ratio) + b2 * ratio)

        # Draw horizontal line
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return frame


def draw_star(
    frame: Image.Image,
    center: tuple[int, int],
    size: int,
    fill_color: tuple[int, int, int],
    outline_color: Optional[tuple[int, int, int]] = None,
    outline_width: int = 1,
) -> Image.Image:
    """
    Draw a 5-pointed star.

    Args:
        frame: PIL Image to draw on
        center: (x, y) center position
        size: Star size (outer radius)
        fill_color: RGB fill color
        outline_color: RGB outline color (None for no outline)
        outline_width: Outline width

    Returns:
        Modified frame
    """
    import math

    draw = ImageDraw.Draw(frame)
    x, y = center

    # Calculate star points
    points = []
    for i in range(10):
        angle = (i * 36 - 90) * math.pi / 180  # 36 degrees per point, start at top
        radius = size if i % 2 == 0 else size * 0.4  # Alternate between outer and inner
        px = x + radius * math.cos(angle)
        py = y + radius * math.sin(angle)
        points.append((px, py))

    # Draw star
    draw.polygon(points, fill=fill_color, outline=outline_color, width=outline_width)

    return frame


def draw_ring(
    frame: Image.Image,
    center: tuple[int, int],
    radius: int,
    thickness: int,
    color: tuple[int, int, int],
    alpha: int = 255,
) -> Image.Image:
    """
    Draw an outlined circle ring (no fill) — useful for shockwave/ripple effects.

    Args:
        frame: PIL Image to draw on
        center: (x, y) center position
        radius: Ring radius
        thickness: Outline thickness in pixels
        color: RGB color
        alpha: Opacity 0-255

    Returns:
        Modified frame
    """
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y = center
    bbox = [x - radius, y - radius, x + radius, y + radius]
    draw.ellipse(bbox, outline=(*color, alpha), width=thickness)
    frame_rgba = frame.convert("RGBA")
    frame_rgba = Image.alpha_composite(frame_rgba, overlay)
    return frame_rgba.convert("RGB")


def draw_trail(
    frame: Image.Image,
    positions: list[tuple[int, int]],
    radius: int,
    color: tuple[int, int, int],
    max_alpha: int = 120,
) -> Image.Image:
    """
    Draw a fading motion trail behind a moving object.

    Args:
        frame: PIL Image to draw on
        positions: List of (x, y) past positions, oldest first
        radius: Size of each ghost circle
        color: RGB color
        max_alpha: Maximum opacity for the most recent ghost

    Returns:
        Modified frame
    """
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    n = len(positions)
    for i, (x, y) in enumerate(positions):
        alpha = int(max_alpha * (i / n))
        r = max(1, int(radius * (i / n)))
        bbox = [x - r, y - r, x + r, y + r]
        draw.ellipse(bbox, fill=(*color, alpha))
    frame_rgba = frame.convert("RGBA")
    frame_rgba = Image.alpha_composite(frame_rgba, overlay)
    return frame_rgba.convert("RGB")


def apply_glitch(
    frame: Image.Image,
    num_slices: int = 8,
    max_shift: int = 12,
    color_fringe: bool = True,
) -> Image.Image:
    """
    Apply a randomized digital glitch effect to a frame.

    Args:
        frame: PIL Image to distort
        num_slices: Number of horizontal strips to shift
        max_shift: Maximum pixel shift per strip
        color_fringe: If True, also shift the red channel for color aberration

    Returns:
        Glitched PIL Image
    """
    import random

    arr = np.array(frame)
    height = arr.shape[0]
    for _ in range(num_slices):
        y = random.randint(0, height - 8)
        h = random.randint(2, 8)
        shift = random.randint(-max_shift, max_shift)
        arr[y : y + h] = np.roll(arr[y : y + h], shift, axis=1)
    if color_fringe:
        shift = random.randint(-6, 6)
        arr[:, :, 0] = np.roll(arr[:, :, 0], shift, axis=1)  # shift red channel
    return Image.fromarray(arr)


def hue_shift_color(
    base_hue: float,
    frame_index: int,
    total_frames: int,
    saturation: float = 0.9,
    value: float = 1.0,
) -> tuple[int, int, int]:
    """
    Get an RGB color cycling through hues over the animation.

    Args:
        base_hue: Starting hue (0.0–1.0)
        frame_index: Current frame number
        total_frames: Total number of frames
        saturation: HSV saturation (0.0–1.0)
        value: HSV brightness (0.0–1.0)

    Returns:
        RGB color tuple
    """
    import colorsys

    hue = (base_hue + frame_index / total_frames) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (int(r * 255), int(g * 255), int(b * 255))


def create_radial_gradient_background(
    width: int,
    height: int,
    center_color: tuple[int, int, int],
    edge_color: tuple[int, int, int],
) -> Image.Image:
    """
    Create a radial gradient background (center color fades to edge color).

    Args:
        width: Frame width
        height: Frame height
        center_color: RGB color at the center
        edge_color: RGB color at the edges

    Returns:
        PIL Image with radial gradient
    """
    import math

    frame = Image.new("RGB", (width, height))
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = width / 2, height / 2
    max_dist = math.sqrt(cx**2 + cy**2)

    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            t = min(dist / max_dist, 1.0)
            arr[y, x] = [
                int(center_color[c] * (1 - t) + edge_color[c] * t) for c in range(3)
            ]
    return Image.fromarray(arr)
