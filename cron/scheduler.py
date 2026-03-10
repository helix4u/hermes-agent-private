"""
Cron job scheduler - executes due jobs.

Provides tick() which checks for due jobs and runs them. The gateway
calls this every 60 seconds from a background thread.

Uses a file-based lock (~/.hermes/cron/.tick.lock) so only one tick
runs at a time if multiple processes overlap.
"""

import asyncio
import json
import logging
import multiprocessing
import os
import sys
import traceback
import time

# fcntl is Unix-only; on Windows use msvcrt for file locking
try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cron.jobs import get_due_jobs, mark_job_run, save_job_output
from agent.env_loader import load_dotenv_with_fallback

# Resolve Hermes home directory (respects HERMES_HOME override)
_hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))

# File-based lock prevents concurrent ticks from gateway + daemon + systemd timer
_LOCK_DIR = _hermes_home / "cron"
_LOCK_FILE = _LOCK_DIR / ".tick.lock"
_DEFAULT_MODEL = "google/gemini-2.0-flash-001:free"
_DEFAULT_CRON_JOB_TIMEOUT_SECONDS = 1800


def _resolve_cron_job_timeout_seconds() -> int:
    """
    Resolve per-job timeout used by the scheduler tick.

    Set HERMES_CRON_JOB_TIMEOUT_SECONDS=0 to disable timeout enforcement.
    """
    raw = os.getenv("HERMES_CRON_JOB_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_CRON_JOB_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid HERMES_CRON_JOB_TIMEOUT_SECONDS='%s'; using default=%ss",
            raw,
            _DEFAULT_CRON_JOB_TIMEOUT_SECONDS,
        )
        return _DEFAULT_CRON_JOB_TIMEOUT_SECONDS
    return max(0, value)


def _build_job_failure_output(job: dict, error_msg: str, tb: Optional[str] = None) -> str:
    """Build a markdown failure document consistent with run_job() output."""
    trace_block = tb or "No traceback available."
    timing_block = _format_latest_session_timing_block(job.get("id", "unknown"))
    return f"""# Cron Job: {job.get("name", job.get("id", "unknown"))} (FAILED)

**Job ID:** {job.get("id", "unknown")}
**Run Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Schedule:** {job.get('schedule_display', 'N/A')}

## Prompt

{job.get("prompt", "")}

## Error

```
{error_msg}

{trace_block}
```
{timing_block}
"""


