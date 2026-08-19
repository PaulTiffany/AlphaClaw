from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
OMEGA_ROOT = REPO_ROOT / "OmegaClaw-Core"
HERE = Path(__file__).parent
OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
CHROMADB_SHA = "218484875d5d1bfb217a9a03d3983dc1ed9d406c"
MODEL = "asi1-mini"
PROVIDER = "ASIOne"
LIFE_CYCLES = 8
WAKE_CYCLES = 0
BOOT_CYCLES = 0

README = """---
title: AlphaClaw Omega Resident
emoji: 🦀
sdk: docker
app_port: 7860
short_description: Bounded pinned stock OmegaClaw resident
---

# AlphaClaw Omega Resident

This Space runs the complete pinned OmegaClaw substrate. AlphaClaw is not imported
into OmegaClaw and does not run a second agent or control loop inside the resident.

- OmegaClaw source: `{omega_sha}`
- Provider: `{provider}`
- Model: `{model}`
- Boot inference cycles: `{boot_cycles}`
- Human-triggered resident cycles: `{life_cycles}`
- Scheduled wake cycles: `{wake_cycles}`
- Public surface: health/status only on port 7860
- Agent communication: outbound WebSocket when `OMEGA_WS_URL` is configured

The only Omega semantic adaptation is the boot gate: the resident starts with zero
inference authority and receives its configured cycle budget only after new human
input. The pinned upstream submodule remains pristine.

The ASI:One credential is never committed to this Space. The OFF transition removes
it before pausing the Space.
"""


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def validate_source() -> None:
    if not OMEGA_ROOT.is_dir():
        raise RuntimeError("OmegaClaw-Core submodule is missing")
    observed = git_head(OMEGA_ROOT)
    if observed != OMEGA_SHA:
        raise RuntimeError(f"OmegaClaw pin mismatch: expected {OMEGA_SHA}, observed {observed}")
    if subprocess.check_output(
        ["git", "-C", str(OMEGA_ROOT), "status", "--porcelain"],
        text=True,
    ).strip():
        raise RuntimeError("OmegaClaw-Core submodule is dirty")


def preserve_runtime_config_through_privilege_drop(entrypoint: Path) -> None:
    text = entrypoint.read_text(encoding="utf-8")
    old = 'SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \\\n'
    new = 'SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL OMEGACLAW_config \\\n'
    if old not in text:
        raise RuntimeError("pinned Omega entrypoint allowlist changed")
    entrypoint.write_text(text.replace(old, new, 1), encoding="utf-8")


def require_human_input_before_inference(loop: Path) -> None:
    text = loop.read_text(encoding="utf-8")
    old = (
        '          (change-state! &lastresults "")\n'
        '          (change-state! &loops (maxNewInputLoops))\n'
        '          ))'
    )
    new = (
        '          (change-state! &lastresults "")\n'
        '          ; AlphaClaw embodiment gate: boot grants no inference authority.\n'
        '          ; New human input still refills &loops through stock Omega logic below.\n'
        '          (change-state! &loops 0)\n'
        '          (change-state! &nextWakeAt (+ (get_time) (wakeupInterval)))\n'
        '          ))'
    )
    if text.count(old) != 1:
        raise RuntimeError("pinned Omega initLoop changed; refusing boot-gate transform")
    transformed = text.replace(old, new, 1)
    if transformed.count("(change-state! &loops (maxNewInputLoops))") != 1:
        raise RuntimeError("human-input refill path changed unexpectedly")
    loop.write_text(transformed, encoding="utf-8")


