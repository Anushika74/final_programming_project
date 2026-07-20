"""Natural-language AI Assistant — the central intelligence layer of SystemIQ.

The assistant recognises the user's intent, then reasons over a single
consolidated `SystemContext` (built by `SystemContextService`) that combines
software metrics, hardware sensors, history, processes, predictions,
recommendations, alerts and logs. It behaves like an experienced system
administrator: it performs root-cause analysis and answers in plain language
rather than echoing raw numbers.

Architecture: the assistant NEVER touches sensors or the database directly — it
only consumes the `SystemContext`. This keeps it a pure reasoning layer.

The intent classifier is rule-based (regex), so the assistant is deterministic,
explainable, offline and free. The `SystemContext` it consumes is fully
JSON-serializable, so an LLM prompt builder can be slotted in later without
changing any of the data-gathering logic.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.schemas.context import SystemContext
from app.schemas.insight import AssistantResponse, OptimizationAction
from app.services.context_service import SystemContextService
from app.services.optimization_service import ACTIONS, optimization_service

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    name: str
    patterns: list[re.Pattern[str]]


def _p(*expressions: str) -> list[re.Pattern[str]]:
    return [re.compile(e, re.I) for e in expressions]


# Intent definitions, evaluated in order (specific first, generic last).
_INTENTS: list[Intent] = [
    Intent("health_summary", _p(
        r"\b(how('?s| is| are)?\s+(my|the)?\s*(system|computer|laptop|pc))\b",
        r"\b(summar(y|ise|ize)|overall health|system health|health (report|score)|is (my|the).*health)\b",
    )),
    Intent("compare", _p(
        r"\b(compare|today.*(vs|versus|than).*yesterday|yesterday.*today|than yesterday|higher than yesterday)\b",
    )),
    Intent("explain_concept", _p(
        r"\b(explain|what('?s| is)|define|meaning of)\b.*\b(thermal throttl|throttl|cpu frequency|clock speed|"
        r"swap( memory| space)?|load average|smart( health)?|fan rpm|rpm|battery cycle|battery health)\b",
    )),
    Intent("why_slow", _p(r"\b(why.*(slow|lag|sluggish|freez|stutter)|is.*(slow|lagging))\b")),
    Intent("will_overheat", _p(
        r"\b(will.*(overheat|too hot|get hot)|overheat.*soon|going to overheat|risk of overheat)\b",
    )),
    Intent("cpu_temp_rising", _p(
        r"\b(why.*(cpu|processor).*(temp|hot|heat|warm)|temperature.*(increas|ris|going up|high)|"
        r"why.*(so )?(hot|warm|heating))\b",
    )),
    Intent("overheating_app", _p(
        r"\b(which|what).*(app|application|program|process).*(overheat|heat|hot|temp|warm)\b",
    )),
    Intent("fan", _p(r"\b(fan)\b")),
    Intent("ssd_health", _p(
        r"\b(ssd|nvme|disk|drive|storage).*(health|healthy|ok|okay|fine|dying|fail)\b",
        r"\bis (my|the) (ssd|disk|drive|storage)\b",
    )),
    Intent("battery_health", _p(
        r"\b(battery).*(health|degrad|dying|wear|cycle|condition|good|bad)\b",
        r"\bis (my|the) battery\b",
    )),
    Intent("what_optimize", _p(
        r"\b(what.*(optimi[sz]e|improve|fix|speed).*(first)?|optimi[sz]e first|"
        r"what should i (do|optimi[sz]e|fix|close))\b",
    )),
    Intent("close_apps", _p(r"\b(should i (close|quit|kill|stop)|what.*(close|quit))\b")),
    Intent("memory_cause", _p(r"\b(what|why).*(causing|using|high|eating).*(memory|ram)\b")),
    Intent("predict_disk", _p(r"\b(predict|forecast|will|run out).*(disk|storage|space)\b")),
    Intent("predict_cpu_temp", _p(r"\b(predict|forecast).*(temp|temperature|thermal)\b")),
    Intent("predict_cpu", _p(r"\b(predict|forecast|will).*(cpu|processor)\b")),
    Intent("predict_memory", _p(r"\b(predict|forecast|will).*(memory|ram)\b")),
    Intent("optimize", _p(r"\b(optimi[sz]e|clean ?up|speed up|free up|tune)\b")),
    Intent("top_memory", _p(r"\b(memory|ram).*(top|most|consum|hungry|heavy|hog)\b|top.*(memory|ram)\b")),
    Intent("top_cpu", _p(r"\b(cpu).*(top|most|consum|heavy|hog)\b|top.*cpu\b")),
    Intent("temp_status", _p(r"\b(temp|temperature|thermal|hot|heat|cooling)\b")),
    Intent("disk_status", _p(r"\b(disk|storage|space)\b")),
    Intent("memory_status", _p(r"\b(memory|ram)\b")),
    Intent("cpu_status", _p(r"\b(cpu|processor|load)\b")),
]

# Beginner-friendly explanations of technical concepts.
_GLOSSARY: dict[str, tuple[tuple[str, ...], str]] = {
    "thermal_throttling": (
        ("thermal throttl", "throttl"),
        "Thermal throttling is when your CPU automatically slows itself down because "
        "it has become too hot. Slowing down produces less heat and protects the chip "
        "from damage — but it also makes the computer feel slower until it cools off.",
    ),
    "cpu_frequency": (
        ("cpu frequency", "clock speed"),
        "CPU frequency (clock speed), measured in GHz, is how many billions of operations "
        "per second the processor can do. Higher means faster, but it also generates more "
        "heat. The CPU raises and lowers this automatically based on load and temperature.",
    ),
    "swap": (
        ("swap memory", "swap space", "swap"),
        "Swap is disk space the system uses as overflow when physical RAM fills up. It "
        "prevents crashes, but disk is far slower than RAM, so heavy swapping makes the "
        "whole computer feel sluggish.",
    ),
    "load_average": (
        ("load average",),
        "Load average is the average number of tasks waiting to run. Compare it to your "
        "CPU core count: a load equal to your cores means fully busy; much higher means "
        "the system is overloaded and tasks are queuing.",
    ),
    "smart": (
        ("smart health", "smart"),
        "S.M.A.R.T. is a self-monitoring system built into drives that reports health "
        "indicators (reallocated sectors, wear, temperature). It helps predict a failing "
        "disk before you lose data.",
    ),
    "fan_rpm": (
        ("fan rpm", "rpm"),
        "Fan RPM (revolutions per minute) is how fast the cooling fan spins. It rises "
        "automatically as temperature increases to remove more heat; a loud fan usually "
        "means the system is working hard or running warm.",
    ),
    "battery_cycle": (
        ("battery cycle", "battery health"),
        "A battery cycle is one full charge-and-discharge. Batteries wear a little with "
        "each cycle, so their maximum capacity (battery health %) slowly drops over time. "
        "Below about 80% you'll notice shorter runtime.",
    ),
}


class NLService:
    """The AI Assistant. Detects intent and reasons over the SystemContext."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.context_service = SystemContextService(db)
        self._handlers: dict[str, Callable[[str, SystemContext], AssistantResponse]] = {
            "health_summary": self._health_summary,
            "why_slow": self._why_slow,
            "cpu_temp_rising": self._cpu_temp_rising,
            "overheating_app": self._overheating_app,
            "will_overheat": self._will_overheat,
            "fan": self._fan,
            "ssd_health": self._ssd_health,
            "battery_health": self._battery_health,
            "what_optimize": self._what_optimize,
            "close_apps": self._close_apps,
            "memory_cause": self._memory_cause,
            "optimize": self._optimize,
            "explain_concept": self._explain_concept,
            "compare": self._compare,
            "predict_cpu": lambda q, c: self._predict(q, c, "cpu"),
            "predict_memory": lambda q, c: self._predict(q, c, "memory"),
            "predict_disk": lambda q, c: self._predict(q, c, "disk"),
            "predict_cpu_temp": lambda q, c: self._predict(q, c, "cpu_temperature"),
            "top_cpu": lambda q, c: self._top(q, c, "cpu"),
            "top_memory": lambda q, c: self._top(q, c, "memory"),
            "temp_status": lambda q, c: self._status(q, c, "temp"),
            "disk_status": lambda q, c: self._status(q, c, "disk"),
            "memory_status": lambda q, c: self._status(q, c, "memory"),
            "cpu_status": lambda q, c: self._status(q, c, "cpu"),
        }

    # Intents that benefit from (more expensive) ML predictions in the context.
    _PREDICTION_INTENTS = {
        "health_summary", "why_slow", "will_overheat", "cpu_temp_rising",
        "predict_cpu", "predict_memory", "predict_disk", "predict_cpu_temp",
    }

    def detect_intent(self, query: str) -> str:
        for intent in _INTENTS:
            if any(p.search(query) for p in intent.patterns):
                return intent.name
        return "health_summary"  # sensible, informative default

    def handle(self, query: str) -> AssistantResponse:
        intent = self.detect_intent(query)
        ctx = self.context_service.build(
            include_predictions=intent in self._PREDICTION_INTENTS
        )
        handler = self._handlers.get(intent, lambda q, c: self._status(q, c, "all"))
        response = handler(query, ctx)
        response.intent = intent
        response.query = query
        response.sources = ctx.sources
        return response

    # ------------------------------------------------------------------ #
    # Root-cause analysis (correlates signals across subsystems)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _root_causes(ctx: SystemContext) -> list[str]:
        causes: list[str] = []
        heavy_cpu = ctx.top_cpu[0] if ctx.top_cpu else None

        if (ctx.cpu_usage or 0) >= 80 and (ctx.cpu_temp or 0) >= 80 and heavy_cpu:
            causes.append(
                f"'{heavy_cpu.name}' is using {heavy_cpu.cpu_usage:.0f}% CPU and is the "
                f"likely driver of both the high CPU load and the rising temperature."
            )
        elif (ctx.cpu_usage or 0) >= 80 and heavy_cpu:
            causes.append(
                f"'{heavy_cpu.name}' ({heavy_cpu.cpu_usage:.0f}% CPU) is the main "
                f"contributor to the high CPU load."
            )

        if (ctx.cpu_temp or 0) >= 85 and ctx.fan_speed_rpm is not None and ctx.fan_speed_rpm < 1500:
            causes.append(
                "The CPU is hot but the fan is spinning slowly — this points to a possible "
                "cooling problem (dust build-up, blocked vents, or a failing fan)."
            )

        if (ctx.disk_usage or 0) >= 50 and (ctx.ssd_temp or 0) >= 60:
            causes.append(
                "Elevated SSD temperature together with disk activity suggests a "
                "disk-intensive workload."
            )

        if (ctx.memory_usage or 0) >= 85:
            causes.append(
                "Memory usage is high, which can force the system to swap to disk and slow "
                "everything down."
            )

        if ctx.throttling:
            causes.append(
                "The CPU is currently thermally throttling (clocking down to cool off), "
                "which directly reduces performance."
            )
        return causes

    @staticmethod
    def _suggested_for(ctx: SystemContext) -> list[OptimizationAction]:
        actions: list[OptimizationAction] = []
        if (ctx.cpu_usage or 0) >= 80 or (ctx.cpu_temp or 0) >= 85:
            actions.append(ACTIONS["optimize_resources"])
        if (ctx.disk_usage or 0) >= 85:
            actions.append(ACTIONS["clean_temp_files"])
        if (ctx.memory_usage or 0) >= 85:
            actions.append(ACTIONS["clear_memory_cache"])
        return actions

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #
    def _health_summary(self, query: str, ctx: SystemContext) -> AssistantResponse:
        issues: list[str] = []
        if (ctx.cpu_temp or 0) >= 85:
            issues.append(f"CPU temperature is high ({ctx.cpu_temp:.0f}°C).")
        if (ctx.cpu_usage or 0) >= 85:
            issues.append(f"CPU usage is high ({ctx.cpu_usage:.0f}%).")
        if (ctx.memory_usage or 0) >= 85:
            issues.append(f"Memory usage is high ({ctx.memory_usage:.0f}%).")
        if (ctx.disk_usage or 0) >= 90:
            issues.append(f"Disk is nearly full ({ctx.disk_usage:.0f}%).")
        if ctx.top_cpu and ctx.top_cpu[0].cpu_usage >= 50:
            issues.append(f"'{ctx.top_cpu[0].name}' is consuming a lot of CPU.")
        if ctx.throttling:
            issues.append("The CPU is thermally throttling.")
        if not issues:
            issues.append("No significant issues detected — everything looks healthy.")

        score = f"{ctx.health_overall:.0f}%" if ctx.health_overall is not None else "n/a"
        lines = [
            f"Overall hardware health: {score} ({ctx.health_rating or 'unknown'}).",
            f"Performance: CPU {ctx.cpu_usage:.0f}%, memory {ctx.memory_usage:.0f}%, "
            f"disk {ctx.disk_usage:.0f}%." if ctx.cpu_usage is not None else "",
        ]
        if ctx.cpu_temp is not None:
            lines.append(f"Thermal: CPU {ctx.cpu_temp:.0f}°C"
                         + (f", fan {ctx.fan_speed_rpm:.0f} RPM" if ctx.fan_speed_rpm else "") + ".")
        if ctx.battery_health is not None:
            lines.append(f"Battery health: {ctx.battery_health:.0f}% of design capacity.")
        lines.append("Detected issues: " + " ".join(issues))

        recs = [r.issue for r in ctx.recommendations[:3]]
        if recs:
            lines.append("Top recommendations: " + "; ".join(recs) + ".")

        return AssistantResponse(
            query=query, intent="health_summary", answer="\n".join(l for l in lines if l),
            data={"health": {"overall": ctx.health_overall, "rating": ctx.health_rating,
                             "components": [c.model_dump() for c in ctx.health_components]},
                  "issues": issues},
            suggested_actions=self._suggested_for(ctx),
        )

    def _why_slow(self, query: str, ctx: SystemContext) -> AssistantResponse:
        causes = self._root_causes(ctx)
        if causes:
            answer = "Your system may feel slow for these reasons:\n- " + "\n- ".join(causes)
        else:
            busiest = ctx.top_cpu[0].name if ctx.top_cpu else "no single process"
            answer = (
                "Your core resources look healthy right now (CPU "
                f"{ctx.cpu_usage:.0f}%, memory {ctx.memory_usage:.0f}%, "
                f"CPU temp {ctx.cpu_temp:.0f}°C). " if ctx.cpu_usage is not None else ""
            ) + f"The busiest process is {busiest}. Any slowness may be transient or app-specific."
        return AssistantResponse(
            query=query, intent="why_slow", answer=answer,
            data={"root_causes": causes, "top_cpu": [p.model_dump() for p in ctx.top_cpu]},
            suggested_actions=self._suggested_for(ctx),
        )

    def _cpu_temp_rising(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if ctx.cpu_temp is None:
            return self._no_sensor(query, "CPU temperature")
        parts = [f"Your CPU is currently {ctx.cpu_temp:.0f}°C"]
        if ctx.cpu_temp_avg_1h is not None:
            trend = "above" if ctx.cpu_temp > ctx.cpu_temp_avg_1h else "around"
            parts.append(f", which is {trend} its last-hour average of {ctx.cpu_temp_avg_1h:.0f}°C")
        parts.append(".")
        if ctx.top_cpu and ctx.top_cpu[0].cpu_usage >= 30:
            parts.append(f" The main heat source is '{ctx.top_cpu[0].name}' "
                         f"({ctx.top_cpu[0].cpu_usage:.0f}% CPU).")
        if ctx.sustained_high_cpu_temp:
            parts.append(" It has stayed above 90°C for several minutes, indicating a "
                         "sustained heavy workload rather than a brief spike.")
        pred = next((p for p in ctx.predictions if p.metric == "cpu_temperature"), None)
        if pred and pred.predicted_peak is not None:
            parts.append(f" Forecast: about {pred.predicted_peak:.0f}°C in the next 10 minutes "
                         f"({pred.risk} risk).")
        return AssistantResponse(
            query=query, intent="cpu_temp_rising", answer="".join(parts),
            data={"cpu_temp": ctx.cpu_temp, "avg_1h": ctx.cpu_temp_avg_1h,
                  "top_cpu": [p.model_dump() for p in ctx.top_cpu[:3]]},
            suggested_actions=self._suggested_for(ctx),
        )

    def _overheating_app(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if not ctx.top_cpu:
            return self._no_sensor(query, "process information")
        worst = ctx.top_cpu[0]
        temp_note = f" while the CPU is at {ctx.cpu_temp:.0f}°C" if ctx.cpu_temp is not None else ""
        answer = (
            f"The application most likely heating your laptop is '{worst.name}' "
            f"(PID {worst.pid}), using {worst.cpu_usage:.0f}% CPU{temp_note}. "
            "Sustained high CPU use is the usual cause of rising temperature. "
            "Closing or pausing it should reduce the thermal load."
        )
        return AssistantResponse(
            query=query, intent="overheating_app", answer=answer,
            data={"culprit": worst.model_dump(), "top_cpu": [p.model_dump() for p in ctx.top_cpu]},
            suggested_actions=[ACTIONS["optimize_resources"]],
        )

    def _will_overheat(self, query: str, ctx: SystemContext) -> AssistantResponse:
        pred = next((p for p in ctx.predictions if p.metric == "cpu_temperature"), None)
        if pred is None or pred.predicted_peak is None:
            base = (f"CPU is currently {ctx.cpu_temp:.0f}°C. "
                    if ctx.cpu_temp is not None else "")
            return AssistantResponse(
                query=query, intent="will_overheat",
                answer=base + "There isn't enough thermal history yet to forecast reliably. "
                "Let the monitor collect more data for an accurate prediction.",
                data={}, suggested_actions=[],
            )
        verdict = {
            "high": "Yes — there is a high risk of overheating soon.",
            "medium": "Possibly — temperatures are trending up; keep an eye on it.",
            "low": "No — temperatures are expected to stay in a safe range.",
        }.get(pred.risk, "")
        answer = f"{verdict} {pred.message}"
        return AssistantResponse(
            query=query, intent="will_overheat", answer=answer,
            data={"prediction": pred.model_dump()},
            suggested_actions=self._suggested_for(ctx) if pred.risk != "low" else [],
        )

    def _fan(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if ctx.fan_speed_rpm is None:
            return self._no_sensor(query, "fan speed")
        if ctx.fan_speed_rpm >= 3000 and (ctx.cpu_temp or 0) >= 75:
            answer = (
                f"The fan is spinning fast ({ctx.fan_speed_rpm:.0f} RPM) because the CPU is "
                f"warm ({ctx.cpu_temp:.0f}°C). This is normal, healthy behaviour — the fan "
                "ramps up to remove heat during heavy workloads. It should quieten once "
                "the load drops."
            )
        elif (ctx.cpu_temp or 0) >= 85 and ctx.fan_speed_rpm < 1500:
            answer = (
                f"The CPU is hot ({ctx.cpu_temp:.0f}°C) but the fan is only at "
                f"{ctx.fan_speed_rpm:.0f} RPM — that's unusual and may indicate a cooling "
                "problem. Check for dust, blocked vents, or a failing fan."
            )
        else:
            answer = (
                f"The fan is at {ctx.fan_speed_rpm:.0f} RPM with the CPU at "
                f"{ctx.cpu_temp:.0f}°C — within normal range." if ctx.cpu_temp is not None
                else f"The fan is at {ctx.fan_speed_rpm:.0f} RPM."
            )
        return AssistantResponse(query=query, intent="fan", answer=answer,
                                 data={"fan_rpm": ctx.fan_speed_rpm, "cpu_temp": ctx.cpu_temp})

    def _ssd_health(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if ctx.ssd_temp is None:
            return AssistantResponse(
                query=query, intent="ssd_health",
                answer="I can't read a drive temperature sensor on this machine, so I can't "
                "assess SSD thermal health directly. Disk usage is "
                f"{ctx.disk_usage:.0f}%." if ctx.disk_usage is not None else
                "I can't read drive sensors on this machine.",
                data={"disk_usage": ctx.disk_usage},
            )
        if ctx.ssd_temp >= 70:
            answer = (f"Your SSD is running hot at {ctx.ssd_temp:.0f}°C. Sustained heat above "
                      "70°C can cause the drive to throttle and shortens its lifespan. Reduce "
                      "heavy disk activity and improve airflow.")
        else:
            answer = (f"Your SSD looks healthy: temperature is {ctx.ssd_temp:.0f}°C (a safe "
                      f"range) and disk usage is {ctx.disk_usage:.0f}%." if ctx.disk_usage
                      else f"Your SSD temperature is {ctx.ssd_temp:.0f}°C, within a safe range.")
        return AssistantResponse(query=query, intent="ssd_health", answer=answer,
                                 data={"ssd_temp": ctx.ssd_temp, "disk_usage": ctx.disk_usage})

    def _battery_health(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if ctx.battery_health is None:
            return self._no_sensor(query, "battery health")
        if ctx.battery_health >= 90:
            verdict = "in excellent condition"
        elif ctx.battery_health >= 80:
            verdict = "in good condition"
        elif ctx.battery_health >= 65:
            verdict = "showing noticeable wear"
        else:
            verdict = "significantly degraded — you may want to consider a replacement"
        temp_note = (f" Battery temperature is {ctx.battery_temp:.0f}°C."
                     if ctx.battery_temp is not None else "")
        answer = (f"Your battery is {verdict}: it holds about {ctx.battery_health:.0f}% of its "
                  f"original design capacity.{temp_note} Batteries lose capacity gradually with "
                  "each charge cycle; below ~80% you'll notice shorter runtime.")
        return AssistantResponse(query=query, intent="battery_health", answer=answer,
                                 data={"battery_health": ctx.battery_health,
                                       "battery_temp": ctx.battery_temp,
                                       "battery_status": ctx.battery_status})

    def _what_optimize(self, query: str, ctx: SystemContext) -> AssistantResponse:
        priorities: list[str] = []
        if ctx.throttling or (ctx.cpu_temp or 0) >= 90:
            priorities.append("1. Reduce thermal load — close heavy apps; the CPU is overheating.")
        if (ctx.memory_usage or 0) >= 85:
            priorities.append("2. Free memory — high RAM use is slowing the system.")
        if (ctx.cpu_usage or 0) >= 85 and ctx.top_cpu:
            priorities.append(f"3. Close '{ctx.top_cpu[0].name}' — it's the top CPU consumer.")
        if (ctx.disk_usage or 0) >= 90:
            priorities.append("4. Clean disk space — the drive is nearly full.")
        if not priorities:
            answer = ("Nothing urgent to optimize — your system is running well. Keep cooling "
                      "vents clear and close apps you're not using.")
        else:
            answer = ("Here's what I'd address first, in order of impact:\n"
                      + "\n".join(priorities))
        return AssistantResponse(
            query=query, intent="what_optimize", answer=answer,
            data={"priorities": priorities}, suggested_actions=self._suggested_for(ctx),
        )

    def _close_apps(self, query: str, ctx: SystemContext) -> AssistantResponse:
        candidates = [p for p in ctx.top_cpu + ctx.top_memory
                      if p.cpu_usage >= 25 or p.memory_usage >= 15]
        seen, unique = set(), []
        for p in candidates:
            if p.pid not in seen:
                seen.add(p.pid)
                unique.append(p)
        if not unique:
            answer = ("Nothing needs closing right now — no application is using an excessive "
                      "amount of CPU or memory.")
        else:
            lines = [f"- {p.name} (PID {p.pid}): {p.cpu_usage:.0f}% CPU, "
                     f"{p.memory_usage:.0f}% memory" for p in unique[:5]]
            answer = ("These applications are using notable resources; closing the ones you're "
                      "not actively using would help:\n" + "\n".join(lines))
        return AssistantResponse(query=query, intent="close_apps", answer=answer,
                                 data={"candidates": [p.model_dump() for p in unique[:5]]},
                                 suggested_actions=[ACTIONS["optimize_resources"]])

    def _memory_cause(self, query: str, ctx: SystemContext) -> AssistantResponse:
        if ctx.memory_usage is None:
            return self._no_sensor(query, "memory metrics")
        worst = ctx.top_memory[0] if ctx.top_memory else None
        lead = f"Memory usage is {ctx.memory_usage:.0f}%"
        lead += (f" (last-hour average {ctx.memory_avg_1h:.0f}%)."
                 if ctx.memory_avg_1h is not None else ".")
        if worst:
            lead += (f" The largest consumer is '{worst.name}' "
                     f"({worst.memory_usage:.0f}%, ~{worst.memory_mb:.0f} MB).")
        if ctx.memory_usage >= 85:
            lead += (" This is high enough to cause swapping and slow the system; consider "
                     "closing memory-heavy apps.")
        return AssistantResponse(query=query, intent="memory_cause", answer=lead,
                                 data={"top_memory": [p.model_dump() for p in ctx.top_memory]},
                                 suggested_actions=self._suggested_for(ctx))

    def _optimize(self, query: str, ctx: SystemContext) -> AssistantResponse:
        actions = optimization_service.list_actions()
        answer = ("Here are safe optimization actions I can run. Each requires your "
                  "confirmation before anything changes:\n"
                  + "\n".join(f"- {a.title}: {a.description}" for a in actions))
        return AssistantResponse(query=query, intent="optimize", answer=answer,
                                 suggested_actions=actions)

    def _explain_concept(self, query: str, ctx: SystemContext) -> AssistantResponse:
        q = query.lower()
        for _, (keywords, explanation) in _GLOSSARY.items():
            if any(k in q for k in keywords):
                return AssistantResponse(query=query, intent="explain_concept",
                                         answer=explanation, data={})
        return AssistantResponse(
            query=query, intent="explain_concept",
            answer="I can explain concepts like thermal throttling, CPU frequency, swap "
            "memory, load average, S.M.A.R.T. health, fan RPM and battery cycles. "
            "Which one would you like?",
            data={},
        )

    def _compare(self, query: str, ctx: SystemContext) -> AssistantResponse:
        # We have last-hour averages; a full yesterday-vs-today needs >24h of data.
        if ctx.cpu_temp is not None and ctx.cpu_temp_avg_1h is not None:
            diff = ctx.cpu_temp - ctx.cpu_temp_avg_1h
            direction = "higher" if diff > 1 else "lower" if diff < -1 else "about the same as"
            answer = (
                f"Right now the CPU is {ctx.cpu_temp:.0f}°C, which is {direction} its "
                f"last-hour average of {ctx.cpu_temp_avg_1h:.0f}°C"
                + (f" (a {abs(diff):.0f}°C difference)." if abs(diff) > 1 else ".")
                + " For full day-over-day comparisons, the Analytics page shows longer-range "
                "trends once enough history has been collected."
            )
        else:
            answer = ("I need more collected history to compare time periods. Once SystemIQ "
                      "has run for a day or more, the Analytics page can compare trends across "
                      "days.")
        return AssistantResponse(query=query, intent="compare", answer=answer,
                                 data={"cpu_temp": ctx.cpu_temp, "cpu_temp_avg_1h": ctx.cpu_temp_avg_1h})

    def _predict(self, query: str, ctx: SystemContext, metric: str) -> AssistantResponse:
        pred = next((p for p in ctx.predictions if p.metric == metric), None)
        if pred is None:
            return AssistantResponse(
                query=query, intent=f"predict_{metric}",
                answer="I don't have enough collected history yet to forecast that reliably.",
                data={},
            )
        return AssistantResponse(query=query, intent=f"predict_{metric}",
                                 answer=pred.message, data={"prediction": pred.model_dump()})

    def _top(self, query: str, ctx: SystemContext, by: str) -> AssistantResponse:
        procs = ctx.top_cpu if by == "cpu" else ctx.top_memory
        if not procs:
            return self._no_sensor(query, "process information")
        lines = [f"{i+1}. {p.name} (PID {p.pid}) — CPU {p.cpu_usage:.0f}%, "
                 f"memory {p.memory_usage:.0f}% (~{p.memory_mb:.0f} MB)"
                 for i, p in enumerate(procs)]
        answer = f"Top {by} consumers:\n" + "\n".join(lines)
        return AssistantResponse(query=query, intent=f"top_{by}", answer=answer,
                                 data={"processes": [p.model_dump() for p in procs]})

    def _status(self, query: str, ctx: SystemContext, focus: str) -> AssistantResponse:
        if focus == "cpu":
            answer = (f"CPU usage is {ctx.cpu_usage:.0f}% across {ctx.cpu_count} cores "
                      f"(load {ctx.load_avg_1m}).") if ctx.cpu_usage is not None else "CPU data unavailable."
        elif focus == "memory":
            answer = (f"Memory usage is {ctx.memory_usage:.0f}%."
                      if ctx.memory_usage is not None else "Memory data unavailable.")
        elif focus == "disk":
            answer = (f"Disk usage is {ctx.disk_usage:.0f}%."
                      if ctx.disk_usage is not None else "Disk data unavailable.")
        elif focus == "temp":
            if ctx.cpu_temp is None:
                return self._no_sensor(query, "temperature sensors")
            extra = f", fan {ctx.fan_speed_rpm:.0f} RPM" if ctx.fan_speed_rpm else ""
            answer = f"CPU temperature is {ctx.cpu_temp:.0f}°C{extra}."
        else:
            return self._health_summary(query, ctx)
        return AssistantResponse(query=query, intent=f"{focus}_status", answer=answer,
                                 data={"snapshot": ctx.model_dump(mode="json")})

    @staticmethod
    def _no_sensor(query: str, what: str) -> AssistantResponse:
        return AssistantResponse(
            query=query, intent="status",
            answer=f"I can't read {what} on this machine — the sensor isn't exposed here "
            "(common in virtual machines). On physical Linux hardware with lm-sensors "
            "installed, this information becomes available.",
            data={},
        )
