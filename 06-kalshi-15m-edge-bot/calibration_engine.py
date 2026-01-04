"""
Calibration Engine for MomentumAnalyzerV4

Derives empirically calibrated YES base probabilities from accumulated outcome
data in skipped_trades.csv, using exponential time-decay weighting so that
recent market conditions count more than old ones.

Called automatically by MomentumAnalyzerV4 on startup.  Recalibration only
runs when skipped_trades.csv is newer than the cached calibration JSON, so
restarts after the first run are instant.

How it works
------------
1. Read every row in skipped_trades.csv that has a valid threshold, spot_price,
   realized_volatility, and actual_outcome (yes/no).

2. Compute norm_dist = (threshold - spot) / spot% / max(vol, vol_floor).
   This is the same σ-distance used in MomentumAnalyzerV4.

3. Assign each row to one of 8 norm_dist buckets.

4. Weight each row by exp(-age_days × ln2 / half_life_days).
   Default half_life = 30 days → data from 30 days ago has half the influence
   of today's data.

5. Compute weighted YES win rate per bucket.  Buckets with fewer than
   min_samples raw rows keep the hardcoded FALLBACK_PROBS value.

6. Enforce monotonicity: YES win rate must decrease as norm_dist increases
   (further below threshold → lower YES probability).

7. Save result to v4_calibration.json (overwrites previous file).

Edge cases
----------
- If skipped_trades.csv has fewer than 1,000 usable rows, calibration is
  skipped and the model uses FALLBACK_PROBS.
- If any individual bucket is sparse, that bucket alone falls back to
  FALLBACK_PROBS while the others use empirical values.
- Non-monotonic calibrated values are corrected by a simple forward pass
  (take running minimum from bucket 0 downward).
"""

import csv
import json
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Norm-distance bucket boundaries — must stay in sync with MomentumAnalyzerV4.
# Bucket i applies when BOUNDARIES[i-1] <= norm_dist < BOUNDARIES[i].
BUCKET_BOUNDARIES: List[float] = [-3.0, -1.5, -0.7, 0.0, 0.7, 1.5, 3.0]

