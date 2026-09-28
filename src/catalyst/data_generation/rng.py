"""Seeded random number generation and small statistical helpers.

A single ``numpy.random.Generator`` seeded from config guarantees the whole
dataset is byte-for-byte reproducible.
"""
from __future__ import annotations

import numpy as np


def make_rng(seed: int) -> np.random.Generator:
    """Return a seeded PCG64 generator."""
    return np.random.default_rng(seed)


def clipped_normal(rng: np.random.Generator, mean: float, sd: float,
                   low: float, high: float, size: int) -> np.ndarray:
    """Normal draws clipped to [low, high]."""
    return np.clip(rng.normal(mean, sd, size), low, high)


def minmax(x: np.ndarray) -> np.ndarray:
    """Scale to [0, 1]; constant arrays map to 0.5."""
    x = np.asarray(x, dtype=float)
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi - lo < 1e-12:
        return np.full_like(x, 0.5)
    return (x - lo) / (hi - lo)


def zscore(x: np.ndarray) -> np.ndarray:
    """Standardise to mean 0 / sd 1; constant arrays map to 0."""
    x = np.asarray(x, dtype=float)
    sd = x.std()
    if sd < 1e-12:
        return np.zeros_like(x)
    return (x - x.mean()) / sd


def weighted_choice(rng: np.random.Generator, options, weights, size: int):
    """Vectorised weighted sampling with replacement."""
    p = np.asarray(weights, dtype=float)
    p = p / p.sum()
    idx = rng.choice(len(options), size=size, p=p)
    return np.asarray(options, dtype=object)[idx]
