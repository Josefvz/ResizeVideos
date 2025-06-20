# Video Processing App: Requirements & Implementation Plan

## Requirements
- **Python** (for scripting)
- **ffmpeg** (with CUDA support, installed and in PATH)
- **Directory** to scan for video files (e.g., `.mp4` files)
- **JSON file** to log processing results

## Steps
1. **Scan a directory** for video files (e.g., `.mp4`).
2. For each file:
   - Run the ffmpeg command to create a processed output.
   - Check if the output file is smaller than the input.
   - Log the filename, processed status, and size difference to a JSON file.

## Implementation Plan
- Use Python's `os`, `subprocess`, and `json` modules.
- Store logs in a file like `process_log.json`.
- Make the script re-runnable: skip files already processed.

## Open Questions
- Should the script process only `.mp4` files or other formats as well?
- Should the directory be specified via command line or hardcoded?

## Updates
- The script will support all common video file types (e.g., `.mp4`, `.mkv`, `.avi`, `.mov`, etc.).
- The directory to scan will be provided as a command-line argument.

## Additional Feature Ideas

- **Parallel Processing:** Speed up processing by running multiple ffmpeg jobs in parallel.
- **Custom Output Directory:** Allow specifying an output directory to keep originals and processed files separate.
- **File Extension Filtering:** Allow filtering by extension (e.g., --ext .mp4,.mkv).
- **Dry Run Mode:** Add a --dry-run option to show what would be processed/skipped/deleted without making changes.
- **Logging Improvements:** Add a log file for errors/warnings or support for more verbose/quiet output modes.
- **Progress Bar:** Show a progress bar for user feedback on large batches.
- **Config File Support:** Allow specifying options in a config file (YAML/JSON).
- **Post-Processing Actions:** Add hooks for post-processing, such as moving, renaming, or uploading processed files.
- **More Flexible ffmpeg Templates:** Allow users to specify a custom ffmpeg command template via a config or argument.
- **Cross-Platform Path Handling:** Ensure all path handling is robust for both Windows and Unix-like systems. 