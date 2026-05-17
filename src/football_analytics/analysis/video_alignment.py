"""Video timestamp alignment — map events to broadcast video timestamps.

Provides tools for synchronising StatsBomb event data with broadcast
video footage for clip generation and coach review workflows.

Features:
- Event-to-timestamp mapping (match clock → video timecode)
- Automatic offset calibration from known events (goals, kick-off)
- Clip window generation (event ± configurable padding)
- Batch clip list export (for FFmpeg or video editing tools)
- SRT subtitle generation from events

Note: Does not handle video processing itself — generates metadata
that can be consumed by FFmpeg, DaVinci Resolve, or similar tools.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VideoConfig:
    """Configuration for video alignment."""

    video_start_offset: float = 0.0  # Seconds from video start to kick-off
    half_time_duration: float = 900.0  # 15 minutes half-time
    extra_time_gap: float = 120.0  # Gap before extra time
    frame_rate: float = 25.0  # Video frame rate (fps)
    pre_event_padding: float = 5.0  # Seconds before event for clip
    post_event_padding: float = 5.0  # Seconds after event for clip


@dataclass
class VideoClip:
    """A video clip definition tied to a match event."""

    event_id: str
    event_type: str
    player_name: str | None
    match_minute: int
    match_second: int
    period: int
    video_start_time: float  # Seconds from video start
    video_end_time: float
    clip_start: float  # With padding
    clip_end: float  # With padding
    label: str  # Human-readable description
    timecode_start: str  # HH:MM:SS.ff format
    timecode_end: str


@dataclass
class AlignmentCalibration:
    """Calibration data for event-video alignment."""

    reference_events: list[dict[str, Any]]  # Known events with video timestamps
    computed_offset: float  # Computed offset (seconds)
    confidence: float  # Calibration confidence (0-1)
    residual_error: float  # Average error after calibration


def match_clock_to_video_time(
    minute: int,
    second: int,
    period: int,
    config: VideoConfig | None = None,
) -> float:
    """Convert match clock time to video timestamp (seconds from video start).

    Accounts for:
    - Video start offset (broadcast starts before kick-off)
    - Half-time break
    - Extra time periods

    Args:
        minute: Match minute (0-based within period, or cumulative).
        second: Second within the minute.
        period: Match period (1=first half, 2=second half, 3/4=extra time).
        config: Video configuration. Uses defaults if None.

    Returns:
        Video timestamp in seconds from start of video file.
    """
    if config is None:
        config = VideoConfig()

    match_seconds = minute * 60 + second

    if period == 1:
        video_time = config.video_start_offset + match_seconds
    elif period == 2:
        # Second half: after first 45min + half-time
        first_half_duration = 45 * 60  # Nominal first half
        video_time = (
            config.video_start_offset
            + first_half_duration
            + config.half_time_duration
            + (match_seconds - first_half_duration)
        )
    elif period == 3:
        # Extra time first half
        normal_time = 90 * 60
        video_time = (
            config.video_start_offset
            + normal_time
            + config.half_time_duration
            + config.extra_time_gap
            + (match_seconds - normal_time)
        )
    elif period == 4:
        # Extra time second half
        normal_time = 105 * 60
        video_time = (
            config.video_start_offset
            + normal_time
            + config.half_time_duration
            + config.extra_time_gap * 2
            + (match_seconds - normal_time)
        )
    else:
        video_time = config.video_start_offset + match_seconds

    return max(0.0, video_time)


def seconds_to_timecode(seconds: float, frame_rate: float = 25.0) -> str:
    """Convert seconds to timecode string (HH:MM:SS.ff).

    Args:
        seconds: Time in seconds.
        frame_rate: Video frame rate for frame calculation.

    Returns:
        Timecode string in HH:MM:SS.ff format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    frames = int((seconds % 1) * frame_rate)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{frames:02d}"


def timecode_to_seconds(timecode: str, frame_rate: float = 25.0) -> float:
    """Convert timecode string to seconds.

    Args:
        timecode: String in HH:MM:SS.ff or HH:MM:SS format.
        frame_rate: Video frame rate.

    Returns:
        Time in seconds.
    """
    parts = timecode.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        if "." in parts[2]:
            sec_parts = parts[2].split(".")
            secs = int(sec_parts[0])
            frames = int(sec_parts[1])
        else:
            secs = int(parts[2])
            frames = 0
    else:
        raise ValueError(f"Invalid timecode format: {timecode}")

    return hours * 3600 + minutes * 60 + secs + frames / frame_rate


def generate_clips_from_events(
    events_df: pd.DataFrame,
    config: VideoConfig | None = None,
    event_types: list[str] | None = None,
    min_xg: float | None = None,
) -> list[VideoClip]:
    """Generate video clip definitions from match events.

    Args:
        events_df: Event DataFrame with standard columns.
        config: Video configuration.
        event_types: Filter to specific event types (e.g., ["Shot", "Goal"]).
        min_xg: Minimum xG for shot events (filter low-quality chances).

    Returns:
        List of VideoClip objects ready for export.
    """
    if config is None:
        config = VideoConfig()

    df = events_df.copy()

    # Apply filters
    if event_types:
        df = df[df["event_type"].isin(event_types)]

    if min_xg is not None and "xg" in df.columns:
        xg_filter = df["xg"].isna() | (df["xg"] >= min_xg)
        df = df[xg_filter]

    clips = []
    for _, row in df.iterrows():
        minute = int(row.get("minute", 0))
        second = int(row.get("second", 0) or 0)
        period = int(row.get("period", 1))

        video_time = match_clock_to_video_time(minute, second, period, config)
        clip_start = max(0.0, video_time - config.pre_event_padding)
        clip_end = video_time + config.post_event_padding

        # Generate label
        player = row.get("player_name", row.get("player", "Unknown"))
        event_type = row.get("event_type", "Event")
        outcome = row.get("shot_outcome", row.get("pass_outcome", ""))
        label = f"{minute}' {player} - {event_type}"
        if outcome:
            label += f" ({outcome})"

        clip = VideoClip(
            event_id=str(row.get("event_id", "")),
            event_type=event_type,
            player_name=str(player) if player else None,
            match_minute=minute,
            match_second=second,
            period=period,
            video_start_time=round(video_time, 2),
            video_end_time=round(video_time + 1.0, 2),
            clip_start=round(clip_start, 2),
            clip_end=round(clip_end, 2),
            label=label,
            timecode_start=seconds_to_timecode(clip_start, config.frame_rate),
            timecode_end=seconds_to_timecode(clip_end, config.frame_rate),
        )
        clips.append(clip)

    logger.info("Generated %d video clips from %d events", len(clips), len(df))
    return clips


