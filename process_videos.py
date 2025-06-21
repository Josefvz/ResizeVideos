import os
import sys
import json
import subprocess
from pathlib import Path
import argparse
import hashlib
import logging
from datetime import datetime
import time
import platform
import signal
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Global flag for graceful shutdown
interrupt_requested = False

# List of common video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.mpeg', '.mpg', '.m4v']

LOG_FILE = 'process_log.json'
ERROR_LOG_FILE = 'error_log.txt'
OUTPUT_SUFFIX = '_1080p_web_gpu.mp4'

FFMPEG_CMD_TEMPLATES = {
    'cuda': [
        'ffmpeg', '-y', '-vsync', '0', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
        '-i', '{input}', '-vf', 'scale_cuda=-2:1080',
        '-c:v', 'hevc_nvenc', '-preset', 'p4', '-rc', 'vbr_hq', '-cq', '24', '-b:v', '0',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '{output}'
    ],
    'x265': [
        'ffmpeg', '-y', '-i', '{input}', '-vf', 'scale=-2:1080',
        '-c:v', 'libx265', '-preset', 'medium', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '{output}'
    ],
    'smart': [
        'ffmpeg', '-y', '-i', '{input}', 
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx265', '-preset', 'medium', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '{output}'
    ]
}

# Cross-platform path handling utilities
def normalize_path(path_str):
    """Normalize path for cross-platform compatibility."""
    if not path_str:
        return None
    # Convert to Path object and resolve to handle symlinks and relative paths
    path = Path(path_str).resolve()
    return str(path)

def ensure_path_exists(path_str):
    """Ensure path exists and return normalized path."""
    if not path_str:
        return None
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path_str}")
    return str(path.resolve())

def get_relative_path(path, base_dir):
    """Get relative path in a cross-platform way."""
    try:
        path_obj = Path(path).resolve()
        base_obj = Path(base_dir).resolve()
        return str(path_obj.relative_to(base_obj))
    except ValueError:
        # If path is not relative to base_dir, return the full path
        return str(path_obj)

def is_same_file(path1, path2):
    """Check if two paths point to the same file (handles symlinks)."""
    try:
        return Path(path1).resolve() == Path(path2).resolve()
    except (OSError, ValueError):
        return False

def setup_logging(verbose=False, quiet=False):
    """Setup logging configuration with appropriate verbosity levels."""
    # Determine log level based on verbosity
    if quiet:
        log_level = logging.WARNING
        console_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
        console_level = logging.DEBUG
    else:
        log_level = logging.INFO
        console_level = logging.INFO
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter('%(message)s')
    
    # Configure root logger
    logging.basicConfig(level=log_level, format='%(message)s')
    logger = logging.getLogger()
    logger.handlers.clear()  # Clear any existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler for all logs - use cross-platform path
    log_file_path = Path('processing.log')
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Error file handler - use cross-platform path
    error_log_path = Path(ERROR_LOG_FILE)
    error_handler = logging.FileHandler(error_log_path, mode='w', encoding='utf-8')
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    return logger

def format_size(size):
    if size is None:
        return 'N/A'
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def load_log():
    log_path = Path(LOG_FILE)
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
                logging.debug(f"Loaded existing log file with {len(log_data)} entries")
                return log_data
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Failed to load existing log file: {e}. Starting with empty log.")
            return {}
    else:
        logging.debug("No existing log file found. Starting with empty log.")
        return {}

def save_log(log):
    try:
        log_path = Path(LOG_FILE)
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2)
        logging.debug(f"Saved log file with {len(log)} entries")
    except IOError as e:
        logging.error(f"Failed to save log file: {e}")

def is_video_file(filename):
    return any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

