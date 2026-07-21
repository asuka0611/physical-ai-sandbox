from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class RolloutBatch:
    observations: np.ndarray
    actions: np.ndarray
    rewards: np.ndarray
    dones: np.ndarray
    values: np.ndarray
    log_probs: np.ndarray
    returns: np.ndarray
    advantages: np.ndarray


class RolloutBuffer:
    def __init__(self) -> None:
        self.observations: list[np.ndarray] = []
        self.actions: list[np.ndarray] = []
        self.rewards: list[float] = []
        self.dones: list[bool] = []
        self.values: list[float] = []
        self.log_probs: list[float] = []

    def add(
        self,
        *,
        observation: np.ndarray,
        action: np.ndarray,
        reward: float,
        done: bool,
        value: float,
        log_prob: float,
    ) -> None:
        self.observations.append(np.asarray(observation, dtype=np.float64))
        self.actions.append(np.asarray(action, dtype=np.float64))
        self.rewards.append(float(reward))
        self.dones.append(bool(done))
        self.values.append(float(value))
        self.log_probs.append(float(log_prob))

    @property
    def size(self) -> int:
        return len(self.rewards)

    def to_batch(self, *, last_value: float, gamma: float, gae_lambda: float) -> RolloutBatch:
        if not self.rewards:
            raise ValueError("RolloutBuffer is empty")
        observations = np.stack(self.observations).astype(np.float64)
        actions = np.stack(self.actions).astype(np.float64)
        rewards = np.asarray(self.rewards, dtype=np.float64)
        dones = np.asarray(self.dones, dtype=np.bool_)
        values = np.asarray(self.values, dtype=np.float64)
        log_probs = np.asarray(self.log_probs, dtype=np.float64)
        advantages, returns = compute_gae(
            rewards=rewards,
            dones=dones,
            values=values,
            last_value=float(last_value),
            gamma=gamma,
            gae_lambda=gae_lambda,
        )
        safe_std = float(np.std(advantages))
        if safe_std > 1e-8:
            advantages = (advantages - float(np.mean(advantages))) / safe_std
        else:
            advantages = advantages - float(np.mean(advantages))
        return RolloutBatch(
            observations=observations,
            actions=actions,
            rewards=rewards,
            dones=dones,
            values=values,
            log_probs=log_probs,
            returns=returns,
            advantages=advantages,
        )


def compute_gae(
    *,
    rewards: np.ndarray,
    dones: np.ndarray,
    values: np.ndarray,
    last_value: float,
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    rewards = np.asarray(rewards, dtype=np.float64)
    dones = np.asarray(dones, dtype=np.bool_)
    values = np.asarray(values, dtype=np.float64)
    if rewards.shape != values.shape or rewards.shape != dones.shape:
        raise ValueError("rewards, dones, and values must have matching shapes")
    if not np.all(np.isfinite(rewards)) or not np.all(np.isfinite(values)):
        raise ValueError("GAE inputs contain NaN or Inf")
    advantages = np.zeros_like(rewards, dtype=np.float64)
    next_advantage = 0.0
    next_value = float(last_value)
    for index in reversed(range(rewards.shape[0])):
        nonterminal = 0.0 if dones[index] else 1.0
        delta = rewards[index] + gamma * next_value * nonterminal - values[index]
        next_advantage = delta + gamma * gae_lambda * nonterminal * next_advantage
        advantages[index] = next_advantage
        next_value = values[index]
    returns = advantages + values
    if not np.all(np.isfinite(advantages)) or not np.all(np.isfinite(returns)):
        raise ValueError("GAE output contains NaN or Inf")
    return advantages, returns
