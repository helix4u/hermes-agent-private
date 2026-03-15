"""Welcome banner, ASCII art, and skills summary for the CLI.

Pure display functions with no HermesCLI state dependency.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import print_formatted_text as _pt_print
from prompt_toolkit.formatted_text import ANSI as _PT_ANSI


# =========================================================================
# ANSI building blocks for conversation display
# =========================================================================

_GOLD = "\033[1;33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RST = "\033[0m"


def cprint(text: str):
    """Print ANSI-colored text through prompt_toolkit's renderer."""
    _pt_print(_PT_ANSI(text))


# =========================================================================
# ASCII Art & Branding
# =========================================================================

from hermes_cli import __version__ as VERSION, __release_date__ as RELEASE_DATE

HERMES_AGENT_LOGO = """[bold #FFD700]██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗       █████╗  ██████╗ ███████╗███╗   ██╗████████╗[/]
[bold #FFD700]██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝      ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝[/]
[#FFBF00]███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗█████╗███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║[/]
[#FFBF00]██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║╚════╝██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║[/]
[#CD7F32]██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║      ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║[/]
[#CD7F32]╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝[/]"""

HERMES_CADUCEUS = """[#CD7F32]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⡀⠀⣀⣀⠀⢀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#CD7F32]⠀⠀⠀⠀⠀⠀⢀⣠⣴⣾⣿⣿⣇⠸⣿⣿⠇⣸⣿⣿⣷⣦⣄⡀⠀⠀⠀⠀⠀⠀[/]
[#FFBF00]⠀⢀⣠⣴⣶⠿⠋⣩⡿⣿⡿⠻⣿⡇⢠⡄⢸⣿⠟⢿⣿⢿⣍⠙⠿⣶⣦⣄⡀⠀[/]
[#FFBF00]⠀⠀⠉⠉⠁⠶⠟⠋⠀⠉⠀⢀⣈⣁⡈⢁⣈⣁⡀⠀⠉⠀⠙⠻⠶⠈⠉⠉⠀⠀[/]
[#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⡿⠛⢁⡈⠛⢿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⣿⣦⣤⣈⠁⢠⣴⣿⠿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFBF00]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠻⢿⣿⣦⡉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFBF00]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⢷⣦⣈⠛⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#CD7F32]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣴⠦⠈⠙⠿⣦⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#CD7F32]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣤⡈⠁⢤⣿⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠷⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⠑⢶⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠁⢰⡆⠈⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠳⠈⣡⠞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"""

COMPACT_BANNER = """
[bold #FFD700]╔══════════════════════════════════════════════════════════════╗[/]
[bold #FFD700]║[/]  [#FFBF00]⚕ NOUS HERMES[/] [dim #B8860B]- AI Agent Framework[/]              [bold #FFD700]║[/]
[bold #FFD700]║[/]  [#CD7F32]Messenger of the Digital Gods[/]    [dim #B8860B]Nous Research[/]   [bold #FFD700]║[/]
[bold #FFD700]╚══════════════════════════════════════════════════════════════╝[/]
"""


# =========================================================================
# Update checks
# =========================================================================

_UPDATE_CACHE_TTL_SECONDS = 6 * 60 * 60
_update_result: Optional[int] = None
_update_check_done = threading.Event()
_update_check_lock = threading.Lock()
_update_check_started = False


def _resolve_update_repo() -> Optional[Path]:
    """Return the git checkout to use for update checks, if available."""
    try:
        from hermes_cli.config import get_hermes_home

        repo_dir = get_hermes_home() / "hermes-agent"
    except Exception:
        repo_dir = Path.home() / ".hermes" / "hermes-agent"

    if not (repo_dir / ".git").exists():
        repo_dir = Path(__file__).resolve().parent.parent
    if not (repo_dir / ".git").exists():
        return None
    return repo_dir


def _git_output(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=True,
    )
    return result.stdout.strip()


