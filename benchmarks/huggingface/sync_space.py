from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
BENCHMARKS_ROOT = REPO_ROOT / "benchmarks"
HERE = Path(__file__).parent
SPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")


def stage(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("Dockerfile", "app.py", "requirements.txt", "README.md"):
        shutil.copy2(HERE / name, destination / name)
    shutil.copy2(BENCHMARKS_ROOT / "analyze.py", destination / "analyze.py")
    shutil.copy2(REPO_ROOT / "LICENSE", destination / "LICENSE")


def as_bool(value: str | None, default: bool = True) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    repo_id = os.environ.get("HF_SPACE_ID", "")
    token = os.environ.get("HF_TOKEN", "")
    private = as_bool(os.environ.get("HF_SPACE_PRIVATE"), default=True)

    if not SPACE_ID.fullmatch(repo_id):
        raise SystemExit(
            "HF_SPACE_ID must have owner/name form, for example PaulTiffany/alphaclaw-benchmarks"
        )
    if not token:
        raise SystemExit("HF_TOKEN is required as a narrowly scoped GitHub Actions secret")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        private=private,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(prefix="alphaclaw-benchmark-space-") as temporary:
        staged = Path(temporary)
        stage(staged)
        api.upload_folder(
            repo_id=repo_id,
            repo_type="space",
            folder_path=staged,
            delete_patterns="*",
            commit_message="Synchronize AlphaClaw benchmark lab",
            token=token,
        )


if __name__ == "__main__":
    main()