# Hardcoded fallback probabilities derived from the initial calibration run
# on 37,344 observations (2026-02-20).  Used for sparse buckets.
FALLBACK_PROBS: List[float] = [0.80, 0.78, 0.76, 0.61, 0.35, 0.22, 0.13, 0.05]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _bucket_index(norm_dist: float) -> int:
    """Return the 0-based bucket index for a given norm_dist value."""
    for i, boundary in enumerate(BUCKET_BOUNDARIES):
        if norm_dist < boundary:
            return i
    return len(BUCKET_BOUNDARIES)  # rightmost bucket


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_calibrated_probs(skipped_trades_path: str,
                              min_samples: int = 200,
                              half_life_days: float = 30.0,
                              vol_floor: float = 0.15) -> Optional[List[float]]:
    """
    Compute YES base probabilities from skipped_trades.csv.

    Parameters
    ----------
    skipped_trades_path : str
        Path to the CSV file produced by NegativeEdgeTracker.
    min_samples : int
        Minimum raw row count for a bucket to use its empirical value.
        Sparse buckets fall back to FALLBACK_PROBS.
    half_life_days : float
        Time-decay half-life.  Data from this many days ago has half the
        weight of today's data.
    vol_floor : float
        Minimum volatility σ (% of price) to avoid division blow-up.

    Returns
    -------
    List[float] of length 8, or None if not enough data.
    """
    path = Path(skipped_trades_path)
    if not path.exists():
        logger.info("CalibrationEngine: skipped_trades.csv not found — skipping")
        return None

    now       = datetime.now(timezone.utc)
    n_buckets = len(BUCKET_BOUNDARIES) + 1
    win_w     = [0.0] * n_buckets   # weighted wins
    total_w   = [0.0] * n_buckets   # total weight
    counts    = [0  ] * n_buckets   # raw row count

    rows_read = rows_skipped = 0

    try:
        with open(path, newline='') as f:
            for row in csv.DictReader(f):
                rows_read += 1
                try:
                    threshold = float(row['threshold'])
                    spot      = float(row['spot_price'])
                    vol       = float(row.get('realized_volatility') or 0)
                    outcome   = row.get('actual_outcome', '').strip()
                    ts_str    = row.get('timestamp', '').strip()

                    if threshold <= 0 or spot <= 0 or outcome not in ('yes', 'no'):
                        rows_skipped += 1
                        continue

                    distance_pct = (threshold - spot) / spot * 100
                    norm_dist    = distance_pct / max(vol, vol_floor)

                    # Exponential time-decay weight
                    weight = 1.0
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
                            weight   = math.exp(-age_days * math.log(2.0) / half_life_days)
                        except ValueError:
                            pass

                    idx          = _bucket_index(norm_dist)
                    total_w[idx] += weight
                    counts[idx]  += 1
                    if outcome == 'yes':
                        win_w[idx] += weight

                except (ValueError, KeyError, TypeError, ZeroDivisionError):
                    rows_skipped += 1
                    continue

    except Exception as e:
        logger.warning(f"CalibrationEngine: error reading {path}: {e}")
        return None

    usable = rows_read - rows_skipped
    logger.info(f"CalibrationEngine: {usable:,} usable rows out of {rows_read:,} read")

    if usable < 1000:
        logger.info("CalibrationEngine: fewer than 1,000 usable rows — using fallback probs")
        return None

    # Build calibrated list, falling back for sparse buckets
    calibrated: List[float] = []
    for i in range(n_buckets):
        if counts[i] < min_samples or total_w[i] == 0:
            calibrated.append(FALLBACK_PROBS[i])
            logger.debug(f"  Bucket {i:d}: n={counts[i]:5d} (sparse) → fallback {FALLBACK_PROBS[i]:.3f}")
        else:
            wr = win_w[i] / total_w[i]
            wr = max(0.05, min(0.95, wr))
            calibrated.append(wr)
            delta = wr - FALLBACK_PROBS[i]
            logger.info(f"  Bucket {i:d}: n={counts[i]:5d} → {wr:.3f}  "
                        f"(fallback {FALLBACK_PROBS[i]:.3f}, Δ={delta:+.3f})")

    # Enforce monotonicity: probs must be non-increasing across buckets
    # (bucket 0 = furthest above threshold = highest YES prob)
    for i in range(1, n_buckets):
        if calibrated[i] > calibrated[i - 1]:
            calibrated[i] = calibrated[i - 1]

    return [round(p, 4) for p in calibrated]


def save_calibration(output_path: str, probs: List[float],
                     source_row_count: int = 0) -> None:
    """Write calibration results to JSON (overwrites previous file)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'calibrated_at':    datetime.now(timezone.utc).isoformat(),
        'source_rows':      source_row_count,
        'bucket_boundaries': BUCKET_BOUNDARIES,
        'base_probs':       probs,
        'note': (
            'base_probs[i] is the YES win probability when norm_dist is in '
            '[boundaries[i-1], boundaries[i]).  Bucket 0 = norm_dist < -3σ '
            '(price well above threshold). Bucket 7 = norm_dist > +3σ '
            '(price well below threshold).'
        ),
    }
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)


def load_calibration(calibration_path: str) -> Optional[List[float]]:
    """Load previously saved calibration; returns None if missing or corrupt."""
    path = Path(calibration_path)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        probs = data.get('base_probs')
        expected_len = len(BUCKET_BOUNDARIES) + 1
        if isinstance(probs, list) and len(probs) == expected_len:
            logger.info(
                f"CalibrationEngine: loaded calibration from {path} "
                f"(calibrated at {data.get('calibrated_at', 'unknown')})"
            )
            return probs
        logger.warning(f"CalibrationEngine: {path} has wrong format — ignoring")
    except Exception as e:
        logger.warning(f"CalibrationEngine: could not load {path}: {e}")
    return None


def needs_recalibration(skipped_trades_path: str, calibration_path: str) -> bool:
    """
    Returns True if calibration should be rerun.

    Triggers when:
    - No cached calibration exists, OR
    - skipped_trades.csv has been modified since the calibration was saved
      (i.e., new rows have been added).
    """
    cal    = Path(calibration_path)
    trades = Path(skipped_trades_path)

    if not cal.exists():
        return True
    if not trades.exists():
        return False   # nothing to calibrate from

    return trades.stat().st_mtime > cal.stat().st_mtime