def _find_latest_cron_session_log(job_id: str) -> Optional[Path]:
    """Return the newest saved session log for a cron job, if present."""
    sessions_dir = _hermes_home / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = sorted(
        sessions_dir.glob(f"session_cron_{job_id}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_tool_events_from_session(session_path: Path) -> list[dict]:
    """Load structured tool timing events from a session log file."""
    try:
        with open(session_path, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
        events = data.get("tool_events")
        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict)]
    except Exception:
        return []
    return []


def _format_tool_timing_block(tool_events: list[dict], session_path: Optional[Path] = None) -> str:
    """Build a compact markdown timing section from tool events."""
    if not tool_events and not session_path:
        return ""

    lines = ["", "## Timing"]
    if session_path:
        lines.append("")
        lines.append(f"**Session Log:** `{session_path}`")

    if not tool_events:
        lines.append("")
        lines.append("No structured tool timing events were available.")
        return "\n".join(lines)

    total = sum(float(e.get("duration_seconds") or 0.0) for e in tool_events)
    lines.append("")
    lines.append(f"**Tool Calls:** {len(tool_events)}")
    lines.append(f"**Tracked Tool Time:** {total:.2f}s")
    lines.append("")
    lines.append("| # | Tool | Duration | Preview |")
    lines.append("|---|------|----------|---------|")
    ranked = sorted(
        enumerate(tool_events, start=1),
        key=lambda item: float(item[1].get("duration_seconds") or 0.0),
        reverse=True,
    )
    for idx, event in ranked[:10]:
        tool_name = str(event.get("tool_name") or "?").replace("|", "\\|")
        duration = float(event.get("duration_seconds") or 0.0)
        preview = str(event.get("args_preview") or "").replace("\n", " ").replace("|", "\\|").strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."
        lines.append(f"| {idx} | `{tool_name}` | {duration:.2f}s | {preview or '-'} |")
    return "\n".join(lines)


def _format_latest_session_timing_block(job_id: str) -> str:
    """Build a timing section from the newest session log for this cron job."""
    session_path = _find_latest_cron_session_log(job_id)
    if not session_path:
        return ""
    tool_events = _load_tool_events_from_session(session_path)
    return _format_tool_timing_block(tool_events, session_path=session_path)


def _run_job_worker(job: dict, conn) -> None:
    """
    Execute run_job() in a child process and send the result through a pipe.

    Keeping job execution out-of-process lets the scheduler forcibly terminate
    stuck jobs and release the tick lock.
    """
    try:
        payload = run_job(job)
    except BaseException as exc:  # pragma: no cover - defensive guard
        payload = (
            False,
            _build_job_failure_output(job, f"{type(exc).__name__}: {exc}", traceback.format_exc()),
            "",
            f"{type(exc).__name__}: {exc}",
        )
    try:
        conn.send(payload)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _run_job_with_timeout(job: dict, timeout_seconds: int) -> tuple[bool, str, str, Optional[str]]:
    """
    Run a cron job with timeout protection.

    If timeout_seconds <= 0, runs inline without timeout.
    """
    if timeout_seconds <= 0:
        return run_job(job)

    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_run_job_worker,
        args=(job, child_conn),
        daemon=True,
        name=f"cron-job-{job.get('id', 'unknown')}",
    )

    proc.start()
    child_conn.close()
    try:
        if parent_conn.poll(timeout_seconds):
            result = parent_conn.recv()
            proc.join(timeout=5)
            return result

        timeout_msg = (
            f"TimeoutError: Cron job exceeded {timeout_seconds}s "
            f"(job_id={job.get('id', 'unknown')})"
        )
        logger.error(timeout_msg)
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            try:
                proc.kill()
            except Exception:
                pass
            proc.join(timeout=2)
        return False, _build_job_failure_output(job, timeout_msg), "", timeout_msg
    finally:
        try:
            parent_conn.close()
        except Exception:
            pass


def _resolve_origin(job: dict) -> Optional[dict]:
    """Extract origin info from a job, returning {platform, chat_id, chat_name} or None."""
    origin = job.get("origin")
    if not origin:
        return None
    platform = origin.get("platform")
    chat_id = origin.get("chat_id")
    if platform and chat_id:
        return origin
    return None


def _resolve_cron_model(provider: Optional[str]) -> str:
    """Resolve cron runtime model after provider selection."""
    from hermes_cli.runtime_provider import normalize_model_for_runtime

    model = os.getenv("HERMES_MODEL") or os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    if model:
        return normalize_model_for_runtime(model.strip(), provider, default_model=_DEFAULT_MODEL)

    try:
        import yaml

        cfg_path = _hermes_home / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            model_cfg = cfg.get("model", {})
            if isinstance(model_cfg, str) and model_cfg.strip():
                return normalize_model_for_runtime(model_cfg.strip(), provider, default_model=_DEFAULT_MODEL)
            if isinstance(model_cfg, dict):
                default_model = str(model_cfg.get("default") or "").strip()
                if default_model:
                    return normalize_model_for_runtime(default_model, provider, default_model=_DEFAULT_MODEL)
    except Exception:
        pass

    return normalize_model_for_runtime(_DEFAULT_MODEL, provider, default_model=_DEFAULT_MODEL)


