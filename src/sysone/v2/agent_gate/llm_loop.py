"""LLM agent for the closed loop: same prompt format as sources.LlmAgent, plus an on-disk prompt cache.

The agent's reply depends only on (model, system prompt, user prompt, seed), so identical situations are asked once:
episodes under different gates share every turn until the gates make the agent's situation diverge.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

from . import sources


class CachedLlmAgent:
    def __init__(self, url: str, model_tag: str, cache_path: Path, temperature: float = 0.7, seed: int = 0):
        self.url = url.rstrip("/") + "/v1/chat/completions"
        self.model_tag, self.temperature, self.seed = model_tag, temperature, seed
        self.cache_path = Path(cache_path)
        self.cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text().splitlines():
                r = json.loads(line)
                self.cache[r["key"]] = r["text"]
        self.calls = self.hits = 0
        self.parse_errors = 0

    def _complete(self, system, user, seed):
        key = hashlib.sha256(json.dumps([self.model_tag, system, user, seed, self.temperature]).encode()).hexdigest()
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": self.temperature, "seed": seed, "max_tokens": 160,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False}}
        r = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=300) as f:
            text = json.load(f)["choices"][0]["message"]["content"]
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        self.calls += 1
        self.cache[key] = text
        with self.cache_path.open("a") as f:
            f.write(json.dumps({"key": key, "text": text}) + "\n")
        return text

    def propose(self, task_text, readings, act, note, turn):
        user = (f"Task: {task_text}\nTurn {turn}. Readings: level {readings['level']}%, "
                f"temperature {readings['temperature']} degC, pressure {readings['pressure']} (rated 1.0), "
                f"flow {readings['flow']} %/s.\nCurrent setpoints: " +
                ", ".join(f"{k} {v:g}" for k, v in act.items()) + ".")
        if note:
            user += "\n" + note
        user += "\n/no_think"
        text = self._complete(sources.SYSTEM, user, self.seed + turn)
        reqs, done = [], False
        try:
            obj = json.loads(text)
            done = bool(obj.get("done", False))
            for w in obj.get("writes", [])[:6]:
                reqs.append(sources.req(int(w.get("address")), float(w.get("value"))))
        except Exception:
            self.parse_errors += 1
        return reqs, done