def render_dockerfile() -> str:
    text = (OMEGA_ROOT / "Dockerfile").read_text(encoding="utf-8")
    replacements = {
        "ARG CHROMADB_REF=master": f"ARG CHROMADB_REF={CHROMADB_SHA}",
        "cmake --build build --config Release --parallel": (
            "cmake --build build --config Release --parallel 1"
        ),
        'RUN mkdir -p /PeTTa/repos \\\n && git clone --depth 1 --branch "${CHROMADB_REF}" "${CHROMADB_REPO}" /PeTTa/repos/petta_lib_chromadb': (
            'RUN mkdir -p /PeTTa/repos \\\n && git clone "${CHROMADB_REPO}" /PeTTa/repos/petta_lib_chromadb \\\n && git -C /PeTTa/repos/petta_lib_chromadb checkout --detach "${CHROMADB_REF}"'
        ),
        "COPY ./requirements.txt /tmp/requirements.txt": (
            "COPY OmegaClaw-Core/requirements.txt /tmp/requirements.txt"
        ),
        "COPY . .": "COPY OmegaClaw-Core .",
        "COPY --chown=www-data:www-data --chmod=0600 ./proxy/* /opt/nginx/": (
            "COPY --chown=www-data:www-data --chmod=0600 OmegaClaw-Core/proxy/* /opt/nginx/\n"
            "# HF runs nginx as www-data; reopening /dev/stdout or /dev/stderr is denied.\n"
            "RUN sed -i \\\n"
            "      -e 's#error_log /dev/stderr warn;#error_log /tmp/nginx-error.log warn;#' \\\n"
            "      -e 's#access_log /dev/stdout;#access_log /tmp/nginx-access.log;#' \\\n"
            "      /opt/nginx/nginx.conf.template \\\n"
            " && chown www-data:www-data /opt/nginx/nginx.conf.template \\\n"
            " && chmod 0600 /opt/nginx/nginx.conf.template"
        ),
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(
                f"pinned Omega Dockerfile changed; missing expected fragment: {old!r}"
            )
        text = text.replace(old, new, 1)

    terminator = (
        'ENTRYPOINT ["/PeTTa/repos/OmegaClaw-Core/entrypoint.sh"]\n'
        "CMD []\n"
    )
    if terminator not in text:
        raise RuntimeError("pinned Omega Dockerfile entrypoint changed")

    boundary = '''# AlphaClaw HF boundary: stock Omega plus deployment bindings only.
USER root
RUN mkdir -p /opt/alphaclaw-hf
COPY alphaclaw-runtime.yaml /opt/alphaclaw-hf/alphaclaw-runtime.yaml
COPY hf_entrypoint.sh /opt/alphaclaw-hf/entrypoint.sh
COPY health.py /opt/alphaclaw-hf/health.py
ENV OMEGACLAW_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml
RUN chmod 0444 /opt/alphaclaw-hf/alphaclaw-runtime.yaml \
              /opt/alphaclaw-hf/health.py \
 && chmod 0555 /opt/alphaclaw-hf/entrypoint.sh \
 && test ! -e /PeTTa/repos/AlphaClaw

EXPOSE 7860
ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]
CMD []
'''
    return text.replace(terminator, boundary, 1)


def render_residency_dockerfile() -> str:
    text = render_dockerfile()
    resident = (
        "EXPOSE 7860\n"
        'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]\n'
        "CMD []\n"
    )
    upstream = (
        'ENTRYPOINT ["/PeTTa/repos/OmegaClaw-Core/entrypoint.sh"]\n'
        "CMD []\n"
    )
    if resident not in text:
        raise RuntimeError("generated resident entrypoint is missing")
    return text.replace(resident, upstream, 1)


def stage(destination: Path) -> None:
    validate_source()
    destination.mkdir(parents=True, exist_ok=True)

    omega_destination = destination / "OmegaClaw-Core"
    # Copy the complete pinned substrate. Alpha does not select or delete Omega organs.
    shutil.copytree(
        OMEGA_ROOT,
        omega_destination,
        ignore=shutil.ignore_patterns(".git"),
        dirs_exist_ok=False,
    )
    preserve_runtime_config_through_privilege_drop(omega_destination / "entrypoint.sh")
    require_human_input_before_inference(omega_destination / "src" / "loop.metta")

    shutil.copy2(REPO_ROOT / "LICENSE", destination / "LICENSE")
    shutil.copy2(HERE / "alphaclaw-runtime.yaml", destination / "alphaclaw-runtime.yaml")
    shutil.copy2(HERE / "hf_entrypoint.sh", destination / "hf_entrypoint.sh")
    shutil.copy2(HERE / "health.py", destination / "health.py")
    (destination / "Dockerfile").write_text(render_dockerfile(), encoding="utf-8")
    (destination / "Dockerfile.residency").write_text(
        render_residency_dockerfile(),
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        README.format(
            omega_sha=OMEGA_SHA,
            provider=PROVIDER,
            model=MODEL,
            boot_cycles=BOOT_CYCLES,
            life_cycles=LIFE_CYCLES,
            wake_cycles=WAKE_CYCLES,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage the bounded pinned stock OmegaClaw Hugging Face runtime"
    )
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    stage(args.destination)


if __name__ == "__main__":
    main()
