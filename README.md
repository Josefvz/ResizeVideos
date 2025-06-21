# AI USAGE
This is my first try at "vibe" coding.
I used Cursor.Ai and this entire project took 02 Hours 03 Minutes from start to the last commit.

# Video Processing App

This app scans a directory for video files, processes each file with a GPU-accelerated or CPU-based ffmpeg command to create a 1080p HEVC version, and logs the results to a JSON file. It only processes files that haven't been processed before, and records the size difference between the original and processed files.

## Features
- Supports all common video file types (`.mp4`, `.mkv`, `.avi`, `.mov`, `.flv`, `.wmv`, `.webm`, `.mpeg`, `.mpg`, `.m4v`)
- Uses ffmpeg with CUDA hardware acceleration (default) or CPU-based x265 encoding
- **Smart aspect ratio handling** for non-1080p compatible videos (mobile videos, etc.)
- **Comprehensive logging system** with multiple log files and verbosity levels
- **Progress bar** for visual feedback on large batch processing
- **Cross-platform path handling** for robust operation on Windows, macOS, and Linux
- **Graceful interruption** support for safe stopping with Ctrl+C
- Skips files already processed (by filename or content hash)
- Logs results to `process_log.json`
- Provides summary statistics after processing
- Supports input file deletion after successful processing

## Requirements
- Python 3.7+
- ffmpeg (with CUDA support for GPU encoding, or libx265 for CPU encoding)
- **Optional**: `tqdm` package for progress bar functionality (`pip install tqdm`)

## Installation
No special installation is required. Just ensure you have Python and ffmpeg installed.

## Usage
```
python process_videos.py <path> [--delete-input] [--encoder {cuda,x265,smart}] [--force-rerun] [--no-recursive] [--verbose] [--quiet] [--no-progress]
```
- `<path>`: Path to a directory containing video files (will scan all subfolders) or a single video file to process.
- `--delete-input`: (Optional) If provided, the script will delete the input file after successful processing and only if the output file is smaller.
- `--encoder`: (Optional) Choose the ffmpeg encoder:
  - `cuda` (default): GPU-accelerated encoding using NVIDIA hardware, maintains aspect ratio
  - `x265`: CPU-based encoding using libx265, maintains aspect ratio
  - `smart`: CPU-based encoding with letterboxing/pillarboxing for perfect 1920x1080 output
- `--force-rerun`: (Optional) Force processing even if the file was already processed before. This bypasses the hash-based rerun protection.
- `--no-recursive`: (Optional) Process only the specified directory, not subdirectories. By default, the script processes all subdirectories recursively. (Ignored when processing a single file)
- `--verbose`, `-v`: (Optional) Enable verbose logging with detailed debug information, including ffmpeg commands and detailed processing steps.
- `--quiet`, `-q`: (Optional) Suppress all output except errors and warnings. Useful for automated processing.
- `--no-progress`: (Optional) Disable the progress bar (enabled by default). Use this for automated processing or when you prefer minimal output.

## Log Files
The app creates several log files for different purposes:

### `process_log.json`
- Main processing log with detailed information about each file
- Each entry contains:
  - `processed`: Whether the file was successfully processed and the output is smaller
  - `input_size`: Size of the original file (bytes)
  - `output_size`: Size of the processed file (bytes)
  - `size_difference`: Number of bytes saved
  - `output_file`: Path to the output file (if processing was successful)
  - `input_hash`: SHA256 hash of the input file content
  - `processing_time`: Timestamp when the file was processed

### `processing.log`
- Detailed log file with timestamps and log levels
- Contains all processing information, debug details, and ffmpeg output
- Useful for troubleshooting and monitoring long-running processes

### `error_log.txt`
- Dedicated error and warning log file
- Contains only errors and warnings for quick problem identification
- Useful for monitoring failed processing attempts

## Progress Bar
The app includes a progress bar feature for visual feedback during processing (enabled by default):

### Features:
- **Real-time progress**: Shows current file being processed
- **Completion percentage**: Visual progress indicator
- **Time estimates**: Elapsed time and estimated time remaining
- **Processing rate**: Files processed per second
- **Current file name**: Updates to show which file is currently being processed

### Default Behavior:
- **Progress bar is enabled by default** for all processing operations
- Provides immediate visual feedback on processing status
- Shows completion percentage and time estimates

### Disabling Progress Bar:
- Use `--no-progress` flag to disable the progress bar
- Useful for automated processing or when you prefer minimal output
- Example: `python process_videos.py D:/Videos --no-progress`

### Requirements:
- Install the `tqdm` package: `pip install tqdm`
- If `tqdm` is not installed, the script will continue without the progress bar and show a warning message

### Example Output:
```
Processing: video_001.mp4: 45%|████▌     | 45/100 [02:30<03:05, 3.2files/s]
```

### Installation:
```bash
pip install tqdm
```

## Cross-Platform Compatibility
The app is designed to work seamlessly across different operating systems:

### Supported Platforms:
- **Windows**: Full support for Windows paths, including UNC paths and drive letters
- **macOS**: Native support for Unix-style paths and macOS file system features
- **Linux**: Optimized for Linux file systems and path conventions

### Path Handling Features:
- **Automatic path normalization**: Converts between different path formats
- **Symlink resolution**: Properly handles symbolic links and junction points
- **Relative path support**: Works with relative and absolute paths
- **Unicode support**: Handles international characters in file and directory names
- **Case sensitivity**: Respects platform-specific case sensitivity rules