def _deliver_result(job: dict, content: str) -> None:
    """
    Deliver job output to the configured target (origin chat, specific platform, etc.).

    Uses the standalone platform send functions from send_message_tool so delivery
    works whether or not the gateway is running.
    """
    deliver = job.get("deliver", "local")
    origin = _resolve_origin(job)

    if deliver == "local":
        return

    # Resolve target platform + chat_id
    if deliver == "origin":
        if not origin:
            logger.warning("Job '%s' deliver=origin but no origin stored, skipping delivery", job["id"])
            return
        platform_name = origin["platform"]
        chat_id = origin["chat_id"]
    elif ":" in deliver:
        platform_name, chat_id = deliver.split(":", 1)
    else:
        # Bare platform name like "telegram" — need to resolve to origin or home channel
        platform_name = deliver
        if origin and origin.get("platform") == platform_name:
            chat_id = origin["chat_id"]
        else:
            # Fall back to home channel
            chat_id = os.getenv(f"{platform_name.upper()}_HOME_CHANNEL", "")
            if not chat_id:
                logger.warning("Job '%s' deliver=%s but no chat_id or home channel. Set via: hermes config set %s_HOME_CHANNEL <channel_id>", job["id"], deliver, platform_name.upper())
                return

    from tools.send_message_tool import _send_to_platform
    from gateway.config import load_gateway_config, Platform

    platform_map = {
        "telegram": Platform.TELEGRAM,
        "discord": Platform.DISCORD,
        "slack": Platform.SLACK,
        "whatsapp": Platform.WHATSAPP,
    }
    platform = platform_map.get(platform_name.lower())
    if not platform:
        logger.warning("Job '%s': unknown platform '%s' for delivery", job["id"], platform_name)
        return

    try:
        config = load_gateway_config()
    except Exception as e:
        logger.error("Job '%s': failed to load gateway config for delivery: %s", job["id"], e)
        return

    pconfig = config.platforms.get(platform)
    if not pconfig or not pconfig.enabled:
        logger.warning("Job '%s': platform '%s' not configured/enabled", job["id"], platform_name)
        return

    # Run the async send in a fresh event loop (safe from any thread)
    try:
        result = asyncio.run(_send_to_platform(platform, pconfig, chat_id, content))
    except RuntimeError:
        # asyncio.run() fails if there's already a running loop in this thread;
        # spin up a new thread to avoid that.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _send_to_platform(platform, pconfig, chat_id, content))
            result = future.result(timeout=30)
    except Exception as e:
        logger.error("Job '%s': delivery to %s:%s failed: %s", job["id"], platform_name, chat_id, e)
        return

    if result and result.get("error"):
        logger.error("Job '%s': delivery error: %s", job["id"], result["error"])
    else:
        logger.info("Job '%s': delivered to %s:%s", job["id"], platform_name, chat_id)
        # Mirror the delivered content into the target's gateway session
        try:
            from gateway.mirror import mirror_to_session
            mirror_to_session(platform_name, chat_id, content, source_label="cron")
        except Exception:
            pass


