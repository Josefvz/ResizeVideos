import os
import sys
import json
import subprocess
from pathlib import Path
import argparse
import hashlib

# List of common video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.mpeg', '.mpg', '.m4v']

LOG_FILE = 'process_log.json'
OUTPUT_SUFFIX = '_1080p_web_gpu.mp4'

FFMPEG_CMD_TEMPLATES = {
    'cuda': [
        'ffmpeg', '-y', '-vsync', '0', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
        '-i', '{input}', '-vf', 'scale_cuda=1920:1080',
        '-c:v', 'hevc_nvenc', '-preset', 'p4', '-rc', 'vbr_hq', '-cq', '24', '-b:v', '0',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '{output}'
    ],
    'x265': [
        'ffmpeg', '-y', '-i', '{input}', '-vf', 'scale=-2:1080',
        '-c:v', 'libx265', '-preset', 'medium', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '{output}'
    ]
}

def format_size(size):
    if size is None:
        return 'N/A'
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_log(log):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)

def is_video_file(filename):
    return any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

def process_video(input_path, output_path, encoder):
    cmd_template = FFMPEG_CMD_TEMPLATES[encoder]
    cmd = [arg.format(input=input_path, output=output_path) for arg in cmd_template]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error processing {input_path}: {e}")
        return False

def file_hash(path):
    """Compute SHA256 hash of a file's content."""
    hash_sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Process videos in a directory with ffmpeg and log results.")
    parser.add_argument('path', help='Directory to scan for video files or single video file to process')
    parser.add_argument('--delete-input', action='store_true', help='Delete input file if output is smaller')
    parser.add_argument('--encoder', choices=['cuda', 'x265'], default='cuda', help='Choose ffmpeg encoder: cuda (GPU, default) or x265 (CPU)')
    parser.add_argument('--force-rerun', action='store_true', help='Force processing even if file was already processed before')
    parser.add_argument('--no-recursive', action='store_true', help='Process only the specified directory, not subdirectories (ignored when processing a single file)')
    args = parser.parse_args()

    path = args.path
    is_single_file = os.path.isfile(path)
    
    if is_single_file:
        if not is_video_file(os.path.basename(path)):
            print(f"File is not a supported video format: {path}")
            sys.exit(1)
        directory = os.path.dirname(path) or '.'
    else:
        if not os.path.isdir(path):
            print(f"Path not found: {path}")
            sys.exit(1)
        directory = path

    log = load_log()
    
    # Build a dict of all hashes of previously processed files to their log entry
    hash_to_log_entry = {entry.get('input_hash'): name for name, entry in log.items() if entry.get('input_hash')}
    
    processed_count = 0
    skipped_count = 0
    total_size_saved = 0
    success_count = 0
    failed_count = 0

    for root, _, files in os.walk(directory):
        # If --no-recursive is specified, only process the root directory
        if not is_single_file and args.no_recursive and root != directory:
            continue
        for file in files:
            # If processing a single file, only process that specific file
            if is_single_file:
                if os.path.join(root, file) != path:
                    continue
            if not is_video_file(file):
                continue
            input_path = os.path.join(root, file)
            output_path = os.path.splitext(input_path)[0] + OUTPUT_SUFFIX
            if args.encoder == 'x265':
                output_path = os.path.splitext(input_path)[0] + '_1080p_web.mp4'
            rel_input = os.path.relpath(input_path, directory)

            # Compute hash of the current file first
            current_hash = file_hash(input_path)
            # Check if this hash is already in the log (regardless of filename)
            if current_hash in hash_to_log_entry and not args.force_rerun:
                print(f"Skipping already processed (by hash): {rel_input}")
                skipped_count += 1
                continue

            # Check if this file is an output file from a previous run (by suffix)
            if file.endswith(OUTPUT_SUFFIX):
                # Check if this output file was already created as a result of processing another file
                # (i.e., it is listed as 'output_file' in any log entry)
                if any(entry.get('output_file') == rel_input for entry in log.values()):
                    print(f"Skipping output file from previous run: {rel_input}")
                    skipped_count += 1
                    continue

            print(f"Processing: {rel_input}")
            input_size = os.path.getsize(input_path)
            success = process_video(input_path, output_path, args.encoder)
            output_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
            size_diff = (input_size - output_size) if output_size else None
            processed = success and output_size is not None and output_size < input_size

            log[rel_input] = {
                'processed': processed,
                'input_size': input_size,
                'output_size': output_size,
                'size_difference': size_diff,
                'output_file': os.path.relpath(output_path, directory) if processed else None,
                'input_hash': current_hash
            }
            save_log(log)
            # Add hash to hash_to_log_entry after processing
            hash_to_log_entry[current_hash] = rel_input
            if processed:
                print(f"Done: {rel_input} (Saved {format_size(size_diff)})")
                total_size_saved += size_diff if size_diff else 0
                processed_count += 1
                success_count += 1
                if args.delete_input:
                    try:
                        os.remove(input_path)
                        print(f"Deleted input file: {rel_input}")
                    except Exception as e:
                        print(f"Failed to delete input file: {rel_input} ({e})")
            else:
                print(f"Failed or not smaller: {rel_input}")
                processed_count += 1
                failed_count += 1

    print("\nSummary:")
    print(f"Files processed: {processed_count}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {failed_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Total size saved: {format_size(total_size_saved)}")

if __name__ == '__main__':
    main() 