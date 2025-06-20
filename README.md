# AI USAGE
This is my first try at "vibe" coding.
I used Cursor.Ai and this entire project took 02 Hours 03 Minutes from start to the last commit.

# Video Processing App

This app scans a directory for video files, processes each file with a GPU-accelerated or CPU-based ffmpeg command to create a 1080p HEVC version, and logs the results to a JSON file. It only processes files that haven't been processed before, and records the size difference between the original and processed files.

## Features
- Supports all common video file types (`.mp4`, `.mkv`, `.avi`, `.mov`, `.flv`, `.wmv`, `.webm`, `.mpeg`, `.mpg`, `.m4v`)
- Uses ffmpeg with CUDA hardware acceleration (default) or CPU-based x265 encoding
- Skips files already processed (by filename or content hash)
- Logs results to `process_log.json`
- Provides summary statistics after processing
- Supports input file deletion after successful processing

## Requirements
- Python 3.7+
- ffmpeg (with CUDA support for GPU encoding, or libx265 for CPU encoding)

## Installation
No special installation is required. Just ensure you have Python and ffmpeg installed.

## Usage
```
python process_videos.py <path> [--delete-input] [--encoder {cuda,x265}] [--force-rerun] [--no-recursive]
```
- `<path>`: Path to a directory containing video files (will scan all subfolders) or a single video file to process.
- `--delete-input`: (Optional) If provided, the script will delete the input file after successful processing and only if the output file is smaller.
- `--encoder`: (Optional) Choose the ffmpeg encoder:
  - `cuda` (default): GPU-accelerated encoding using NVIDIA hardware
  - `x265`: CPU-based encoding using libx265
- `--force-rerun`: (Optional) Force processing even if the file was already processed before. This bypasses the hash-based rerun protection.
- `--no-recursive`: (Optional) Process only the specified directory, not subdirectories. By default, the script processes all subdirectories recursively. (Ignored when processing a single file)

## Log File
- `process_log.json` will be created/updated in the script's directory.
- Each entry contains:
  - `processed`: Whether the file was successfully processed and the output is smaller
  - `input_size`: Size of the original file (bytes)
  - `output_size`: Size of the processed file (bytes)
  - `size_difference`: Number of bytes saved
  - `output_file`: Path to the output file (if processing was successful)
  - `input_hash`: SHA256 hash of the input file content

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
python process_videos.py D:/Videos --encoder x265 --delete-input

# Process single files
python process_videos.py D:/Videos/movie.mp4
python process_videos.py D:/Videos/movie.mp4 --encoder x265
python process_videos.py D:/Videos/movie.mp4 --force-rerun --delete-input

# Force rerun (process all files regardless of previous processing)
python process_videos.py D:/Videos --force-rerun
python process_videos.py D:/Videos --encoder x265 --force-rerun --delete-input

# Process only the specified directory (no subdirectories)
python process_videos.py D:/Videos --no-recursive
python process_videos.py D:/Videos --encoder x265 --no-recursive
```

## Output Files
- GPU encoding: `*_1080p_web_gpu.mp4`
- CPU encoding: `*_1080p_web.mp4`

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
