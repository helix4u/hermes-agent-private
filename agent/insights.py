"""
Session insights for Hermes Agent.

Reads historical session data from the SQLite state database and produces
usage summaries across sessions, models, platforms, tools, and activity
patterns. Unknown or custom models intentionally default to zero estimated
cost so we never invent pricing for self-hosted or custom endpoints.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional


MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4.5-preview": {"input": 75.00, "output": 150.00},
    "gpt-5": {"input": 10.00, "output": 30.00},
    "gpt-5.4": {"input": 10.00, "output": 30.00},
    "o3": {"input": 10.00, "output": 40.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "llama-4-maverick": {"input": 0.50, "output": 0.70},
    "llama-4-scout": {"input": 0.20, "output": 0.30},
}

_DEFAULT_PRICING = {"input": 0.0, "output": 0.0}


def _get_pricing(model_name: str) -> Dict[str, float]:
    if not model_name:
        return _DEFAULT_PRICING

    bare = model_name.split("/")[-1].lower()
    if bare in MODEL_PRICING:
        return MODEL_PRICING[bare]

    best_match = None
    best_len = 0
    for key, price in MODEL_PRICING.items():
        if bare.startswith(key) and len(key) > best_len:
            best_match = price
            best_len = len(key)
    if best_match:
        return best_match

    if "opus" in bare:
        return {"input": 15.00, "output": 75.00}
    if "sonnet" in bare:
        return {"input": 3.00, "output": 15.00}
    if "haiku" in bare:
        return {"input": 0.80, "output": 4.00}
    if "gpt-4o-mini" in bare:
        return {"input": 0.15, "output": 0.60}
    if "gpt-4o" in bare:
        return {"input": 2.50, "output": 10.00}
    if "gpt-5" in bare:
        return {"input": 10.00, "output": 30.00}
    if "deepseek" in bare:
        return {"input": 0.14, "output": 0.28}
    if "gemini" in bare:
        return {"input": 0.15, "output": 0.60}

    return _DEFAULT_PRICING


def _has_known_pricing(model_name: str) -> bool:
    return _get_pricing(model_name) is not _DEFAULT_PRICING


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _get_pricing(model)
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = minutes / 60
    if hours < 24:
        remaining_min = int(minutes % 60)
        return f"{int(hours)}h {remaining_min}m" if remaining_min else f"{int(hours)}h"
    return f"{hours / 24:.1f}d"


def _bar_chart(values: List[int], max_width: int = 20) -> List[str]:
    peak = max(values) if values else 1
    if peak <= 0:
        return ["" for _ in values]
    return ["#" * max(1, int(v / peak * max_width)) if v > 0 else "" for v in values]


class InsightsEngine:
    """Generate usage insights from the Hermes SQLite session database."""

    _SESSION_COLS = (
        "id, source, user_id, model, started_at, ended_at, "
        "message_count, tool_call_count, input_tokens, output_tokens"
    )

    def __init__(self, db: Any):
        self.db = db
        self._conn = db._conn

    def generate(self, days: int = 30, source: Optional[str] = None) -> Dict[str, Any]:
        days = max(int(days or 30), 1)
        cutoff = time.time() - (days * 86400)

        sessions = self._get_sessions(cutoff, source)
        tool_usage = self._get_tool_usage(cutoff, source)
        message_stats = self._get_message_stats(cutoff, source)

        if not sessions:
            return {
                "days": days,
                "source_filter": source,
                "empty": True,
                "overview": {},
                "models": [],
                "platforms": [],
                "tools": [],
                "activity": {},
                "top_sessions": [],
            }

        overview = self._compute_overview(sessions, message_stats)
        models = self._compute_model_breakdown(sessions)
        platforms = self._compute_platform_breakdown(sessions)
        tools = self._compute_tool_breakdown(tool_usage)
        activity = self._compute_activity_patterns(sessions)
        top_sessions = self._compute_top_sessions(sessions)

        return {
            "days": days,
            "source_filter": source,
            "empty": False,
            "generated_at": time.time(),
            "overview": overview,
            "models": models,
            "platforms": platforms,
            "tools": tools,
            "activity": activity,
            "top_sessions": top_sessions,
        }

    @staticmethod
    def _normalize_source_name(source: str, user_id: str = "") -> str:
        raw_source = str(source or "").strip().lower() or "unknown"
        raw_user_id = str(user_id or "").strip().lower()
        if raw_source == "local" and raw_user_id == "local-browser":
            return "browser-sidecar"
        return raw_source

    def _build_source_filter_sql(
        self,
        source: Optional[str],
        *,
        session_alias: str = "sessions",
    ) -> tuple[str, tuple[Any, ...]]:
        normalized = str(source or "").strip().lower()
        session_ref = session_alias
        if not normalized:
            return "", ()
        if normalized in {"browser-sidecar", "browser_sidecar", "sidecar", "browser"}:
            return f" AND {session_ref}.source = ? AND {session_ref}.user_id = ?", ("local", "local-browser")
        if normalized == "local":
            return f" AND {session_ref}.source = ? AND ({session_ref}.user_id IS NULL OR {session_ref}.user_id != ?)", ("local", "local-browser")
        return f" AND {session_ref}.source = ?", (normalized,)

    def _get_sessions(self, cutoff: float, source: Optional[str] = None) -> List[Dict[str, Any]]:
        where_sql, params = self._build_source_filter_sql(source)
        cursor = self._conn.execute(
            f"""SELECT {self._SESSION_COLS} FROM sessions
                WHERE started_at >= ?{where_sql}
                ORDER BY started_at DESC""",
            (cutoff, *params),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_tool_usage(self, cutoff: float, source: Optional[str] = None) -> List[Dict[str, Any]]:
        tool_counts: Counter[str] = Counter()
        where_sql, params = self._build_source_filter_sql(source, session_alias="s")
        cursor = self._conn.execute(
            f"""SELECT m.tool_name, COUNT(*) AS count
               FROM messages m
               JOIN sessions s ON s.id = m.session_id
               WHERE s.started_at >= ?{where_sql}
                 AND m.role = 'tool' AND m.tool_name IS NOT NULL
               GROUP BY m.tool_name
               ORDER BY count DESC""",
            (cutoff, *params),
        )
        for row in cursor.fetchall():
            tool_counts[row["tool_name"]] += row["count"]

        cursor = self._conn.execute(
            f"""SELECT m.tool_calls
               FROM messages m
               JOIN sessions s ON s.id = m.session_id
               WHERE s.started_at >= ?{where_sql}
                 AND m.role = 'assistant' AND m.tool_calls IS NOT NULL""",
            (cutoff, *params),
        )

        tool_calls_counts: Counter[str] = Counter()
        for row in cursor.fetchall():
            try:
                calls = row["tool_calls"]
                if isinstance(calls, str):
                    calls = json.loads(calls)
                if isinstance(calls, list):
                    for call in calls:
                        func = call.get("function", {}) if isinstance(call, dict) else {}
                        name = func.get("name")
                        if name:
                            tool_calls_counts[name] += 1
            except (AttributeError, json.JSONDecodeError, TypeError):
                continue

        if not tool_counts and tool_calls_counts:
            tool_counts = tool_calls_counts
        elif tool_counts and tool_calls_counts:
            merged: Counter[str] = Counter()
            for tool in set(tool_counts) | set(tool_calls_counts):
                merged[tool] = max(tool_counts.get(tool, 0), tool_calls_counts.get(tool, 0))
            tool_counts = merged

        return [{"tool_name": name, "count": count} for name, count in tool_counts.most_common()]

    def _get_message_stats(self, cutoff: float, source: Optional[str] = None) -> Dict[str, int]:
        where_sql, params = self._build_source_filter_sql(source, session_alias="s")
        cursor = self._conn.execute(
            f"""SELECT
                 COUNT(*) AS total_messages,
                 SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) AS user_messages,
                 SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) AS assistant_messages,
                 SUM(CASE WHEN m.role = 'tool' THEN 1 ELSE 0 END) AS tool_messages
               FROM messages m
               JOIN sessions s ON s.id = m.session_id
               WHERE s.started_at >= ?{where_sql}""",
            (cutoff, *params),
        )
        row = cursor.fetchone()
        return dict(row) if row else {
            "total_messages": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_messages": 0,
        }

    def _compute_overview(self, sessions: List[Dict[str, Any]], message_stats: Dict[str, int]) -> Dict[str, Any]:
        total_input = sum(s.get("input_tokens") or 0 for s in sessions)
        total_output = sum(s.get("output_tokens") or 0 for s in sessions)
        total_tokens = total_input + total_output
        total_tool_calls = sum(s.get("tool_call_count") or 0 for s in sessions)
        total_messages = sum(s.get("message_count") or 0 for s in sessions)

        total_cost = 0.0
        models_with_pricing = set()
        models_without_pricing = set()
        for session in sessions:
            model = str(session.get("model") or "")
            inp = session.get("input_tokens") or 0
            out = session.get("output_tokens") or 0
            total_cost += _estimate_cost(model, inp, out)
            display = model.split("/")[-1] if "/" in model else (model or "unknown")
            if _has_known_pricing(model):
                models_with_pricing.add(display)
            else:
                models_without_pricing.add(display)

        durations = []
        for session in sessions:
            start = session.get("started_at")
            end = session.get("ended_at")
            if start and end and end > start:
                durations.append(end - start)

        started_timestamps = [s["started_at"] for s in sessions if s.get("started_at")]
        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "total_tool_calls": total_tool_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "total_hours": (sum(durations) / 3600) if durations else 0,
            "avg_session_duration": (sum(durations) / len(durations)) if durations else 0,
            "avg_messages_per_session": (total_messages / len(sessions)) if sessions else 0,
            "avg_tokens_per_session": (total_tokens / len(sessions)) if sessions else 0,
            "user_messages": message_stats.get("user_messages") or 0,
            "assistant_messages": message_stats.get("assistant_messages") or 0,
            "tool_messages": message_stats.get("tool_messages") or 0,
            "date_range_start": min(started_timestamps) if started_timestamps else None,
            "date_range_end": max(started_timestamps) if started_timestamps else None,
            "models_with_pricing": sorted(models_with_pricing),
            "models_without_pricing": sorted(models_without_pricing),
            "browser_sidecar_sessions": sum(
                1
                for session in sessions
                if self._normalize_source_name(session.get("source", ""), session.get("user_id", "")) == "browser-sidecar"
            ),
        }

    def _compute_model_breakdown(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        model_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "sessions": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "tool_calls": 0,
                "cost": 0.0,
            }
        )
        for session in sessions:
            model = str(session.get("model") or "unknown")
            display_model = model.split("/")[-1] if "/" in model else model
            entry = model_data[display_model]
            entry["sessions"] += 1
            inp = session.get("input_tokens") or 0
            out = session.get("output_tokens") or 0
            entry["input_tokens"] += inp
            entry["output_tokens"] += out
            entry["total_tokens"] += inp + out
            entry["tool_calls"] += session.get("tool_call_count") or 0
            entry["cost"] += _estimate_cost(model, inp, out)
            entry["has_pricing"] = _has_known_pricing(model)

        result = [{"model": model, **data} for model, data in model_data.items()]
        result.sort(key=lambda item: (item["total_tokens"], item["sessions"]), reverse=True)
        return result

    def _compute_platform_breakdown(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        platform_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "sessions": 0,
                "messages": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "tool_calls": 0,
            }
        )
        for session in sessions:
            source = self._normalize_source_name(session.get("source", ""), session.get("user_id", ""))
            entry = platform_data[source]
            entry["sessions"] += 1
            entry["messages"] += session.get("message_count") or 0
            inp = session.get("input_tokens") or 0
            out = session.get("output_tokens") or 0
            entry["input_tokens"] += inp
            entry["output_tokens"] += out
            entry["total_tokens"] += inp + out
            entry["tool_calls"] += session.get("tool_call_count") or 0

        result = [{"platform": platform, **data} for platform, data in platform_data.items()]
        result.sort(key=lambda item: item["sessions"], reverse=True)
        return result

    def _compute_tool_breakdown(self, tool_usage: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        total_calls = sum(tool["count"] for tool in tool_usage) if tool_usage else 0
        result = []
        for tool in tool_usage:
            percentage = (tool["count"] / total_calls * 100) if total_calls else 0
            result.append({
                "tool": tool["tool_name"],
                "count": tool["count"],
                "percentage": percentage,
            })
        return result

    def _compute_activity_patterns(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        day_counts: Counter[int] = Counter()
        hour_counts: Counter[int] = Counter()
        daily_counts: Counter[str] = Counter()

        for session in sessions:
            ts = session.get("started_at")
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts)
            day_counts[dt.weekday()] += 1
            hour_counts[dt.hour] += 1
            daily_counts[dt.strftime("%Y-%m-%d")] += 1

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_breakdown = [{"day": day_names[i], "count": day_counts.get(i, 0)} for i in range(7)]
        hour_breakdown = [{"hour": i, "count": hour_counts.get(i, 0)} for i in range(24)]

        max_streak = 0
        if daily_counts:
            all_dates = sorted(daily_counts.keys())
            current_streak = 1
            max_streak = 1
            for index in range(1, len(all_dates)):
                previous = datetime.strptime(all_dates[index - 1], "%Y-%m-%d")
                current = datetime.strptime(all_dates[index], "%Y-%m-%d")
                if (current - previous).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1

        return {
            "by_day": day_breakdown,
            "by_hour": hour_breakdown,
            "busiest_day": max(day_breakdown, key=lambda item: item["count"]) if day_breakdown else None,
            "busiest_hour": max(hour_breakdown, key=lambda item: item["count"]) if hour_breakdown else None,
            "active_days": len(daily_counts),
            "max_streak": max_streak,
        }

    def _compute_top_sessions(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        top = []

        sessions_with_duration = [s for s in sessions if s.get("started_at") and s.get("ended_at")]
        if sessions_with_duration:
            longest = max(sessions_with_duration, key=lambda s: (s["ended_at"] - s["started_at"]))
            top.append({
                "label": "Longest session",
                "session_id": longest["id"][:16],
                "value": _format_duration(longest["ended_at"] - longest["started_at"]),
                "date": datetime.fromtimestamp(longest["started_at"]).strftime("%b %d"),
            })

        most_messages = max(sessions, key=lambda s: s.get("message_count") or 0)
        if (most_messages.get("message_count") or 0) > 0:
            top.append({
                "label": "Most messages",
                "session_id": most_messages["id"][:16],
                "value": f"{most_messages['message_count']} msgs",
                "date": datetime.fromtimestamp(most_messages["started_at"]).strftime("%b %d") if most_messages.get("started_at") else "?",
            })

        most_tokens = max(
            sessions,
            key=lambda s: (s.get("input_tokens") or 0) + (s.get("output_tokens") or 0),
        )
        token_total = (most_tokens.get("input_tokens") or 0) + (most_tokens.get("output_tokens") or 0)
        if token_total > 0:
            top.append({
                "label": "Most tokens",
                "session_id": most_tokens["id"][:16],
                "value": f"{token_total:,} tokens",
                "date": datetime.fromtimestamp(most_tokens["started_at"]).strftime("%b %d") if most_tokens.get("started_at") else "?",
            })

        most_tools = max(sessions, key=lambda s: s.get("tool_call_count") or 0)
        if (most_tools.get("tool_call_count") or 0) > 0:
            top.append({
                "label": "Most tool calls",
                "session_id": most_tools["id"][:16],
                "value": f"{most_tools['tool_call_count']} calls",
                "date": datetime.fromtimestamp(most_tools["started_at"]).strftime("%b %d") if most_tools.get("started_at") else "?",
            })

        return top

    def format_terminal(self, report: Dict[str, Any]) -> str:
        if report.get("empty"):
            days = report.get("days", 30)
            source = f" (source: {report['source_filter']})" if report.get("source_filter") else ""
            return f"  No sessions found in the last {days} days{source}."

        lines: List[str] = []
        overview = report["overview"]
        days = report["days"]
        source_filter = report.get("source_filter")

        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════════╗")
        lines.append("  ║                    Hermes Insights                      ║")
        period_label = f"Last {days} days"
        if source_filter:
            period_label += f" ({source_filter})"
        padding = 58 - len(period_label) - 2
        left_pad = max(padding // 2, 0)
        right_pad = max(padding - left_pad, 0)
        lines.append(f"  ║{' ' * left_pad} {period_label} {' ' * right_pad}║")
        lines.append("  ╚══════════════════════════════════════════════════════════╝")
        lines.append("")

        if overview.get("date_range_start") and overview.get("date_range_end"):
            start_str = datetime.fromtimestamp(overview["date_range_start"]).strftime("%b %d, %Y")
            end_str = datetime.fromtimestamp(overview["date_range_end"]).strftime("%b %d, %Y")
            lines.append(f"  Period: {start_str} -- {end_str}")
            lines.append("")

        lines.append("  Overview")
        lines.append("  " + "-" * 56)
        lines.append(f"  Sessions:          {overview['total_sessions']:<12}  Messages:        {overview['total_messages']:,}")
        lines.append(f"  Tool calls:        {overview['total_tool_calls']:<12,}  User messages:   {overview['user_messages']:,}")
        lines.append(f"  Input tokens:      {overview['total_input_tokens']:<12,}  Output tokens:   {overview['total_output_tokens']:,}")
        cost_str = f"${overview['estimated_cost']:.2f}"
        if overview.get("models_without_pricing"):
            cost_str += " *"
        lines.append(f"  Total tokens:      {overview['total_tokens']:<12,}  Est. cost:       {cost_str}")
        if overview["total_hours"] > 0:
            lines.append(
                f"  Active time:       ~{_format_duration(overview['total_hours'] * 3600):<11}"
                f"  Avg session:     ~{_format_duration(overview['avg_session_duration'])}"
            )
        if overview.get("browser_sidecar_sessions"):
            lines.append(f"  Browser sidecar:   {overview['browser_sidecar_sessions']:<12}  sessions")
        lines.append(f"  Avg msgs/session:  {overview['avg_messages_per_session']:.1f}")
        lines.append("")

        if report["models"]:
            lines.append("  Models Used")
            lines.append("  " + "-" * 56)
            lines.append(f"  {'Model':<30} {'Sessions':>8} {'Tokens':>12} {'Cost':>8}")
            for model in report["models"]:
                model_name = model["model"][:28]
                cost_cell = f"${model['cost']:>6.2f}" if model.get("has_pricing") else "     N/A"
                lines.append(f"  {model_name:<30} {model['sessions']:>8} {model['total_tokens']:>12,} {cost_cell}")
            if overview.get("models_without_pricing"):
                lines.append("  * Cost N/A for custom/self-hosted models")
            lines.append("")

        if len(report["platforms"]) > 1 or (report["platforms"] and report["platforms"][0]["platform"] != "cli"):
            lines.append("  Platforms")
            lines.append("  " + "-" * 56)
            lines.append(f"  {'Platform':<14} {'Sessions':>8} {'Messages':>10} {'Tokens':>14}")
            for platform in report["platforms"]:
                lines.append(
                    f"  {platform['platform']:<14} {platform['sessions']:>8} "
                    f"{platform['messages']:>10,} {platform['total_tokens']:>14,}"
                )
            lines.append("")

        if report["tools"]:
            lines.append("  Top Tools")
            lines.append("  " + "-" * 56)
            lines.append(f"  {'Tool':<28} {'Calls':>8} {'%':>8}")
            for tool in report["tools"][:15]:
                lines.append(f"  {tool['tool']:<28} {tool['count']:>8,} {tool['percentage']:>7.1f}%")
            if len(report["tools"]) > 15:
                lines.append(f"  ... and {len(report['tools']) - 15} more tools")
            lines.append("")

        activity = report.get("activity", {})
        if activity.get("by_day"):
            lines.append("  Activity Patterns")
            lines.append("  " + "-" * 56)
            day_values = [day["count"] for day in activity["by_day"]]
            bars = _bar_chart(day_values, max_width=15)
            for index, day in enumerate(activity["by_day"]):
                lines.append(f"  {day['day']}  {bars[index]:<15} {day['count']}")
            lines.append("")

            busy_hours = sorted(activity["by_hour"], key=lambda item: item["count"], reverse=True)
            busy_hours = [hour for hour in busy_hours if hour["count"] > 0][:5]
            if busy_hours:
                labels = []
                for hour in busy_hours:
                    raw_hour = hour["hour"]
                    ampm = "AM" if raw_hour < 12 else "PM"
                    display_hour = raw_hour % 12 or 12
                    labels.append(f"{display_hour}{ampm} ({hour['count']})")
                lines.append(f"  Peak hours: {', '.join(labels)}")
            if activity.get("active_days"):
                lines.append(f"  Active days: {activity['active_days']}")
            if activity.get("max_streak", 0) > 1:
                lines.append(f"  Best streak: {activity['max_streak']} consecutive days")
            lines.append("")

        if report.get("top_sessions"):
            lines.append("  Notable Sessions")
            lines.append("  " + "-" * 56)
            for session in report["top_sessions"]:
                lines.append(
                    f"  {session['label']:<20} {session['value']:<18} "
                    f"({session['date']}, {session['session_id']})"
                )
            lines.append("")

        return "\n".join(lines)

    def format_gateway(self, report: Dict[str, Any]) -> str:
        if report.get("empty"):
            days = report.get("days", 30)
            source = report.get("source_filter")
            suffix = f" for `{source}`" if source else ""
            return f"No sessions found in the last {days} days{suffix}."

        lines: List[str] = []
        overview = report["overview"]
        days = report["days"]
        source = report.get("source_filter")
        header = f"📊 **Hermes Insights** — Last {days} days"
        if source:
            header += f" (`{source}`)"
        lines.append(header)
        lines.append("")
        lines.append(
            f"**Sessions:** {overview['total_sessions']} | **Messages:** {overview['total_messages']:,} "
            f"| **Tool calls:** {overview['total_tool_calls']:,}"
        )
        if overview.get("browser_sidecar_sessions"):
            lines.append(f"**Browser sidecar sessions:** {overview['browser_sidecar_sessions']}")
        lines.append(
            f"**Tokens:** {overview['total_tokens']:,} "
            f"(in: {overview['total_input_tokens']:,} / out: {overview['total_output_tokens']:,})"
        )
        cost_note = " _(excludes custom/self-hosted models)_" if overview.get("models_without_pricing") else ""
        lines.append(f"**Est. cost:** ${overview['estimated_cost']:.2f}{cost_note}")
        if overview["total_hours"] > 0:
            lines.append(
                f"**Active time:** ~{_format_duration(overview['total_hours'] * 3600)} "
                f"| **Avg session:** ~{_format_duration(overview['avg_session_duration'])}"
            )
        lines.append("")

        if report["models"]:
            lines.append("**Models:**")
            for model in report["models"][:5]:
                cost = f"${model['cost']:.2f}" if model.get("has_pricing") else "N/A"
                lines.append(
                    f"  {model['model'][:25]} — {model['sessions']} sessions, "
                    f"{model['total_tokens']:,} tokens, {cost}"
                )
            lines.append("")

        if len(report["platforms"]) > 1:
            lines.append("**Platforms:**")
            for platform in report["platforms"]:
                lines.append(f"  {platform['platform']} — {platform['sessions']} sessions, {platform['messages']:,} msgs")
            lines.append("")

        if report["tools"]:
            lines.append("**Top Tools:**")
            for tool in report["tools"][:8]:
                lines.append(f"  {tool['tool']} — {tool['count']:,} calls ({tool['percentage']:.1f}%)")
            lines.append("")

        activity = report.get("activity", {})
        if activity.get("busiest_day") and activity.get("busiest_hour"):
            hour = activity["busiest_hour"]["hour"]
            ampm = "AM" if hour < 12 else "PM"
            display_hour = hour % 12 or 12
            lines.append(
                f"**Busiest:** {activity['busiest_day']['day']}s ({activity['busiest_day']['count']} sessions), "
                f"{display_hour}{ampm} ({activity['busiest_hour']['count']} sessions)"
            )
            if activity.get("active_days"):
                lines.append(f"**Active days:** {activity['active_days']}")
            if activity.get("max_streak", 0) > 1:
                lines.append(f"**Best streak:** {activity['max_streak']} consecutive days")

        return "\n".join(lines)