def calibrate_alignment(
    reference_points: list[dict[str, Any]],
    config: VideoConfig | None = None,
) -> AlignmentCalibration:
    """Calibrate video-event alignment from known reference points.

    Uses known events (goals, cards) with their actual video timestamps
    to compute the optimal offset.

    Args:
        reference_points: List of dicts with:
            - minute: Match minute of event
            - second: Match second
            - period: Match period
            - video_timestamp: Actual video timestamp (seconds or timecode)

    Returns:
        AlignmentCalibration with computed offset and confidence.
    """
    if config is None:
        config = VideoConfig()

    if not reference_points:
        return AlignmentCalibration(
            reference_events=[], computed_offset=0.0, confidence=0.0, residual_error=0.0
        )

    # Compute offset from each reference point
    offsets = []
    for ref in reference_points:
        predicted = match_clock_to_video_time(
            ref["minute"], ref["second"], ref["period"], config
        )
        actual = ref["video_timestamp"]
        if isinstance(actual, str):
            actual = timecode_to_seconds(actual)
        offsets.append(actual - predicted)

    # Median offset (robust to outliers)
    median_offset = float(pd.Series(offsets).median())

    # Residual error after applying offset
    residuals = [abs(o - median_offset) for o in offsets]
    avg_residual = sum(residuals) / len(residuals) if residuals else 0.0

    # Confidence: inverse of residual error (higher = more consistent)
    confidence = max(0.0, min(1.0, 1.0 - avg_residual / 5.0))

    return AlignmentCalibration(
        reference_events=reference_points,
        computed_offset=round(median_offset, 2),
        confidence=round(confidence, 3),
        residual_error=round(avg_residual, 2),
    )


def export_ffmpeg_clip_list(
    clips: list[VideoClip],
    video_path: str,
    output_dir: str = "clips",
) -> str:
    """Generate a bash script for FFmpeg clip extraction.

    Args:
        clips: List of VideoClip objects.
        video_path: Path to source video file.
        output_dir: Output directory for clips.

    Returns:
        Shell script content as string.
    """
    lines = [
        "#!/bin/bash",
        f"# Auto-generated clip extraction script",
        f"# Source: {video_path}",
        f"# Clips: {len(clips)}",
        "",
        f"mkdir -p {output_dir}",
        "",
    ]

    for i, clip in enumerate(clips, 1):
        duration = clip.clip_end - clip.clip_start
        safe_label = clip.label.replace(" ", "_").replace("'", "").replace("(", "").replace(")", "")
        filename = f"{output_dir}/{i:03d}_{safe_label}.mp4"

        lines.append(f"# Clip {i}: {clip.label}")
        lines.append(
            f'ffmpeg -ss {clip.clip_start:.2f} -i "{video_path}" '
            f'-t {duration:.2f} -c copy "{filename}" -y'
        )
        lines.append("")

    return "\n".join(lines)


def export_srt_subtitles(
    clips: list[VideoClip],
    include_xg: bool = False,
    events_df: pd.DataFrame | None = None,
) -> str:
    """Generate SRT subtitle file from event clips.

    Useful for overlaying event information on video playback.

    Args:
        clips: List of VideoClip objects.
        include_xg: Whether to include xG values in subtitles.
        events_df: Optional event data for additional info.

    Returns:
        SRT-format subtitle string.
    """
    lines = []

    for i, clip in enumerate(clips, 1):
        start_tc = _format_srt_time(clip.video_start_time)
        end_tc = _format_srt_time(clip.video_start_time + 3.0)  # 3-second display

        lines.append(str(i))
        lines.append(f"{start_tc} --> {end_tc}")
        lines.append(clip.label)
        lines.append("")

    return "\n".join(lines)


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_event_timeline(
    events_df: pd.DataFrame,
    config: VideoConfig | None = None,
) -> pd.DataFrame:
    """Generate a full event timeline with video timestamps.

    Useful for creating video chapters or navigation points.

    Args:
        events_df: Event DataFrame.
        config: Video configuration.

    Returns:
        DataFrame with event details and video timestamps.
    """
    if config is None:
        config = VideoConfig()

    records = []
    for _, row in events_df.iterrows():
        minute = int(row.get("minute", 0))
        second = int(row.get("second", 0) or 0)
        period = int(row.get("period", 1))

        video_time = match_clock_to_video_time(minute, second, period, config)

        records.append({
            "event_id": row.get("event_id"),
            "event_type": row.get("event_type"),
            "player_name": row.get("player_name"),
            "team_id": row.get("team_id"),
            "minute": minute,
            "second": second,
            "period": period,
            "video_timestamp_seconds": round(video_time, 2),
            "video_timecode": seconds_to_timecode(video_time, config.frame_rate),
        })

    return pd.DataFrame(records)
