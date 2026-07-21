from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from physical_ai_sandbox.envs.panda_pick_place import PandaPickPlaceEnv
from physical_ai_sandbox.learning.bc.dataset import load_bc_dataset, observation_normalizer
from physical_ai_sandbox.learning.datasets.feature_encoder import ObservationEncoder
from physical_ai_sandbox.learning.ppo.buffer import RolloutBatch, RolloutBuffer
from physical_ai_sandbox.learning.ppo.evaluation import evaluate_ppo
from physical_ai_sandbox.learning.ppo.policy import (
    PPOActorCritic,
    gradient_clip_scale,
    gradient_global_norm,
)
from physical_ai_sandbox.learning.ppo.task import (
    GraspLiftTaskConfig,
    grasp_lift_reward,
    task_success,
)
from physical_ai_sandbox.paths import DEFAULT_CONFIG_PATH

PPO_TRAINER_VERSION = "phase4.ppo.numpy.v1"


@dataclass(frozen=True, slots=True)
class PPOTrainingConfig:
    total_steps: int = 256
    rollout_steps: int = 64
    max_episode_steps: int = 120
    update_epochs: int = 3
    minibatch_size: int = 64
    gamma: float = 0.98
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    actor_learning_rate: float = 0.001
    critic_learning_rate: float = 0.003
    entropy_coef: float = 0.001
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    seed: int = 42
    init: str = "bc"
    hidden_sizes: tuple[int, ...] = (64, 64)


@dataclass(frozen=True, slots=True)
class PPOTrainingResult:
    output_dir: Path
    checkpoint_path: Path
    history: list[dict[str, Any]]
    evaluation: dict[str, Any]


