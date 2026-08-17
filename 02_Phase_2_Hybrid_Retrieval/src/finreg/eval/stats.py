"""Bootstrap confidence intervals and McNemar paired significance tests (T-132, Invariant E5)."""

import numpy as np
from typing import List, Dict, Any, Tuple
from scipy.stats import chi2


def compute_bootstrap_ci(
    scores: List[float],
    num_resamples: int = 10000,
    confidence_level: float = 0.95,
    seed: int = 42
) -> Tuple[float, float, float]:
    """
    Computes percentile bootstrap confidence interval over scores array.
    Returns (mean_score, ci_lower, ci_upper).
    """
    if not scores:
        return 0.0, 0.0, 0.0

    arr = np.array(scores, dtype=np.float32)
    mean_val = float(np.mean(arr))

    rng = np.random.default_rng(seed)
    n = len(arr)
    boot_means = np.empty(num_resamples, dtype=np.float32)

    for i in range(num_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = 1.0 - confidence_level
    lower = float(np.percentile(boot_means, (alpha / 2.0) * 100))
    upper = float(np.percentile(boot_means, (1.0 - alpha / 2.0) * 100))

    return round(mean_val, 4), round(lower, 4), round(upper, 4)


def compute_paired_mcnemar_test(
    arm_a_outcomes: List[int],  # 1 for correct, 0 for incorrect
    arm_b_outcomes: List[int]
) -> Dict[str, Any]:
    """
    Computes McNemar test on paired binary outcomes between Arm A4 and Arm A2.
    Chi-squared statistic with continuity correction: (|b - c| - 1)^2 / (b + c)
    """
    if len(arm_a_outcomes) != len(arm_b_outcomes):
        raise ValueError("Paired outcomes arrays must have equal length.")

    # Contingency table: [[both_correct, A_correct_B_wrong], [A_wrong_B_correct, both_wrong]]
    n00, n01, n10, n11 = 0, 0, 0, 0
    for a, b in zip(arm_a_outcomes, arm_b_outcomes):
        if a == 1 and b == 1:
            n11 += 1
        elif a == 1 and b == 0:
            n10 += 1
        elif a == 0 and b == 1:
            n01 += 1
        else:
            n00 += 1

    table = [[n11, n10], [n01, n00]]
    b = n10
    c = n01

    if b + c == 0:
        stat = 0.0
        p_val = 1.0
    else:
        stat = float(((abs(b - c) - 1.0) ** 2) / (b + c))
        p_val = float(chi2.sf(stat, df=1))

    return {
        "contingency_table": table,
        "statistic": round(stat, 4),
        "p_value": round(p_val, 4),
        "is_statistically_significant": p_val < 0.05
    }