def _resolve_tracking_ref(repo_dir: Path) -> Optional[str]:
    try:
        upstream_ref = _git_output(repo_dir, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if upstream_ref:
            return upstream_ref
    except Exception:
        pass

    for candidate in ("private/main", "upstream/main", "origin/main", "origin/master"):
        try:
            _git_output(repo_dir, "rev-parse", "--verify", candidate)
            return candidate
        except Exception:
            continue
    return None


def check_for_updates() -> Optional[int]:
    """Return how many commits behind the tracked branch this checkout is."""
    repo_dir = _resolve_update_repo()
    if repo_dir is None:
        return None

    try:
        from hermes_cli.config import get_hermes_home

        cache_file = get_hermes_home() / ".update_check"
    except Exception:
        cache_file = Path.home() / ".hermes" / ".update_check"

    now = time.time()
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8", errors="replace"))
        if now - float(cache.get("checked_at", 0)) < _UPDATE_CACHE_TTL_SECONDS:
            return int(cache.get("behind", 0))
    except Exception:
        pass

    tracking_ref = _resolve_tracking_ref(repo_dir)
    if not tracking_ref:
        return None

    try:
        remote_name = tracking_ref.split("/", 1)[0]
        subprocess.run(
            ["git", "fetch", "--quiet", remote_name],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
        )
        behind = int(_git_output(repo_dir, "rev-list", "--count", f"HEAD..{tracking_ref}") or "0")
    except Exception:
        return None

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"checked_at": now, "behind": behind}, ensure_ascii=False),
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    return behind


def prefetch_update_check() -> None:
    """Start the update check in a background daemon thread once."""
    global _update_check_started
    with _update_check_lock:
        if _update_check_started:
            return
        _update_check_started = True

    def _run() -> None:
        global _update_result
        try:
            _update_result = check_for_updates()
        finally:
            _update_check_done.set()

    threading.Thread(target=_run, daemon=True).start()


def get_update_result(timeout: float = 0.0) -> Optional[int]:
    """Return the prefetched update result, or None if it isn't ready."""
    _update_check_done.wait(timeout=timeout)
    if not _update_check_done.is_set():
        return None
    return _update_result


# =========================================================================
# Skills scanning
# =========================================================================

def get_available_skills() -> Dict[str, List[str]]:
    """Scan ~/.hermes/skills/ and return skills grouped by category."""
    import os

    hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    skills_dir = hermes_home / "skills"
    skills_by_category = {}

    if not skills_dir.exists():
        return skills_by_category

    for skill_file in skills_dir.rglob("SKILL.md"):
        rel_path = skill_file.relative_to(skills_dir)
        parts = rel_path.parts
        if len(parts) >= 2:
            category = parts[0]
            skill_name = parts[-2]
        else:
            category = "general"
            skill_name = skill_file.parent.name
        skills_by_category.setdefault(category, []).append(skill_name)

    return skills_by_category


# =========================================================================
# Welcome banner
# =========================================================================

