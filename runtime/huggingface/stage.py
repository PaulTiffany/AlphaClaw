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
HISTORY_CHARS = 0
PERSIST_HISTORY = False
MODEL_ACTIONS = ("send",)
RESIDENT_PLUGINS = ("wschat", "asione")

MINIMAL_PLUGINS = """# AlphaClaw staged resident plugin allowlist.
# The pinned upstream tree remains complete; only these plugins are loaded.
- name: wschat
  loader: python
  location: "{REPO}/channels"

- name: asione
  loader: python
  location: "{REPO}/providers"
"""

README = """---
title: AlphaClaw Omega Resident
emoji: 🦀
sdk: docker
app_port: 7860
short_description: Minimum-authority bounded OmegaClaw resident
---

# AlphaClaw Omega Resident

This Space contains the complete pinned OmegaClaw source substrate, but exposes a
minimum-authority resident surface. AlphaClaw is not imported into OmegaClaw and
does not run a second agent or control loop inside the resident.

- OmegaClaw source: `{omega_sha}`
- Provider: `{provider}`
- Model: `{model}`
- Boot inference cycles: `{boot_cycles}`
- Human-triggered resident cycles: `{life_cycles}`
- Scheduled wake cycles: `{wake_cycles}`
- Cross-episode history recall: `{history_chars}` characters
- Persistent history writes: `{persist_history}`
- Model-directed actions: `{model_actions}`
- Loaded plugins: `{resident_plugins}`
- Public surface: health/status only on port 7860
- Agent communication: outbound WSS when `OMEGA_WS_URL` is configured

The staged resident makes only subtractive authority adaptations: boot begins with
zero inference authority; every genuinely new human message refills the configured
finite budget; persistent history and historical recall are disabled; only `send`
is model-callable; and only the ASI:One provider plus WebSocket channel plugins are
loaded. The pinned upstream submodule remains pristine.

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
        '          ; Every genuinely new human input refills stock Omega below.\n'
        '          (change-state! &loops 0)\n'
        '          (change-state! &nextWakeAt (+ (get_time) (wakeupInterval)))\n'
        '          ))'
    )
    if text.count(old) != 1:
        raise RuntimeError("pinned Omega initLoop changed; refusing boot-gate transform")
    transformed = text.replace(old, new, 1)

    refill_gate = "(if (and (> $k 1) $msgnew)"
    if transformed.count(refill_gate) != 1:
        raise RuntimeError("pinned Omega human-input refill gate changed")
    transformed = transformed.replace(refill_gate, "(if $msgnew", 1)

    if transformed.count("(change-state! &loops (maxNewInputLoops))") != 1:
        raise RuntimeError("human-input refill path changed unexpectedly")
    if refill_gate in transformed:
        raise RuntimeError("first-iteration human refill gate survived transform")
    loop.write_text(transformed, encoding="utf-8")


def restrict_resident_plugins(plugin_config: Path) -> None:
    text = plugin_config.read_text(encoding="utf-8")
    required = (
        '- name: wschat\n  loader: python\n  location: "{REPO}/channels"',
        '- name: asione\n  loader: python\n  location: "{REPO}/providers"',
    )
    for record in required:
        if text.count(record) != 1:
            raise RuntimeError("pinned Omega plugin registry changed; refusing resident allowlist")
    plugin_config.write_text(MINIMAL_PLUGINS, encoding="utf-8")


def restrict_model_action_surface(helper: Path, skills: Path) -> None:
    helper_text = helper.read_text(encoding="utf-8")
    start = helper_text.find("STATIC_LLM_COMMANDS = {")
    end = helper_text.find("\nLLM_COMMANDS = set(STATIC_LLM_COMMANDS)", start)
    if start < 0 or end < 0:
        raise RuntimeError("pinned Omega static command registry changed")
    original_registry = helper_text[start:end]
    for command in ('"send"', '"shell"', '"metta"', '"websearch"', '"write-file"'):
        if command not in original_registry:
            raise RuntimeError("pinned Omega command registry lost an expected command")
    helper_text = helper_text[:start] + 'STATIC_LLM_COMMANDS = {"send"}' + helper_text[end:]

    add_old = """def add_llm_command(command):
    LLM_COMMANDS.add(str(command))
    return True
"""
    add_new = """def add_llm_command(command):
    # AlphaClaw resident authority is fixed outside mutable Omega state.
    return str(command) in STATIC_LLM_COMMANDS
"""
    if helper_text.count(add_old) != 1:
        raise RuntimeError("pinned Omega dynamic command registration changed")
    helper_text = helper_text.replace(add_old, add_new, 1)
    helper.write_text(helper_text, encoding="utf-8")

    skills_text = skills.read_text(encoding="utf-8")
    get_skills_old = """(= (getSkills)
   (let $static (getStaticSkills)
     (collapse (superpose ((superpose $static) (dynamic-skill $_))))))
"""
    get_skills_new = """(= (getSkills)
   (getStaticSkills))
"""
    if skills_text.count(get_skills_old) != 1:
        raise RuntimeError("pinned Omega skill aggregation changed")
    skills_text = skills_text.replace(get_skills_old, get_skills_new, 1)

    static_start = skills_text.find("(= (getStaticSkills)")
    static_end = skills_text.find("\n    ; TODO add load-plugin/unload-plugin skills", static_start)
    if static_start < 0 or static_end < 0:
        raise RuntimeError("pinned Omega static skill description block changed")
    original_static = skills_text[static_start:static_end]
    for token in ("Execute shell command", "Search the web", "Execute MeTTa expression"):
        if token not in original_static:
            raise RuntimeError("pinned Omega static skill surface lost expected capability")
    minimal_static = """(= (getStaticSkills)
   ("- Send message to user: send string"))
"""
    skills_text = skills_text[:static_start] + minimal_static + skills_text[static_end:]
    skills.write_text(skills_text, encoding="utf-8")


def disable_persistent_history(memory: Path) -> None:
    text = memory.read_text(encoding="utf-8")
    old = """(= (appendToHistory $addition)
   (append-file-raw (library OmegaClaw-Core ./memory/history.metta) (swrite $addition)))
"""
    new = """(= (appendToHistory $addition)
   ; AlphaClaw staged boundary: persistent history writes disabled.
   True)
"""
    if text.count(old) != 1:
        raise RuntimeError("pinned Omega history writer changed; refusing persistence transform")
    memory.write_text(text.replace(old, new, 1), encoding="utf-8")


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

    boundary = '''# AlphaClaw HF boundary: pinned Omega plus minimum-authority deployment bindings.
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
    # Copy the complete pinned substrate; authority is narrowed only in the staged copy.
    shutil.copytree(
        OMEGA_ROOT,
        omega_destination,
        ignore=shutil.ignore_patterns(".git"),
        dirs_exist_ok=False,
    )
    preserve_runtime_config_through_privilege_drop(omega_destination / "entrypoint.sh")
    require_human_input_before_inference(omega_destination / "src" / "loop.metta")
    restrict_resident_plugins(omega_destination / "config" / "plugins.yaml")
    restrict_model_action_surface(
        omega_destination / "src" / "helper.py",
        omega_destination / "src" / "skills.metta",
    )
    disable_persistent_history(omega_destination / "src" / "memory.metta")

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
            history_chars=HISTORY_CHARS,
            persist_history=str(PERSIST_HISTORY).lower(),
            model_actions=", ".join(MODEL_ACTIONS),
            resident_plugins=", ".join(RESIDENT_PLUGINS),
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage the minimum-authority pinned OmegaClaw Hugging Face runtime"
    )
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    stage(args.destination)


if __name__ == "__main__":
    main()
