import json
import os
import platform
import subprocess
from typing import List, Optional, Tuple

_IS_WINDOWS = platform.system() == "Windows"


def atomic_write_json(file_path: str, data) -> None:
    tmp = file_path + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, file_path)


def find_line_number_grep(file_path: str, search_pattern: str) -> Optional[int]:
    try:
        result = subprocess.run(
            ["grep", "-n", "-F", search_pattern, file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            first_match = result.stdout.split("\n")[0]
            if ":" in first_match:
                return int(first_match.split(":")[0]) - 1
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def count_lines_wc(file_path: str) -> int:
    try:
        result = subprocess.run(
            ["wc", "-l", file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return 0


def read_lines_range(file_path: str, start: int, end: int) -> List[dict]:
    messages = []

    if not _IS_WINDOWS:
        try:
            result = subprocess.run(
                ["sed", "-n", f"{start+1},{end}p", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                return messages
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if idx >= start and idx < end:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            elif idx >= end:
                break
    return messages


def get_messages_around_from_file(file_path: str, message_id: str, above: int = 50, below: int = 50) -> Tuple[Optional[List[dict]], Optional[int], Optional[int]]:
    if not os.path.exists(file_path):
        return None, None, None

    above = max(0, min(above, 200))
    below = max(0, min(below, 200))

    if not _IS_WINDOWS:
        target_idx = find_line_number_grep(file_path, f'"id":"{message_id}"')
        if target_idx is None:
            return None, None, None

        total_lines = count_lines_wc(file_path)
        if total_lines == 0:
            total_lines = target_idx + 1

        start_line = max(0, target_idx - below)
        end_line = min(total_lines, target_idx + above + 1)

        messages = read_lines_range(file_path, start_line, end_line)
        return messages, start_line, end_line

    target_idx = None
    total_lines = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            total_lines = idx + 1
            if target_idx is None and f'"id":"{message_id}"' in line:
                target_idx = idx

    if target_idx is None:
        return None, None, None

    start_line = max(0, target_idx - below)
    end_line = min(total_lines, target_idx + above + 1)

    messages = read_lines_range(file_path, start_line, end_line)
    return messages, start_line, end_line


def build_id_index(messages):
    return {msg["id"]: i for i, msg in enumerate(messages) if "id" in msg}