def count_video_files(directory, is_single_file=False, path=None, no_recursive=False):
    """Count total video files to be processed for progress bar."""
    if is_single_file:
        return 1 if path and is_video_file(Path(path).name) else 0
    
    count = 0
    directory_path = Path(directory)
    for root, _, files in os.walk(directory_path):
        if no_recursive and Path(root) != directory_path:
            continue
        for file in files:
            if is_video_file(file):
                count += 1
    return count

def process_video(input_path, output_path, encoder):
    cmd_template = FFMPEG_CMD_TEMPLATES[encoder]
    cmd = [arg.format(input=input_path, output=output_path) for arg in cmd_template]
    
    logging.debug(f"Running ffmpeg command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.debug(f"ffmpeg completed successfully for {input_path}")
        if result.stderr:
            logging.debug(f"ffmpeg stderr output: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg failed for {input_path}: {e}")
        if e.stdout:
            logging.debug(f"ffmpeg stdout: {e.stdout}")
        if e.stderr:
            logging.error(f"ffmpeg stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"ffmpeg not found in PATH. Please ensure ffmpeg is installed and accessible.")
        return False
    except Exception as e:
        logging.error(f"Unexpected error processing {input_path}: {e}")
        return False

def file_hash(path):
    """Compute SHA256 hash of a file's content."""
    try:
        path_obj = Path(path)
        hash_sha256 = hashlib.sha256()
        with open(path_obj, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_sha256.update(chunk)
        logging.debug(f"Computed hash for {path}")
        return hash_sha256.hexdigest()
    except Exception as e:
        logging.error(f"Failed to compute hash for {path}: {e}")
        return None

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global interrupt_requested
    interrupt_requested = True
    logging.info(f"\nReceived interrupt signal ({signum}). Gracefully stopping processing...")
    logging.info("Current file will complete, then processing will stop.")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    try:
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
        if hasattr(signal, 'SIGBREAK'):  # Windows Ctrl+Break
            signal.signal(signal.SIGBREAK, signal_handler)
    except (OSError, ValueError) as e:
        logging.warning(f"Could not setup signal handlers: {e}")

def cleanup_on_exit(pbar=None, log=None):
    """Cleanup resources on exit."""
    if pbar:
        pbar.close()
    if log:
        try:
            save_log(log)
            logging.info("Log file saved before exit.")
        except Exception as e:
            logging.error(f"Failed to save log on exit: {e}")

def main():
    parser = argparse.ArgumentParser(description="Process videos in a directory with ffmpeg and log results.")
    parser.add_argument('path', help='Directory to scan for video files or single video file to process')
    parser.add_argument('--delete-input', action='store_true', help='Delete input file if output is smaller')
    parser.add_argument('--encoder', choices=['cuda', 'x265', 'smart'], default='cuda', help='Choose ffmpeg encoder: cuda (GPU, default), x265 (CPU), or smart (smart aspect ratio handling)')
    parser.add_argument('--force-rerun', action='store_true', help='Force processing even if file was already processed before')
    parser.add_argument('--no-recursive', action='store_true', help='Process only the specified directory, not subdirectories (ignored when processing a single file)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging with detailed debug information')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress all output except errors and warnings')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bar (enabled by default)')
    args = parser.parse_args()

    # Setup logging based on verbosity
    logger = setup_logging(verbose=args.verbose, quiet=args.quiet)
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Track total execution time
    total_start_time = time.time()
    
    # Progress bar is enabled by default unless --no-progress is specified
    show_progress = not args.no_progress
    
    # Check progress bar availability
    if show_progress and not TQDM_AVAILABLE:
        logging.warning("Progress bar requested but tqdm package not available. Install with: pip install tqdm")
        show_progress = False
    
    logging.info(f"Video processing started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Platform: {platform.system()} {platform.release()}")
    logging.info(f"Encoder: {args.encoder}")
    logging.info(f"Force rerun: {args.force_rerun}")
    logging.info(f"Delete input: {args.delete_input}")
    logging.info(f"Recursive: {not args.no_recursive}")
    logging.info(f"Progress bar: {show_progress}")

    # Normalize and validate input path
    try:
        normalized_path = normalize_path(args.path)
        if not normalized_path:
            logging.error("Invalid path provided")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to normalize path '{args.path}': {e}")
        sys.exit(1)

    path = normalized_path
    is_single_file = Path(path).is_file()
    
    if is_single_file:
        if not is_video_file(Path(path).name):
            logging.error(f"File is not a supported video format: {path}")
            sys.exit(1)
        directory = str(Path(path).parent) or '.'
        logging.info(f"Processing single file: {path}")
    else:
        try:
            directory = ensure_path_exists(path)
            logging.info(f"Processing directory: {directory}")
        except FileNotFoundError as e:
            logging.error(f"Path not found: {path}")
            sys.exit(1)

    log = load_log()
    
    # Build a dict of all hashes of previously processed files to their log entry
    hash_to_log_entry = {entry.get('input_hash'): name for name, entry in log.items() if entry.get('input_hash')}
    
    logging.info(f"Found {len(hash_to_log_entry)} previously processed files in log")
    
    # Count total video files for progress bar
    total_video_files = count_video_files(directory, is_single_file, path, args.no_recursive)
    logging.info(f"Found {total_video_files} video files to process")
    
    # Initialize progress bar
    pbar = None
    if show_progress and total_video_files > 0:
        pbar = tqdm(
            total=total_video_files,
            desc="Processing videos",
            unit="file",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        )
    
    processed_count = 0
    skipped_count = 0
    total_size_saved = 0
    success_count = 0
    failed_count = 0
    video_files_found = 0

    # Ensure directory is a valid string for os.walk
    if not directory:
        logging.error("Invalid directory path")
        sys.exit(1)
    
    directory_path = Path(directory)
    for root, _, files in os.walk(directory_path):
        # Check for interrupt request
        if interrupt_requested:
            logging.info("Processing interrupted by user. Stopping gracefully...")
            break
            
        # If --no-recursive is specified, only process the root directory
        if not is_single_file and args.no_recursive and Path(root) != directory_path:
            continue
        for file in files:
            # Check for interrupt request
            if interrupt_requested:
                logging.info("Processing interrupted by user. Stopping gracefully...")
                break
                
            # If processing a single file, only process that specific file
            if is_single_file:
                if Path(root) / file == Path(path):
                    pass  # This is the file we want to process
                else:
                    continue
            if not is_video_file(file):
                continue
            
            video_files_found += 1
            input_path = Path(root) / file
            output_path = input_path.with_suffix('')  # Remove extension
            if args.encoder == 'x265':
                output_path = output_path.with_name(output_path.name + '_1080p_web.mp4')
            elif args.encoder == 'smart':
                output_path = output_path.with_name(output_path.name + '_1080p_smart.mp4')
            else:
                output_path = output_path.with_name(output_path.name + OUTPUT_SUFFIX)
            
            rel_input = get_relative_path(input_path, directory)

            # Update progress bar description
            if pbar:
                pbar.set_description(f"Processing: {file}")

            # Compute hash of the current file first
            current_hash = file_hash(input_path)
            if current_hash is None:
                logging.warning(f"Skipping {rel_input} due to hash computation failure")
                skipped_count += 1
                if pbar:
                    pbar.update(1)
                continue
                
            # Check if this hash is already in the log (regardless of filename)
            if current_hash in hash_to_log_entry and not args.force_rerun:
                logging.info(f"Skipping already processed (by hash): {rel_input}")
                skipped_count += 1
                if pbar:
                    pbar.update(1)
                continue

            # Check if this file is an output file from a previous run (by suffix)
            if file.endswith(OUTPUT_SUFFIX):
                # Check if this output file was already created as a result of processing another file
                # (i.e., it is listed as 'output_file' in any log entry)
                if any(entry.get('output_file') == rel_input for entry in log.values()):
                    logging.info(f"Skipping output file from previous run: {rel_input}")
                    skipped_count += 1
                    if pbar:
                        pbar.update(1)
                    continue

            logging.info(f"Processing: {rel_input}")
            start_time = time.time()
            
            try:
                input_size = input_path.stat().st_size
                logging.debug(f"Input file size: {format_size(input_size)}")
            except OSError as e:
                logging.error(f"Failed to get file size for {rel_input}: {e}")
                failed_count += 1
                if pbar:
                    pbar.update(1)
                continue
                
            success = process_video(str(input_path), str(output_path), args.encoder)
            processing_time = time.time() - start_time
            
            try:
                output_size = output_path.stat().st_size if output_path.exists() else None
                if output_size:
                    logging.debug(f"Output file size: {format_size(output_size)}")
            except OSError as e:
                logging.error(f"Failed to get output file size for {rel_input}: {e}")
                output_size = None
                
            size_diff = (input_size - output_size) if output_size else None
            processed = success and output_size is not None and output_size < input_size

            log[rel_input] = {
                'processed': processed,
                'input_size': input_size,
                'output_size': output_size,
                'size_difference': size_diff,
                'output_file': get_relative_path(output_path, directory) if processed else None,
                'input_hash': current_hash,
                'processing_time': datetime.now().isoformat(),
                'processing_duration_seconds': processing_time
            }
            save_log(log)
            # Add hash to hash_to_log_entry after processing
            hash_to_log_entry[current_hash] = rel_input
            if processed:
                logging.info(f"Done: {rel_input} (Saved {format_size(size_diff)}, Time: {processing_time:.1f}s)")
                total_size_saved += size_diff if size_diff else 0
                processed_count += 1
                success_count += 1
                if args.delete_input:
                    try:
                        input_path.unlink()
                        logging.info(f"Deleted input file: {rel_input}")
                    except Exception as e:
                        logging.error(f"Failed to delete input file: {rel_input} ({e})")
            else:
                if not success:
                    logging.error(f"Processing failed: {rel_input}")
                elif output_size is None:
                    logging.error(f"No output file created: {rel_input}")
                elif output_size >= input_size:
                    logging.warning(f"Output not smaller: {rel_input} (Input: {format_size(input_size)}, Output: {format_size(output_size)})")
                processed_count += 1
                failed_count += 1
            
            # Update progress bar
            if pbar:
                pbar.update(1)

    # Check if processing was interrupted
    if interrupt_requested:
        logging.info("Processing was interrupted by user.")
        logging.info("Current file completed, but remaining files were skipped.")
    
    # Close progress bar
    if pbar:
        pbar.close()

    # Calculate total execution time
    total_execution_time = time.time() - total_start_time
    
    logging.info(f"\nProcessing completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Total execution time: {total_execution_time:.1f} seconds ({total_execution_time/60:.1f} minutes)")
    logging.info(f"Video files found: {video_files_found}")
    logging.info(f"Files processed: {processed_count}")
    logging.info(f"  Success: {success_count}")
    logging.info(f"  Failed: {failed_count}")
    logging.info(f"Files skipped: {skipped_count}")
    if interrupt_requested:
        logging.info("Processing was interrupted - some files may not have been processed")
    logging.info(f"Total size saved: {format_size(total_size_saved)}")
    
    if failed_count > 0:
        logging.warning(f"Some files failed to process. Check {ERROR_LOG_FILE} for details.")
    
    logging.info(f"Detailed logs saved to: processing.log")
    logging.info(f"Error logs saved to: {ERROR_LOG_FILE}")
    
    # Cleanup on exit
    cleanup_on_exit(pbar, log)
    
    # Exit with appropriate code
    if interrupt_requested:
        sys.exit(130)  # Standard exit code for interrupt
    elif failed_count > 0:
        sys.exit(1)    # Exit with error if any files failed
    else:
        sys.exit(0)    # Successful completion

if __name__ == '__main__':
    main() 