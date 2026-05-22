#!/usr/bin/env python3
"""
GIF Builder - Core module for assembling frames into GIFs optimized for Slack.
v2: Adds loop control, per-frame duration, add_hold(), pingpong/boomerang,
    and duration-preserving deduplication.
"""

from pathlib import Path
from typing import Optional

import imageio.v3 as imageio
import numpy as np
from PIL import Image


class GIFBuilder:
    """Builder for creating optimized GIFs from frames."""

    def __init__(self, width: int = 480, height: int = 480, fps: int = 15, loop: int = 0):
        """
        Initialize GIF builder.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Frames per second
            loop: Number of times to loop (0 = infinite, 1 = play once, etc.)
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.loop = loop
        self.frames: list[np.ndarray] = []
        self._frame_durations: list[float] = []  # per-frame duration in ms

    def add_frame(self, frame, duration_ms: Optional[float] = None):
        """
        Add a frame to the GIF.

        Args:
            frame: Frame as numpy array or PIL Image
            duration_ms: Optional per-frame duration override in milliseconds.
                         Useful for hold frames or variable-speed animations.
                         If None, uses global fps setting.
        """
        if isinstance(frame, Image.Image):
            frame = np.array(frame.convert("RGB"))

        if frame.shape[:2] != (self.height, self.width):
            pil_frame = Image.fromarray(frame)
            pil_frame = pil_frame.resize((self.width, self.height), Image.Resampling.LANCZOS)
            frame = np.array(pil_frame)

        self.frames.append(frame)
        self._frame_durations.append(duration_ms if duration_ms is not None else 1000 / self.fps)

    def add_frames(self, frames, duration_ms: Optional[float] = None):
        """Add multiple frames at once."""
        for frame in frames:
            self.add_frame(frame, duration_ms=duration_ms)

    def add_hold(self, duration_ms: float = 800):
        """
        Duplicate the last frame as a hold/pause (e.g. pause at end before looping).

        Args:
            duration_ms: How long to hold in milliseconds
        """
        if not self.frames:
            raise ValueError("No frames to hold — add at least one frame first.")
        self.add_frame(self.frames[-1].copy(), duration_ms=duration_ms)

    def reverse_frames(self):
        """
        Append the frames in reverse order (ping-pong / boomerang effect).
        The first and last frames are not duplicated at the join point.
        """
        self.frames = self.frames + self.frames[-2:0:-1]
        self._frame_durations = self._frame_durations + self._frame_durations[-2:0:-1]

    def optimize_colors(self, num_colors: int = 128, use_global_palette: bool = True) -> list:
        """Reduce colors in all frames using quantization."""
        optimized = []

        if use_global_palette and len(self.frames) > 1:
            sample_size = min(5, len(self.frames))
            sample_indices = [int(i * len(self.frames) / sample_size) for i in range(sample_size)]
            sample_frames = [self.frames[i] for i in sample_indices]
            all_pixels = np.vstack([f.reshape(-1, 3) for f in sample_frames])

            total_pixels = len(all_pixels)
            w = min(512, int(np.sqrt(total_pixels)))
            h = (total_pixels + w - 1) // w
            pixels_needed = w * h
            if pixels_needed > total_pixels:
                padding = np.zeros((pixels_needed - total_pixels, 3), dtype=np.uint8)
                all_pixels = np.vstack([all_pixels, padding])

            img_array = all_pixels[:pixels_needed].reshape(h, w, 3).astype(np.uint8)
            combined_img = Image.fromarray(img_array, mode="RGB")
            global_palette = combined_img.quantize(colors=num_colors, method=2)

            for frame in self.frames:
                pil_frame = Image.fromarray(frame)
                quantized = pil_frame.quantize(palette=global_palette, dither=1)
                optimized.append(np.array(quantized.convert("RGB")))
        else:
            for frame in self.frames:
                pil_frame = Image.fromarray(frame)
                quantized = pil_frame.quantize(colors=num_colors, method=2, dither=1)
                optimized.append(np.array(quantized.convert("RGB")))

        return optimized

    def deduplicate_frames(self, threshold: float = 0.9995) -> int:
        """
        Remove duplicate or near-duplicate consecutive frames.
        Duration of removed frames is merged into the preceding frame so
        total animation length is preserved.

        Args:
            threshold: Similarity threshold (0.0-1.0). Higher = more strict.

        Returns:
            Number of frames removed
        """
        if len(self.frames) < 2:
            return 0

        deduplicated = [self.frames[0]]
        dedup_durations = [self._frame_durations[0]]
        removed_count = 0

        for i in range(1, len(self.frames)):
            prev = np.array(deduplicated[-1], dtype=np.float32)
            curr = np.array(self.frames[i], dtype=np.float32)
            similarity = 1.0 - (np.mean(np.abs(prev - curr)) / 255.0)

            if similarity < threshold:
                deduplicated.append(self.frames[i])
                dedup_durations.append(self._frame_durations[i])
            else:
                # Merge duration into previous frame — preserves total length
                dedup_durations[-1] += self._frame_durations[i]
                removed_count += 1

        self.frames = deduplicated
        self._frame_durations = dedup_durations
        return removed_count

    def save(
        self,
        output_path,
        num_colors: int = 128,
        optimize_for_emoji: bool = False,
        remove_duplicates: bool = False,
        pingpong: bool = False,
    ) -> dict:
        """
        Save frames as optimized GIF for Slack.

        Args:
            output_path: Where to save the GIF
            num_colors: Number of colors to use (fewer = smaller file)
            optimize_for_emoji: If True, optimize for emoji size (128x128, fewer colors)
            remove_duplicates: If True, remove duplicate consecutive frames
            pingpong: If True, play forward then backward (boomerang loop)

        Returns:
            Dictionary with file info
        """
        if not self.frames:
            raise ValueError("No frames to save. Add frames with add_frame() first.")

        output_path = Path(output_path)

        if pingpong:
            self.reverse_frames()

        if remove_duplicates:
            removed = self.deduplicate_frames(threshold=0.9995)
            if removed > 0:
                print(f"  Removed {removed} nearly identical frames (duration preserved)")

        if optimize_for_emoji:
            if self.width > 128 or self.height > 128:
                print(f"  Resizing from {self.width}x{self.height} to 128x128 for emoji")
                self.width = 128
                self.height = 128
                resized = []
                for frame in self.frames:
                    pil_frame = Image.fromarray(frame)
                    pil_frame = pil_frame.resize((128, 128), Image.Resampling.LANCZOS)
                    resized.append(np.array(pil_frame))
                self.frames = resized
            num_colors = min(num_colors, 48)

            if len(self.frames) > 12:
                print(f"  Reducing frames from {len(self.frames)} to ~12 for emoji size")
                keep_every = max(1, len(self.frames) // 12)
                self.frames = [self.frames[i] for i in range(0, len(self.frames), keep_every)]
                self._frame_durations = [self._frame_durations[i] for i in range(0, len(self._frame_durations), keep_every)]

        optimized_frames = self.optimize_colors(num_colors, use_global_palette=True)
        durations = self._frame_durations[:len(optimized_frames)]

        imageio.imwrite(
            output_path,
            optimized_frames,
            duration=durations,
            loop=self.loop,
        )

        file_size_kb = output_path.stat().st_size / 1024
        file_size_mb = file_size_kb / 1024
        total_duration = sum(durations) / 1000

        info = {
            "path": str(output_path),
            "size_kb": file_size_kb,
            "size_mb": file_size_mb,
            "dimensions": f"{self.width}x{self.height}",
            "frame_count": len(optimized_frames),
            "fps": self.fps,
            "duration_seconds": total_duration,
            "colors": num_colors,
            "loop": self.loop,
        }

        print(f"\n✓ GIF created successfully!")
        print(f"  Path: {output_path}")
        print(f"  Size: {file_size_kb:.1f} KB ({file_size_mb:.2f} MB)")
        print(f"  Dimensions: {self.width}x{self.height}")
        print(f"  Frames: {len(optimized_frames)} @ {self.fps} fps")
        print(f"  Duration: {total_duration:.1f}s | Loop: {'infinite' if self.loop == 0 else f'{self.loop}x'}")
        print(f"  Colors: {num_colors}")

        if optimize_for_emoji:
            print(f"  Optimized for emoji (128x128, reduced colors)")
        if file_size_mb > 1.0:
            print(f"\n  ⚠ Large file ({file_size_kb:.1f} KB) — consider fewer frames or colors")

        return info

    def clear(self):
        """Clear all frames."""
        self.frames = []
        self._frame_durations = []
