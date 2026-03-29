import json
import os
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
polls_file = os.path.join(_MODULE_DIR, "polls.json")
poll_votes_file = os.path.join(_MODULE_DIR, "poll_votes.json")

_lock = threading.RLock()
_polls_cache: Dict[str, dict] = {}
_votes_cache: Dict[str, List[dict]] = {}
_loaded: bool = False


def _load_polls():
    global _polls_cache, _votes_cache, _loaded

    try:
        with open(polls_file, 'r') as f:
            _polls_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _polls_cache = {}

    try:
        with open(poll_votes_file, 'r') as f:
            _votes_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _votes_cache = {}

    _loaded = True


def _save_polls():
    tmp = polls_file + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(_polls_cache, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, polls_file)


def _save_votes():
    tmp = poll_votes_file + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(_votes_cache, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, poll_votes_file)


def _ensure_loaded():
    if not _loaded:
        _load_polls()


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(polls_file):
        with open(polls_file, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(poll_votes_file):
        with open(poll_votes_file, 'w') as f:
            json.dump({}, f)


_ensure_storage()


def create_poll(message_id: str, question: str, options: List[dict],
                channel: Optional[str] = None, thread_id: Optional[str] = None,
                allow_multiselect: bool = False, expires_at: Optional[float] = None,
                created_by: Optional[str] = None) -> str:
    _ensure_loaded()

    poll_id = str(uuid.uuid4())
    now = time.time()

    for i, opt in enumerate(options):
        if "id" not in opt:
            opt["id"] = str(i)

    with _lock:
        _polls_cache[poll_id] = {
            "id": poll_id,
            "message_id": message_id,
            "channel": channel,
            "thread_id": thread_id,
            "question": question,
            "options": options,
            "allow_multiselect": allow_multiselect,
            "expires_at": expires_at,
            "created_by": created_by,
            "created_at": now,
            "ended": False,
            "ended_at": None
        }
        _votes_cache[poll_id] = []
        _save_polls()
        _save_votes()

    return poll_id


def get_poll(poll_id: str) -> Optional[dict]:
    _ensure_loaded()
    with _lock:
        poll = _polls_cache.get(poll_id)
        return poll.copy() if poll else None


def get_poll_by_message(message_id: str) -> Optional[dict]:
    _ensure_loaded()
    with _lock:
        for poll in _polls_cache.values():
            if poll.get("message_id") == message_id:
                return poll.copy()
    return None


def vote_poll(poll_id: str, option_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    _ensure_loaded()

    poll = get_poll(poll_id)
    if not poll:
        return False, "Poll not found"

    if poll["ended"]:
        return False, "Poll has ended"

    if poll["expires_at"] and time.time() > poll["expires_at"]:
        return False, "Poll has expired"

    valid_option = False
    for opt in poll["options"]:
        if opt.get("id") == option_id:
            valid_option = True
            break

    if not valid_option:
        return False, f"Invalid option: {option_id}"

    with _lock:
        votes = _votes_cache.get(poll_id, [])

        if not poll["allow_multiselect"]:
            votes = [v for v in votes if v["user_id"] != user_id or v["option_id"] == option_id]

        existing = any(v["user_id"] == user_id and v["option_id"] == option_id for v in votes)
        if not existing:
            votes.append({
                "poll_id": poll_id,
                "option_id": option_id,
                "user_id": user_id,
                "voted_at": time.time()
            })
            _votes_cache[poll_id] = votes
            _save_votes()

    return True, None


def remove_vote(poll_id: str, option_id: str, user_id: str) -> bool:
    _ensure_loaded()

    poll = get_poll(poll_id)
    if not poll:
        return False

    if poll["ended"]:
        return False

    with _lock:
        votes = _votes_cache.get(poll_id, [])
        original_len = len(votes)
        votes = [v for v in votes if not (v["user_id"] == user_id and v["option_id"] == option_id)]

        if len(votes) < original_len:
            _votes_cache[poll_id] = votes
            _save_votes()
            return True

    return False


def get_poll_results(poll_id: str) -> Optional[dict]:
    _ensure_loaded()

    poll = get_poll(poll_id)
    if not poll:
        return None

    with _lock:
        votes = _votes_cache.get(poll_id, [])

    results = {}
    for opt in poll["options"]:
        results[opt.get("id")] = {
            "id": opt.get("id"),
            "text": opt.get("text"),
            "emoji": opt.get("emoji"),
            "votes": 0,
            "voters": []
        }

    for vote in votes:
        option_id = vote["option_id"]
        if option_id in results:
            results[option_id]["votes"] += 1
            results[option_id]["voters"].append(vote["user_id"])

    total_votes = len(votes)

    return {
        "poll_id": poll_id,
        "question": poll["question"],
        "allow_multiselect": poll["allow_multiselect"],
        "ended": poll["ended"],
        "ended_at": poll["ended_at"],
        "total_votes": total_votes,
        "results": list(results.values())
    }


def end_poll(poll_id: str) -> bool:
    _ensure_loaded()

    poll = get_poll(poll_id)
    if not poll:
        return False

    if poll["ended"]:
        return False

    now = time.time()

    with _lock:
        if poll_id in _polls_cache:
            _polls_cache[poll_id]["ended"] = True
            _polls_cache[poll_id]["ended_at"] = now
            _save_polls()
            return True

    return False


def delete_poll(poll_id: str) -> bool:
    _ensure_loaded()

    with _lock:
        if poll_id in _polls_cache:
            del _polls_cache[poll_id]
            if poll_id in _votes_cache:
                del _votes_cache[poll_id]
            _save_polls()
            _save_votes()
            return True
    return False


def get_user_vote(poll_id: str, user_id: str) -> List[str]:
    _ensure_loaded()

    with _lock:
        votes = _votes_cache.get(poll_id, [])
        return [v["option_id"] for v in votes if v["user_id"] == user_id]


def is_poll_expired(poll_id: str) -> bool:
    poll = get_poll(poll_id)
    if not poll:
        return True

    if poll["ended"]:
        return True

    if poll["expires_at"] and time.time() > poll["expires_at"]:
        return True

    return False


def cleanup_expired_polls() -> int:
    _ensure_loaded()

    now = time.time()
    count = 0

    with _lock:
        for poll_id, poll in list(_polls_cache.items()):
            if poll.get("expires_at") and poll["expires_at"] < now and not poll.get("ended"):
                _polls_cache[poll_id]["ended"] = True
                _polls_cache[poll_id]["ended_at"] = now
                count += 1

        if count > 0:
            _save_polls()

    return count
