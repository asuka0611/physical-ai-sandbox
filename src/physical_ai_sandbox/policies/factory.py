from __future__ import annotations

from pathlib import Path

from physical_ai_sandbox.policies.base import Policy
from physical_ai_sandbox.policies.bc import BehaviorCloningPolicy
from physical_ai_sandbox.policies.manual import ManualPolicy
from physical_ai_sandbox.policies.ppo import PPOPolicy
from physical_ai_sandbox.policies.random import RandomPolicy


def create_policy(
    policy_name: str,
    *,
    model_path: str | Path | None = None,
    seed: int = 42,
) -> Policy:
    normalized = policy_name.lower().strip()
    if normalized == "random":
        return RandomPolicy(seed=seed)
    if normalized == "manual":
        return ManualPolicy()
    if normalized == "bc":
        if model_path is None:
            raise ValueError("--model is required for bc policy")
        return BehaviorCloningPolicy(model_path)
    if normalized == "ppo":
        if model_path is None:
            raise ValueError("--model is required for ppo policy")
        return PPOPolicy(model_path, seed=seed)
    raise ValueError(f"Unsupported policy: {policy_name}")