class PPOTrainer:
    def __init__(self, config: PPOTrainingConfig | None = None) -> None:
        self.config = config or PPOTrainingConfig()
        self.encoder = ObservationEncoder()
        self.rng = np.random.default_rng(self.config.seed)

    def train(
        self,
        output_dir: str | Path,
        *,
        dataset_dir: str | Path = "datasets/grasp_lift_v1",
        bc_model_dir: str | Path | None = "models/bc_grasp_lift_v1",
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        resume: bool = False,
        overwrite: bool = True,
    ) -> PPOTrainingResult:
        output = Path(output_dir)
        checkpoint_path = output / "ppo_checkpoint.npz"
        history_path = output / "training_history.json"
        if resume and checkpoint_path.exists():
            policy, metadata = PPOActorCritic.load(checkpoint_path)
            history = self._load_history(history_path)
            mean = np.asarray(metadata["observation_mean"], dtype=np.float64)
            safe_std = np.asarray(metadata["observation_safe_std"], dtype=np.float64)
            start_step = int(metadata.get("trained_steps", 0))
        else:
            if output.exists() and overwrite:
                import shutil

                shutil.rmtree(output)
            output.mkdir(parents=True, exist_ok=True)
            mean, safe_std = self._normalizer(dataset_dir, bc_model_dir)
            metadata = self._metadata(dataset_dir, bc_model_dir, mean, safe_std)
            policy = self._initialize_policy(metadata, bc_model_dir)
            history = []
            start_step = 0
        self._validate_policy(policy)
        steps_done = start_step
        while steps_done < self.config.total_steps:
            batch, rollout_summary = self._collect_rollout(
                policy,
                mean,
                safe_std,
                config_path=config_path,
            )
            update_summary = self._ppo_update(policy, batch)
            steps_done += batch.rewards.shape[0]
            history.append(
                {
                    "iteration": len(history) + 1,
                    "trained_steps": steps_done,
                    **rollout_summary,
                    **update_summary,
                },
            )
        metadata = {
            **metadata,
            "trained_steps": steps_done,
            "updated_at": datetime.now(UTC).isoformat(),
            "history_length": len(history),
        }
        output.mkdir(parents=True, exist_ok=True)
        policy.save(checkpoint_path, metadata)
        self._write_json(history_path, {"history": history})
        evaluation = evaluate_ppo(
            output,
            episodes=3,
            max_steps=self.config.max_episode_steps,
            seed=self.config.seed,
            config_path=config_path,
            record=False,
        )
        self._write_json(output / "evaluation_report.json", evaluation)
        self._write_json(output / "metadata.json", metadata)
        return PPOTrainingResult(
            output_dir=output,
            checkpoint_path=checkpoint_path,
            history=history,
            evaluation=evaluation,
        )

    def _initialize_policy(
        self,
        metadata: dict[str, Any],
        bc_model_dir: str | Path | None,
    ) -> PPOActorCritic:
        if self.config.init == "bc":
            if bc_model_dir is None:
                raise ValueError("bc_model_dir is required for BC initialization")
            bc_checkpoint = Path(bc_model_dir) / "policy_checkpoint.npz"
            return PPOActorCritic.initialize_from_bc(
                bc_checkpoint,
                seed=self.config.seed,
                metadata=metadata,
            )
        if self.config.init == "random":
            return PPOActorCritic.initialize_random(
                self.encoder.dimension,
                hidden_sizes=self.config.hidden_sizes,
                seed=self.config.seed,
                metadata=metadata,
            )
        raise ValueError("init must be 'bc' or 'random'")

    def _collect_rollout(
        self,
        policy: PPOActorCritic,
        mean: np.ndarray,
        safe_std: np.ndarray,
        *,
        config_path: str | Path,
    ) -> tuple[RolloutBatch, dict[str, Any]]:
        buffer = RolloutBuffer()
        env = PandaPickPlaceEnv(config_path=config_path)
        observation = env.reset()
        episode_step = 0
        episode_rewards: list[float] = []
        episode_successes = 0
        current_reward = 0.0
        last_normalized = self._normalize(observation, mean, safe_std)
        try:
            while buffer.size < self.config.rollout_steps:
                action, log_prob, value = policy.sample_action(last_normalized, self.rng)
                next_observation, _env_reward, terminated, truncated, info = env.step(action)
                reward = grasp_lift_reward(env, next_observation, config=GraspLiftTaskConfig())
                episode_step += 1
                current_reward += reward
                success = task_success(env, next_observation)
                done = bool(
                    success
                    or terminated
                    or truncated
                    or episode_step >= self.config.max_episode_steps
                )
                buffer.add(
                    observation=last_normalized,
                    action=action,
                    reward=reward,
                    done=done,
                    value=value,
                    log_prob=log_prob,
                )
                if done:
                    episode_rewards.append(current_reward)
                    episode_successes += int(success)
                    observation = env.reset()
                    episode_step = 0
                    current_reward = 0.0
                else:
                    observation = next_observation
                last_normalized = self._normalize(observation, mean, safe_std)
                if info.get("failure_reason") == "non-finite observation value":
                    raise FloatingPointError("Environment produced non-finite observation")
            last_value = (
                0.0 if buffer.dones[-1] else float(policy.value(last_normalized[None, :])[0])
            )
            batch = buffer.to_batch(
                last_value=last_value,
                gamma=self.config.gamma,
                gae_lambda=self.config.gae_lambda,
            )
        finally:
            env.close()
        return batch, {
            "rollout_reward_mean": float(np.mean(batch.rewards)),
            "rollout_reward_sum": float(np.sum(batch.rewards)),
            "rollout_episode_count": len(episode_rewards),
            "rollout_task_success_count": episode_successes,
            "rollout_episode_reward_mean": (
                float(np.mean(episode_rewards)) if episode_rewards else None
            ),
        }

    def _ppo_update(self, policy: PPOActorCritic, batch: RolloutBatch) -> dict[str, Any]:
        sample_count = batch.observations.shape[0]
        order = np.arange(sample_count)
        actor_losses: list[float] = []
        value_losses: list[float] = []
        entropy_values: list[float] = []
        grad_norms: list[float] = []
        clip_fraction_values: list[float] = []
        for _ in range(self.config.update_epochs):
            self.rng.shuffle(order)
            for start in range(0, sample_count, self.config.minibatch_size):
                indices = order[start : start + self.config.minibatch_size]
                minibatch = self._slice_batch(batch, indices)
                update = self._update_minibatch(policy, minibatch)
                actor_losses.append(update["actor_loss"])
                value_losses.append(update["value_loss"])
                entropy_values.append(update["entropy"])
                grad_norms.append(update["grad_norm"])
                clip_fraction_values.append(update["clip_fraction"])
        return {
            "actor_loss": float(np.mean(actor_losses)),
            "value_loss": float(np.mean(value_losses)),
            "entropy": float(np.mean(entropy_values)),
            "gradient_norm": float(np.mean(grad_norms)),
            "clip_fraction": float(np.mean(clip_fraction_values)),
        }

    def _update_minibatch(
        self,
        policy: PPOActorCritic,
        batch: RolloutBatch,
    ) -> dict[str, float]:
        mean, actor_activations, actor_pre_activations = policy.mean(batch.observations)
        std = np.exp(policy.log_std)
        variance = std**2
        new_log_probs = policy.log_prob(batch.observations, batch.actions)
        ratios = np.exp(np.clip(new_log_probs - batch.log_probs, -20.0, 20.0))
        clipped = np.clip(ratios, 1.0 - self.config.clip_epsilon, 1.0 + self.config.clip_epsilon)
        surrogate = np.minimum(ratios * batch.advantages, clipped * batch.advantages)
        actor_loss = -float(np.mean(surrogate))
        active = np.where(
            batch.advantages >= 0.0,
            ratios <= 1.0 + self.config.clip_epsilon,
            ratios >= 1.0 - self.config.clip_epsilon,
        )
        dloss_dlogp = np.where(active, -batch.advantages * ratios, 0.0) / batch.actions.shape[0]
        dlogp_dmean = (batch.actions - mean) / variance
        dloss_dmean = dloss_dlogp[:, None] * dlogp_dmean
        raw_actor = np.arctanh(np.clip(mean, -0.999999, 0.999999))
        dloss_draw = dloss_dmean * (1.0 - np.tanh(raw_actor) ** 2)
        actor_weight_grads, actor_bias_grads = policy.actor.gradients(
            actor_activations,
            actor_pre_activations,
            dloss_draw,
        )
        dlogp_dlog_std = ((batch.actions - mean) ** 2 / variance) - 1.0
        log_std_grad = np.sum(dloss_dlogp[:, None] * dlogp_dlog_std, axis=0)
        log_std_grad -= self.config.entropy_coef

        values_raw, critic_activations, critic_pre_activations = policy.critic.forward(
            batch.observations,
        )
        values = values_raw[:, 0]
        value_error = values - batch.returns
        value_loss = float(0.5 * np.mean(value_error**2))
        critic_output_grad = (
            self.config.value_coef * value_error[:, None] / batch.returns.shape[0]
        )
        critic_weight_grads, critic_bias_grads = policy.critic.gradients(
            critic_activations,
            critic_pre_activations,
            critic_output_grad,
        )
        grad_norm = gradient_global_norm(
            [actor_weight_grads, actor_bias_grads, critic_weight_grads, critic_bias_grads],
            extra=[log_std_grad],
        )
        scale = gradient_clip_scale(grad_norm, self.config.max_grad_norm)
        policy.actor.apply_gradients(
            actor_weight_grads,
            actor_bias_grads,
            learning_rate=self.config.actor_learning_rate,
            scale=scale,
        )
        policy.critic.apply_gradients(
            critic_weight_grads,
            critic_bias_grads,
            learning_rate=self.config.critic_learning_rate,
            scale=scale,
        )
        policy.log_std -= self.config.actor_learning_rate * scale * log_std_grad
        policy.log_std = np.clip(policy.log_std, -5.0, 1.0)
        self._validate_policy(policy)
        entropy = policy.entropy()
        clip_fraction = float(np.mean(np.abs(ratios - 1.0) > self.config.clip_epsilon))
        return {
            "actor_loss": actor_loss,
            "value_loss": value_loss,
            "entropy": entropy,
            "grad_norm": grad_norm,
            "clip_fraction": clip_fraction,
        }

    @staticmethod
    def _slice_batch(batch: RolloutBatch, indices: np.ndarray) -> RolloutBatch:
        return RolloutBatch(
            observations=batch.observations[indices],
            actions=batch.actions[indices],
            rewards=batch.rewards[indices],
            dones=batch.dones[indices],
            values=batch.values[indices],
            log_probs=batch.log_probs[indices],
            returns=batch.returns[indices],
            advantages=batch.advantages[indices],
        )

    def _normalize(
        self,
        observation: dict[str, Any],
        mean: np.ndarray,
        safe_std: np.ndarray,
    ) -> np.ndarray:
        encoded = self.encoder.encode(observation)
        normalized = (encoded - mean) / safe_std
        if normalized.shape != (self.encoder.dimension,):
            raise ValueError("Normalized observation has invalid shape")
        if not np.all(np.isfinite(normalized)):
            raise FloatingPointError("Normalized observation contains NaN or Inf")
        return normalized.astype(np.float64)

    def _normalizer(
        self,
        dataset_dir: str | Path,
        bc_model_dir: str | Path | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.config.init == "bc" and bc_model_dir is not None:
            from physical_ai_sandbox.learning.bc.policy import MLPPolicy

            _policy, metadata = MLPPolicy.load(Path(bc_model_dir) / "policy_checkpoint.npz")
            return (
                np.asarray(metadata["observation_mean"], dtype=np.float64),
                np.asarray(metadata["observation_safe_std"], dtype=np.float64),
            )
        dataset = load_bc_dataset(dataset_dir)
        return observation_normalizer(dataset)

    def _metadata(
        self,
        dataset_dir: str | Path,
        bc_model_dir: str | Path | None,
        mean: np.ndarray,
        safe_std: np.ndarray,
    ) -> dict[str, Any]:
        dataset = load_bc_dataset(dataset_dir)
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "trainer_version": PPO_TRAINER_VERSION,
            "task": "fixed_initial_grasp_lift",
            "init": self.config.init,
            "bc_model_dir": str(bc_model_dir) if bc_model_dir is not None else None,
            "dataset_dir": str(dataset_dir),
            "dataset_episode_count": dataset.manifest.get("episode_count"),
            "dataset_sample_count": dataset.manifest.get("sample_count"),
            "input_dim": self.encoder.dimension,
            "action_dim": 8,
            "feature_order": self.encoder.feature_order,
            "observation_mean": mean.tolist(),
            "observation_safe_std": safe_std.tolist(),
            "seed": self.config.seed,
            "total_steps_target": self.config.total_steps,
            "rollout_steps": self.config.rollout_steps,
            "max_episode_steps": self.config.max_episode_steps,
            "update_epochs": self.config.update_epochs,
            "clip_epsilon": self.config.clip_epsilon,
            "entropy_coef": self.config.entropy_coef,
            "value_coef": self.config.value_coef,
            "max_grad_norm": self.config.max_grad_norm,
            "warnings": [
                "Phase 4 PPO is a short fixed-condition smoke pipeline; "
                "performance may degrade from BC initialization.",
                "Do not interpret PPO smoke results as generalized robot performance.",
            ],
        }

    def _validate_policy(self, policy: PPOActorCritic) -> None:
        arrays = [
            *policy.actor.weights,
            *policy.actor.biases,
            *policy.critic.weights,
            *policy.critic.biases,
            policy.log_std,
        ]
        if any(not np.all(np.isfinite(array)) for array in arrays):
            raise FloatingPointError("PPO policy contains NaN or Inf")
        if policy.input_dim != self.encoder.dimension:
            raise ValueError("PPO policy input dimension does not match ObservationEncoder")

    @staticmethod
    def _load_history(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8")).get("history", [])

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
