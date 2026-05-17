# Video Integration HOWTO

## Overview

This document describes how to map StatsBomb event data to broadcast video timestamps, extract tactical clips, and sync them with analytical outputs. This is essential for presenting insights to coaching staff who rely on visual evidence.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  StatsBomb      │     │  Video Source     │     │  Output        │
│  Events DB      │────▶│  (MP4/Broadcast)  │────▶│  Clips + Report│
│  (timestamps)   │     │  (sync offset)    │     │  (tagged)      │
└─────────────────┘     └──────────────────┘     └────────────────┘
```

## Step 1: Obtain Match Video

StatsBomb event data uses match-clock timestamps (period + minute:second). To create clips, you need:

- **Broadcast footage** (obtained via club agreements or official broadcast recording)
- **OR** tactical camera footage (wide-angle, available to professional clubs)

**Important**: This project does NOT include or distribute any video files. Clubs must provide their own footage under appropriate licensing.

## Step 2: Synchronise Event Timestamps with Video

### The Offset Problem

StatsBomb timestamps are in match-clock time (e.g., `23:15` = 23 minutes, 15 seconds of play). Broadcast video has a different timeline due to:
- Pre-match coverage and build-up
- Stoppages not reflected in match clock
- Half-time break
- Replay cuts

### Calibration Method

1. **Identify anchor events** — Find 2-3 clearly visible events in both data and video:
   - Kick-off (Period 1, `00:00:00`)
   - A goal (exact timestamp in data, visible in video)
   - Second-half kick-off (Period 2, `45:00:00`)

2. **Calculate offset per period**:
   ```python
   # Example calibration
   offsets = {
       1: timedelta(minutes=5, seconds=32),   # Broadcast starts 5:32 before kick-off
       2: timedelta(minutes=52, seconds=18),   # Half-time adds ~7 min
   }
   ```

3. **Apply offset to all events**:
   ```python
   def event_to_video_timestamp(event_period: int, event_time: str, offsets: dict) -> float:
       """Convert StatsBomb event time to video timestamp in seconds.
       
       Args:
           event_period: 1 or 2 (or 3/4 for extra time)
           event_time: "MM:SS.mmm" format from StatsBomb
           offsets: Dict mapping period -> timedelta offset from video start
       
       Returns:
           Seconds from video start.
       """
       parts = event_time.split(":")
       minutes = int(parts[0])
       seconds = float(parts[1])
       
       match_seconds = minutes * 60 + seconds
       video_offset = offsets[event_period].total_seconds()
       
       return match_seconds + video_offset
   ```

## Step 3: Define Clip Extraction Rules

### Clip Windows

For different event types, use appropriate time windows around the event:

| Event Type | Pre-event Buffer | Post-event Buffer | Typical Duration |
|-----------|-----------------|------------------|-----------------|
| Shot | 8s | 3s | ~11s |
| Goal | 10s | 5s | ~15s |
| Pressing sequence | 5s | 2s | ~7s |
| Possession chain | Start of possession | End of possession | Variable |
| Set piece | 5s | 8s | ~13s |

### Code Example: Clip Extraction with FFmpeg

```python
import subprocess
from pathlib import Path