def build_welcome_banner(console: Console, model: str, cwd: str,
                         tools: List[dict] = None,
                         enabled_toolsets: List[str] = None,
                         session_id: str = None,
                         get_toolset_for_tool=None):
    """Build and print a welcome banner with caduceus on left and info on right.

    Args:
        console: Rich Console instance.
        model: Current model name.
        cwd: Current working directory.
        tools: List of tool definitions.
        enabled_toolsets: List of enabled toolset names.
        session_id: Session identifier.
        get_toolset_for_tool: Callable to map tool name -> toolset name.
    """
    from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
    if get_toolset_for_tool is None:
        from model_tools import get_toolset_for_tool

    tools = tools or []
    enabled_toolsets = enabled_toolsets or []

    _, unavailable_toolsets = check_tool_availability(quiet=True)
    disabled_tools = set()
    for item in unavailable_toolsets:
        disabled_tools.update(item.get("tools", []))

    layout_table = Table.grid(padding=(0, 2))
    layout_table.add_column("left", justify="center")
    layout_table.add_column("right", justify="left")

    left_lines = ["", HERMES_CADUCEUS, ""]
    model_short = model.split("/")[-1] if "/" in model else model
    if len(model_short) > 28:
        model_short = model_short[:25] + "..."
    left_lines.append(f"[#FFBF00]{model_short}[/] [dim #B8860B]·[/] [dim #B8860B]Nous Research[/]")
    left_lines.append(f"[dim #B8860B]{cwd}[/]")
    if session_id:
        left_lines.append(f"[dim #8B8682]Session: {session_id}[/]")
    left_content = "\n".join(left_lines)

    right_lines = ["[bold #FFBF00]Available Tools[/]"]
    toolsets_dict: Dict[str, list] = {}

    for tool in tools:
        tool_name = tool["function"]["name"]
        toolset = get_toolset_for_tool(tool_name) or "other"
        toolsets_dict.setdefault(toolset, []).append(tool_name)

    for item in unavailable_toolsets:
        toolset_id = item.get("id", item.get("name", "unknown"))
        display_name = f"{toolset_id}_tools" if not toolset_id.endswith("_tools") else toolset_id
        if display_name not in toolsets_dict:
            toolsets_dict[display_name] = []
        for tool_name in item.get("tools", []):
            if tool_name not in toolsets_dict[display_name]:
                toolsets_dict[display_name].append(tool_name)

    sorted_toolsets = sorted(toolsets_dict.keys())
    display_toolsets = sorted_toolsets[:8]
    remaining_toolsets = len(sorted_toolsets) - 8

    for toolset in display_toolsets:
        tool_names = toolsets_dict[toolset]
        colored_names = []
        for name in sorted(tool_names):
            if name in disabled_tools:
                colored_names.append(f"[red]{name}[/]")
            else:
                colored_names.append(f"[#FFF8DC]{name}[/]")

        tools_str = ", ".join(colored_names)
        if len(", ".join(sorted(tool_names))) > 45:
            short_names = []
            length = 0
            for name in sorted(tool_names):
                if length + len(name) + 2 > 42:
                    short_names.append("...")
                    break
                short_names.append(name)
                length += len(name) + 2
            colored_names = []
            for name in short_names:
                if name == "...":
                    colored_names.append("[dim]...[/]")
                elif name in disabled_tools:
                    colored_names.append(f"[red]{name}[/]")
                else:
                    colored_names.append(f"[#FFF8DC]{name}[/]")
            tools_str = ", ".join(colored_names)

        right_lines.append(f"[dim #B8860B]{toolset}:[/] {tools_str}")

    if remaining_toolsets > 0:
        right_lines.append(f"[dim #B8860B](and {remaining_toolsets} more toolsets...)[/]")

    # MCP Servers section (only if configured)
    try:
        from tools.mcp_tool import get_mcp_status
        mcp_status = get_mcp_status()
    except Exception:
        mcp_status = []

    if mcp_status:
        right_lines.append("")
        right_lines.append("[bold #FFBF00]MCP Servers[/]")
        for srv in mcp_status:
            if srv["connected"]:
                right_lines.append(
                    f"[dim #B8860B]{srv['name']}[/] [#FFF8DC]({srv['transport']})[/] "
                    f"[dim #B8860B]—[/] [#FFF8DC]{srv['tools']} tool(s)[/]"
                )
            else:
                right_lines.append(
                    f"[red]{srv['name']}[/] [dim]({srv['transport']})[/] "
                    f"[red]— failed[/]"
                )

    right_lines.append("")
    right_lines.append("[bold #FFBF00]Available Skills[/]")
    skills_by_category = get_available_skills()
    total_skills = sum(len(s) for s in skills_by_category.values())

    if skills_by_category:
        for category in sorted(skills_by_category.keys()):
            skill_names = sorted(skills_by_category[category])
            if len(skill_names) > 8:
                display_names = skill_names[:8]
                skills_str = ", ".join(display_names) + f" +{len(skill_names) - 8} more"
            else:
                skills_str = ", ".join(skill_names)
            if len(skills_str) > 50:
                skills_str = skills_str[:47] + "..."
            right_lines.append(f"[dim #B8860B]{category}:[/] [#FFF8DC]{skills_str}[/]")
    else:
        right_lines.append("[dim #B8860B]No skills installed[/]")

    right_lines.append("")
    mcp_connected = sum(1 for s in mcp_status if s["connected"]) if mcp_status else 0
    summary_parts = [f"{len(tools)} tools", f"{total_skills} skills"]
    if mcp_connected:
        summary_parts.append(f"{mcp_connected} MCP servers")
    summary_parts.append("/help for commands")
    right_lines.append(f"[dim #B8860B]{' · '.join(summary_parts)}[/]")

    try:
        behind = get_update_result(timeout=0.0)
        if behind and behind > 0:
            commits_word = "commit" if behind == 1 else "commits"
            right_lines.append(f"[dim #B8860B]Update available: {behind} {commits_word} behind[/]")
    except Exception:
        pass

    right_content = "\n".join(right_lines)
    layout_table.add_row(left_content, right_content)

    outer_panel = Panel(
        layout_table,
        title=f"[bold #FFD700]Hermes Agent v{VERSION} ({RELEASE_DATE})[/]",
        border_style="#CD7F32",
        padding=(0, 2),
    )

    console.print()
    console.print(HERMES_AGENT_LOGO)
    console.print()
    console.print(outer_panel)
