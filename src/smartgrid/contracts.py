"""Stable, data-independent contracts derived from the official specification.

This module intentionally contains no assumptions about the unknown Excel layout,
energy-register semantics, or forecast horizon.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectContract:
    """Dimensions, fields, and units that every pipeline stage must preserve."""

    cadence_minutes: int = 15
    samples_per_day: int = 96
    context_days: int = 7
    electrical_features: tuple[str, ...] = ("Ea", "Er", "Pmax", "Smax")
    target_features: tuple[str, ...] = ("delta_Ea", "delta_Er", "Pmax", "Smax")
    calendar_feature_count: int = 7
    seasonal_lags: tuple[int, ...] = (96, 672)

    @property
    def context_steps(self) -> int:
        """Number of 15-minute observations in the seven-day input context."""

        return self.samples_per_day * self.context_days

    @property
    def input_feature_count(self) -> int:
        """Total electrical and calendar features at each time step."""

        return len(self.electrical_features) + self.calendar_feature_count

    @property
    def canonical_columns(self) -> tuple[str, ...]:
        """Minimum standardized columns expected after raw-column mapping."""

        return ("timestamp", *self.electrical_features)

    def validate(self) -> None:
        """Fail fast if a future edit contradicts the official dimensional contract."""

        if 24 * 60 // self.cadence_minutes != self.samples_per_day:
            raise ValueError("cadence_minutes and samples_per_day are inconsistent")
        if self.context_steps != 672:
            raise ValueError("official context must contain 672 samples")
        if self.input_feature_count != 11:
            raise ValueError("official input must contain 11 features per sample")
        if len(self.target_features) != 4:
            raise ValueError("official multi-output target must contain four quantities")
        if set(self.seasonal_lags) != {96, 672}:
            raise ValueError("official seasonal baselines use lags 96 and 672")


PROJECT_CONTRACT = ProjectContract()
PROJECT_CONTRACT.validate()