def run_job(job: dict, tool_progress_callback=None) -> tuple[bool, str, str, Optional[str]]:
    """
    Execute a single cron job.
    
    Returns:
        Tuple of (success, full_output_doc, final_response, error_message)
    """
    from run_agent import AIAgent
    
    job_id = job["id"]
    job_name = job["name"]
    prompt = job["prompt"]
    origin = _resolve_origin(job)
    
    logger.info("Running job '%s' (ID: %s)", job_name, job_id)
    logger.info("Prompt: %s", prompt[:100])

    # Inject origin context so the agent's send_message tool knows the chat
    if origin:
        os.environ["HERMES_SESSION_PLATFORM"] = origin["platform"]
        os.environ["HERMES_SESSION_CHAT_ID"] = str(origin["chat_id"])
        if origin.get("chat_name"):
            os.environ["HERMES_SESSION_CHAT_NAME"] = origin["chat_name"]

    try:
        # Re-read .env and config.yaml fresh every run so provider/key
        # changes take effect without a gateway restart.
        load_dotenv_with_fallback(_hermes_home / ".env", override=True, logger=logger)

        from hermes_cli.runtime_provider import (
            resolve_runtime_provider,
            format_runtime_provider_error,
        )
        try:
            runtime = resolve_runtime_provider(
                requested=os.getenv("HERMES_INFERENCE_PROVIDER"),
            )
        except Exception as exc:
            message = format_runtime_provider_error(exc)
            raise RuntimeError(message) from exc

        model = _resolve_cron_model(runtime.get("provider"))

        agent = AIAgent(
            model=model,
            api_key=runtime.get("api_key"),
            base_url=runtime.get("base_url"),
            provider=runtime.get("provider"),
            api_mode=runtime.get("api_mode"),
            quiet_mode=True,
            tool_progress_callback=tool_progress_callback,
            session_id=f"cron_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        result = agent.run_conversation(prompt)
        
        final_response = result.get("final_response", "")
        if not final_response:
            final_response = "(No response generated)"
        session_log_file = result.get("session_log_file") or str(agent.session_log_file)
        tool_events = result.get("tool_events") or []
        timing_block = _format_tool_timing_block(
            tool_events,
            session_path=Path(session_log_file) if session_log_file else None,
        )
        
        output = f"""# Cron Job: {job_name}

**Job ID:** {job_id}
**Run Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Schedule:** {job.get('schedule_display', 'N/A')}

## Prompt

{prompt}

## Response

{final_response}
{timing_block}
"""
        
        logger.info("Job '%s' completed successfully", job_name)
        return True, output, final_response, None
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error("Job '%s' failed: %s", job_name, error_msg)
        
        output = f"""# Cron Job: {job_name} (FAILED)

**Job ID:** {job_id}
**Run Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Schedule:** {job.get('schedule_display', 'N/A')}

## Prompt

{prompt}

## Error

```
{error_msg}

{traceback.format_exc()}
```
"""
        return False, output, "", error_msg

    finally:
        # Clean up injected env vars so they don't leak to other jobs
        for key in ("HERMES_SESSION_PLATFORM", "HERMES_SESSION_CHAT_ID", "HERMES_SESSION_CHAT_NAME"):
            os.environ.pop(key, None)


def tick(verbose: bool = True) -> int:
    """
    Check and run all due jobs.
    
    Uses a file lock so only one tick runs at a time, even if the gateway's
    in-process ticker and a standalone daemon or manual tick overlap.
    
    Args:
        verbose: Whether to print status messages
    
    Returns:
        Number of jobs executed (0 if another tick is already running)
    """
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)

    # Cross-platform file locking: fcntl on Unix, msvcrt on Windows
    lock_fd = None
    try:
        lock_fd = open(_LOCK_FILE, "w", encoding="utf-8")
        if fcntl:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif msvcrt:
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
    except (OSError, IOError):
        logger.debug("Tick skipped — another instance holds the lock")
        if lock_fd is not None:
            lock_fd.close()
        return 0

    try:
        due_jobs = get_due_jobs()
        job_timeout_seconds = _resolve_cron_job_timeout_seconds()

        if verbose and not due_jobs:
            logger.info("%s - No jobs due", datetime.now().strftime('%H:%M:%S'))
            return 0

        if verbose:
            logger.info("%s - %s job(s) due", datetime.now().strftime('%H:%M:%S'), len(due_jobs))

        executed = 0
        for job in due_jobs:
            try:
                job_name = job.get("name", job["id"])
                started_at_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _deliver_result(
                    job,
                    (
                        f"⏳ Cron job starting\n"
                        f"Name: {job_name}\n"
                        f"ID: {job['id']}\n"
                        f"Started: {started_at_human}"
                    ),
                )

                started_at = time.monotonic()
                success, output, final_response, error = _run_job_with_timeout(job, job_timeout_seconds)
                elapsed_s = int(max(0, time.monotonic() - started_at))

                output_file = save_job_output(job["id"], output)
                if verbose:
                    logger.info("Output saved to: %s", output_file)

                # Deliver the final response to the origin/target chat
                deliver_content = final_response if success else f"⚠️ Cron job '{job.get('name', job['id'])}' failed:\n{error}"
                if deliver_content:
                    try:
                        _deliver_result(job, deliver_content)
                    except Exception as de:
                        logger.error("Delivery failed for job %s: %s", job["id"], de)

                status_msg = (
                    f"✅ Cron job completed\n"
                    f"Name: {job_name}\n"
                    f"ID: {job['id']}\n"
                    f"Duration: {elapsed_s}s\n"
                    f"Output: {output_file}"
                ) if success else (
                    f"❌ Cron job failed\n"
                    f"Name: {job_name}\n"
                    f"ID: {job['id']}\n"
                    f"Duration: {elapsed_s}s\n"
                    f"Error: {error}\n"
                    f"Output: {output_file}"
                )
                try:
                    _deliver_result(job, status_msg)
                except Exception as de:
                    logger.error("Status delivery failed for job %s: %s", job["id"], de)

                mark_job_run(job["id"], success, error)
                executed += 1

            except Exception as e:
                logger.error("Error processing job %s: %s", job['id'], e)
                mark_job_run(job["id"], False, str(e))

        return executed
    finally:
        if fcntl:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        elif msvcrt:
            try:
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass
        lock_fd.close()


if __name__ == "__main__":
    tick(verbose=True)