### Platform Detection:
The app automatically detects and logs the current platform:
```
Platform: Windows 10
Platform: macOS 12.0
Platform: Linux 5.4
```

### Path Examples:
```bash
# Windows paths
python process_videos.py "C:\Users\Username\Videos"
python process_videos.py "\\server\share\videos"

# Unix/Linux/macOS paths
python process_videos.py "/home/username/videos"
python process_videos.py "./videos"

# Mixed paths (automatically normalized)
python process_videos.py "C:/Users/Username/Videos"  # Windows with forward slashes
```

## Graceful Interruption
The app supports graceful interruption, allowing you to safely stop processing at any time:

### Interruption Methods:
- **Ctrl+C** (SIGINT): Most common method
- **Ctrl+Break** (Windows): Alternative Windows interruption
- **SIGTERM**: System termination signal

### How It Works:
1. **Current File Completion**: The currently processing file will complete before stopping
2. **Safe Cleanup**: Progress is saved and log files are properly closed
3. **Clear Feedback**: You'll see a message indicating processing was interrupted
4. **Proper Exit Codes**: Returns appropriate exit codes for automation

### Example Interruption:
```
Processing: video_001.mp4: 45%|████▌     | 45/100 [02:30<03:05, 3.2files/s]
^C
Received interrupt signal (2). Gracefully stopping processing...
Current file will complete, then processing will stop.
Processing: video_001.mp4: 100%|██████████| 45/100 [02:35<00:00, 3.2files/s]
Processing interrupted by user. Stopping gracefully...
Current file completed, but remaining files were skipped.

Processing completed at 2024-01-15 10:30:45
Total execution time: 155.3 seconds (2.6 minutes)
Video files found: 100
Files processed: 45
  Success: 42
  Failed: 3
Files skipped: 55
Processing was interrupted - some files may not have been processed
Total size saved: 2.1 GB
```

### Benefits:
- **No File Corruption**: Current file completes safely
- **Progress Preservation**: Log files are saved with current progress
- **Clear Status**: You know exactly what was processed and what was skipped
- **Automation Friendly**: Proper exit codes for script integration

## Rerun Protection
The script includes robust rerun protection:
- Files are tracked by their content hash, so renamed files are not reprocessed
- Output files from previous runs are automatically skipped
- The log prevents duplicate processing across multiple runs

## Example
```
# Process directories
python process_videos.py D:/Videos
python process_videos.py D:/Videos --delete-input
python process_videos.py D:/Videos --encoder x265
python process_videos.py D:/Videos --encoder smart
python process_videos.py D:/Videos --encoder x265 --delete-input
python process_videos.py D:/Videos --encoder smart --delete-input

# Process with logging options
python process_videos.py D:/Videos --verbose
python process_videos.py D:/Videos --quiet
python process_videos.py D:/Videos --verbose --encoder smart

# Process with progress bar (enabled by default)
python process_videos.py D:/Videos
python process_videos.py D:/Videos --encoder smart
python process_videos.py D:/Videos --delete-input

# Disable progress bar for automated processing
python process_videos.py D:/Videos --no-progress
python process_videos.py D:/Videos --no-progress --quiet

# Process single files
python process_videos.py D:/Videos/movie.mp4
python process_videos.py D:/Videos/movie.mp4 --encoder x265
python process_videos.py D:/Videos/movie.mp4 --encoder smart
python process_videos.py D:/Videos/movie.mp4 --force-rerun --delete-input

# Force rerun (process all files regardless of previous processing)
python process_videos.py D:/Videos --force-rerun
python process_videos.py D:/Videos --encoder x265 --force-rerun --delete-input
python process_videos.py D:/Videos --encoder smart --force-rerun --delete-input

# Process only the specified directory (no subdirectories)
python process_videos.py D:/Videos --no-recursive
python process_videos.py D:/Videos --encoder x265 --no-recursive
python process_videos.py D:/Videos --encoder smart --no-recursive
```

## Output Files
- GPU encoding: `*_1080p_web_gpu.mp4`
- CPU encoding: `*_1080p_web.mp4`
- Smart encoding: `*_1080p_smart.mp4`

## Aspect Ratio Handling
The app now properly handles videos with non-1080p aspect ratios (like mobile videos):

- **cuda/x265 encoders**: Scale to 1080p height while maintaining the original aspect ratio. This means:
  - 16:9 videos become 1920x1080
  - 9:16 (mobile) videos become 608x1080
  - 4:3 videos become 1440x1080
  - Other ratios are scaled proportionally

- **smart encoder**: Creates a perfect 1920x1080 output with letterboxing/pillarboxing:
  - 16:9 videos become 1920x1080 (no black bars)
  - 9:16 (mobile) videos become 1920x1080 with black bars on sides
  - 4:3 videos become 1920x1080 with black bars on sides
  - All outputs are exactly 1920x1080 for consistent playback

**Recommendation**: Use `smart` encoder for videos that need to be exactly 1920x1080, and `cuda`/`x265` for maintaining original aspect ratios.

## Summary Output
After processing, the script displays:
- Files processed (total attempted)
  - Success: number of files successfully processed and smaller
  - Failed: number of files attempted but not marked as processed
- Files skipped
- Total size saved (in readable format)

## Notes
- Only files that result in a smaller output are marked as processed.
- Make sure your ffmpeg build supports the chosen encoder (CUDA for GPU, libx265 for CPU).
- The script uses content-based hashing to prevent reprocessing of renamed files. 
