from __future__ import annotations

import os

DEFAULT_BASE_URL = "https://api.imastudio.com"
PREFS_PATH = os.path.expanduser("~/.openclaw/memory/ima_prefs.json")
BOOTSTRAP_STATE_PATH = os.path.expanduser("~/.openclaw/memory/ima_bootstrap.json")
VIDEO_MAX_WAIT_SECONDS = 40 * 60
VIDEO_RECORDS_URL = "https://www.imastudio.com/ai-creation/text-to-video"

VIDEO_TASK_TYPES = {
    "text_to_video",
    "image_to_video",
    "first_last_frame_to_video",
    "reference_image_to_video",
}

INPUT_REQUIRED_MIN = {
    "image_to_image": 1,
    "image_to_video": 1,
    "reference_image_to_video": 1,
    "first_last_frame_to_video": 2,
}

INPUT_EXACT_COUNT = {
    "first_last_frame_to_video": 2,
}

TEXT_ONLY_TASK_TYPES = {
    "text_to_image",
    "text_to_video",
    "text_to_music",
    "text_to_speech",
}

IMA_IM_BASE = "https://imapi.liveme.com"
APP_ID = "webAgent"
APP_KEY = "32jdskjdk320eew"

POLL_CONFIG = {
    "text_to_image": {"interval": 5, "max_wait": 600},
    "image_to_image": {"interval": 5, "max_wait": 600},
    "text_to_video": {"interval": 8, "max_wait": VIDEO_MAX_WAIT_SECONDS},
    "image_to_video": {"interval": 8, "max_wait": VIDEO_MAX_WAIT_SECONDS},
    "first_last_frame_to_video": {"interval": 8, "max_wait": VIDEO_MAX_WAIT_SECONDS},
    "reference_image_to_video": {"interval": 8, "max_wait": VIDEO_MAX_WAIT_SECONDS},
    "text_to_music": {"interval": 5, "max_wait": 480},
    "text_to_speech": {"interval": 3, "max_wait": 300},
}

MODEL_ID_ALIASES = {
    "seedance 2.0": "ima-pro",
    "seedance 2.0-fast": "ima-pro-fast",
    "seedance 2.0 fast": "ima-pro-fast",
}
