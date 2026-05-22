#!/usr/bin/env python3
"""
Validators - Check if GIFs meet Slack's requirements.
v2: Adds Slack file-size limits, fps range checks, and a repair() helper.
"""

from pathlib import Path


# Slack's actual upload limits
SLACK_EMOJI_MAX_KB = 512        # 512 KB for custom emoji
SLACK_MESSAGE_MAX_MB = 50       # 50 MB for message GIFs (practical limit)
SLACK_EMOJI_MAX_FRAMES = 500    # practical upper bound before Slack slows down


def validate_gif(
    gif_path, is_emoji: bool = True, verbose: bool = True
) -> tuple[bool, dict]:
    """
    Validate GIF for Slack (dimensions, file size, frame count, fps).

    Args:
        gif_path: Path to GIF file
        is_emoji: True for emoji (128x128 recommended), False for message GIF
        verbose: Print validation details

    Returns:
        Tuple of (passes: bool, results: dict with all details)
    """
    from PIL import Image

    gif_path = Path(gif_path)

    if not gif_path.exists():
        return False, {"error": f"File not found: {gif_path}"}

    size_bytes = gif_path.stat().st_size
    size_kb = size_bytes / 1024
    size_mb = size_kb / 1024

    try:
        with Image.open(gif_path) as img:
            width, height = img.size

            frame_count = 0
            try:
                while True:
                    img.seek(frame_count)
                    frame_count += 1
            except EOFError:
                pass

            try:
                duration_ms = img.info.get("duration", 100)
                total_duration = (duration_ms * frame_count) / 1000
                fps = frame_count / total_duration if total_duration > 0 else 0
            except Exception:
                total_duration = None
                fps = None

    except Exception as e:
        return False, {"error": f"Failed to read GIF: {e}"}

    # ── Dimension check ──────────────────────────────────────────────────────
    if is_emoji:
        optimal = width == height == 128
        acceptable = width == height and 64 <= width <= 128
        dim_pass = acceptable
    else:
        aspect_ratio = (
            max(width, height) / min(width, height)
            if min(width, height) > 0
            else float("inf")
        )
        dim_pass = aspect_ratio <= 2.0 and 320 <= min(width, height) <= 640

    # ── File size check ──────────────────────────────────────────────────────
    if is_emoji:
        size_pass = size_kb <= SLACK_EMOJI_MAX_KB
    else:
        size_pass = size_mb <= SLACK_MESSAGE_MAX_MB

    # ── FPS check ────────────────────────────────────────────────────────────
    fps_pass = fps is None or (10 <= fps <= 30)

    # ── Frame count check ────────────────────────────────────────────────────
    frames_pass = frame_count <= SLACK_EMOJI_MAX_FRAMES

    overall_pass = dim_pass and size_pass and fps_pass and frames_pass

    results = {
        "file": str(gif_path),
        "passes": overall_pass,
        "dim_pass": dim_pass,
        "size_pass": size_pass,
        "fps_pass": fps_pass,
        "frames_pass": frames_pass,
        "width": width,
        "height": height,
        "size_kb": size_kb,
        "size_mb": size_mb,
        "frame_count": frame_count,
        "duration_seconds": total_duration,
        "fps": fps,
        "is_emoji": is_emoji,
        "optimal": optimal if is_emoji else None,
    }

    if verbose:
        status = "✓ PASS" if overall_pass else "✗ FAIL"
        print(f"\n{status} — Validating {gif_path.name}:")

        dim_icon = "✓" if dim_pass else "✗"
        size_icon = "✓" if size_pass else "✗"
        fps_icon = "✓" if fps_pass else "✗"

        if is_emoji:
            print(f"  {dim_icon} Dimensions: {width}x{height} {'(optimal)' if optimal else '(acceptable)' if dim_pass else '(needs 64–128 square)'}")
            print(f"  {size_icon} File size:  {size_kb:.1f} KB / {SLACK_EMOJI_MAX_KB} KB limit")
        else:
            print(f"  {dim_icon} Dimensions: {width}x{height} {'(ok)' if dim_pass else '(unusual for Slack)'}")
            print(f"  {size_icon} File size:  {size_mb:.2f} MB / {SLACK_MESSAGE_MAX_MB} MB limit")

        if fps is not None:
            print(f"  {fps_icon} FPS:        {fps:.1f} {'(ok)' if fps_pass else '(recommend 10–30)'}")
        print(f"     Frames:     {frame_count} ({total_duration:.1f}s)" if total_duration else f"     Frames:     {frame_count}")

        if not overall_pass:
            print(f"\n  Suggestions:")
            if not size_pass:
                print(f"    → Reduce colors (num_colors=48) or frames to shrink file size")
            if not dim_pass:
                print(f"    → Resize to 128x128 with optimize_for_emoji=True")
            if not fps_pass:
                print(f"    → Adjust fps to be between 10 and 30")

    return overall_pass, results


def is_slack_ready(gif_path, is_emoji: bool = True, verbose: bool = True) -> bool:
    """
    Quick check if GIF is ready for Slack.

    Returns:
        True if all checks pass
    """
    passes, _ = validate_gif(gif_path, is_emoji, verbose)
    return passes


def get_repair_suggestions(gif_path, is_emoji: bool = True) -> list[str]:
    """
    Return a list of actionable fix suggestions for a GIF that fails validation.

    Args:
        gif_path: Path to the GIF
        is_emoji: Whether this is intended as an emoji

    Returns:
        List of human-readable suggestion strings
    """
    _, results = validate_gif(gif_path, is_emoji=is_emoji, verbose=False)

    if "error" in results:
        return [f"Could not read file: {results['error']}"]

    suggestions = []

    if not results["dim_pass"]:
        suggestions.append("Resize to 128x128: use optimize_for_emoji=True in builder.save()")

    if not results["size_pass"]:
        if is_emoji:
            suggestions.append(
                f"File is {results['size_kb']:.0f} KB — reduce with: "
                f"num_colors=48, remove_duplicates=True, or fewer frames"
            )
        else:
            suggestions.append(f"File is {results['size_mb']:.1f} MB — reduce frame count or dimensions")

    if not results["fps_pass"]:
        suggestions.append(f"FPS is {results['fps']:.1f} — set builder fps between 10 and 30")

    if not results["frames_pass"]:
        suggestions.append(f"Too many frames ({results['frame_count']}) — reduce animation length")

    if not suggestions:
        suggestions.append("GIF looks good — no fixes needed!")

    return suggestions