def extract_clip(
    video_path: Path,
    start_seconds: float,
    duration: float,
    output_path: Path,
    label: str = "",
) -> Path:
    """Extract a clip from video using FFmpeg.
    
    Args:
        video_path: Source video file.
        start_seconds: Start time in seconds.
        duration: Clip duration in seconds.
        output_path: Where to save the clip.
        label: Optional text overlay for context.
    
    Returns:
        Path to the extracted clip.
    
    Performance: Uses -ss before -i for fast seeking (input seeking).
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_seconds),   # Seek before input = fast
        "-i", str(video_path),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        str(output_path),
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def batch_extract_clips(
    video_path: Path,
    events_df: "pd.DataFrame",
    offsets: dict,
    output_dir: Path,
    pre_buffer: float = 8.0,
    post_buffer: float = 3.0,
) -> list[Path]:
    """Extract clips for a set of events.
    
    Args:
        events_df: Must contain columns: period, timestamp, event_type, player_name
        offsets: Period -> offset mapping from calibration
        output_dir: Directory for output clips
    
    Returns:
        List of paths to extracted clips.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    
    for idx, event in events_df.iterrows():
        video_time = event_to_video_timestamp(
            event["period"], event["timestamp"], offsets
        )
        start = max(0, video_time - pre_buffer)
        duration = pre_buffer + post_buffer
        
        filename = f"{event['minute']:02d}m_{event['event_type']}_{event.get('player_name', 'unknown')}.mp4"
        # Sanitise filename
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        
        output_path = output_dir / filename
        extract_clip(video_path, start, duration, output_path)
        clips.append(output_path)
    
    return clips
```

## Step 4: Tag Clips with Analytical Context

Each clip should be accompanied by metadata for coaching presentations:

```python
def generate_clip_metadata(event_row: "pd.Series", analysis_context: dict) -> dict:
    """Generate metadata card for a tactical clip.
    
    Returns a dict suitable for JSON export or dashboard display.
    """
    return {
        "event_type": event_row["event_type"],
        "player": event_row.get("player_name", "Unknown"),
        "minute": event_row["minute"],
        "team": event_row.get("team_name", "Unknown"),
        "xg": event_row.get("xg"),
        "tactical_note": analysis_context.get("note", ""),
        "tags": analysis_context.get("tags", []),
        # Example tags: ["counter-attack", "high-press-trigger", "overload-left"]
    }
```

## Step 5: Presentation Workflow

### For Coaching Staff (Non-Technical)

1. Run analysis in notebook/dashboard → identify key moments
2. Export event list as CSV with video timestamps
3. Use batch extraction to create a "highlight package"
4. Embed clips in PowerPoint or present via dashboard

### Dashboard Integration

The dashboard can link events to clips:

```python
# In Dash callback — when user clicks an event row:
@callback(Output("video-player", "src"), Input("events-table", "active_cell"))
def play_event_clip(active_cell):
    """Load the corresponding clip when an event is selected."""
    if active_cell is None:
        return ""
    event_id = get_event_id_from_cell(active_cell)
    clip_path = CLIPS_DIR / f"{event_id}.mp4"
    if clip_path.exists():
        return str(clip_path)
    return ""
```

## Step 6: Automation Pipeline

For recurring match analysis (e.g., weekly opposition reports):

```bash
#!/bin/bash
# post_match_pipeline.sh

MATCH_ID=$1
VIDEO_PATH=$2

# 1. Ingest match data
uv run fb-ingest --competition-id 43 --season-id 106 --max-matches 1

# 2. Run analysis and export key events
uv run python -m football_analytics.analysis.export_events --match-id $MATCH_ID --output events.csv

# 3. Calibrate video (manual step — or use pre-saved offsets)
# 4. Extract clips
uv run python -m football_analytics.video.extract --events events.csv --video $VIDEO_PATH --output clips/

# 5. Generate report
uv run python -m football_analytics.reports.match_report --match-id $MATCH_ID
```

## Requirements

- **FFmpeg** >= 5.0 (for clip extraction)
- **Video source** provided separately (not included in this repo)
- **Calibration** is a one-time manual step per match

## Limitations

- Timestamp sync accuracy depends on calibration quality (~1-2s typical error)
- Extra-time periods require additional offset calibration
- No automated scene detection — relies on StatsBomb timestamp accuracy
- Video files must be obtained legally through appropriate agreements

---

## Further Reading

- [StatsBomb Data Specification](https://github.com/statsbomb/open-data/tree/master/doc)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [mplsoccer event synchronisation examples](https://mplsoccer.readthedocs.io/)
