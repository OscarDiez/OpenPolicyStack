"""
config.py — IA criteria weights and scoring configuration.
Uses plain string keys throughout to avoid enum import issues.
"""

DEFAULT_WEIGHTS: dict = {
    "economic":        0.25,
    "social":          0.15,
    "environmental":   0.10,
    "competitiveness": 0.25,
    "feasibility":     0.15,
    "coherence":       0.10,
}

SCORING_ANCHORS: dict = {
    "economic": {
        "+2": "Strong positive GDP/investment impact, well-evidenced",
        "+1": "Moderate positive economic effect",
         "0": "Neutral or negligible economic impact",
        "-1": "Moderate negative effect on costs or market",
        "-2": "Strong negative economic impact or significant compliance cost",
    },
    "social": {
        "+2": "Major improvement in jobs, skills, or inclusion",
        "+1": "Moderate positive social effect",
         "0": "No significant social impact",
        "-1": "Some negative social effect",
        "-2": "Significant negative social consequences",
    },
    "environmental": {
        "+2": "Strong reduction in environmental footprint",
        "+1": "Moderate environmental benefit",
         "0": "Neutral environmental impact",
        "-1": "Minor negative environmental effect",
        "-2": "Significant environmental harm",
    },
    "competitiveness": {
        "+2": "Major boost to EU strategic autonomy and global tech leadership",
        "+1": "Moderate improvement in competitiveness",
         "0": "No significant effect on competitiveness",
        "-1": "Slight competitiveness disadvantage",
        "-2": "Significant competitive harm vs non-EU players",
    },
    "feasibility": {
        "+2": "Highly feasible, low implementation risk, clear governance",
        "+1": "Feasible with manageable challenges",
         "0": "Uncertain feasibility",
        "-1": "Difficult to implement, high risk",
        "-2": "Not feasible in current context",
    },
    "coherence": {
        "+2": "Fully coherent with EU objectives and existing regulation",
        "+1": "Largely coherent with minor tensions",
         "0": "Neutral coherence",
        "-1": "Some tension with existing policy frameworks",
        "-2": "Significant incoherence or contradiction with EU law",
    },
}

SENSITIVITY_WEIGHT_GRID: list = [
    {
        "label": "economic_priority",
        "economic": 0.40, "social": 0.10, "environmental": 0.05,
        "competitiveness": 0.30, "feasibility": 0.10, "coherence": 0.05,
    },
    {
        "label": "social_env_priority",
        "economic": 0.15, "social": 0.25, "environmental": 0.25,
        "competitiveness": 0.15, "feasibility": 0.10, "coherence": 0.10,
    },
    {
        "label": "feasibility_priority",
        "economic": 0.20, "social": 0.10, "environmental": 0.05,
        "competitiveness": 0.20, "feasibility": 0.35, "coherence": 0.10,
    },
    {
        "label": "equal_weights",
        "economic": 0.167, "social": 0.167, "environmental": 0.167,
        "competitiveness": 0.167, "feasibility": 0.167, "coherence": 0.165,
    },
]

TOP_K_DRIVERS = 3
SCORE_MIN     = -2.0
SCORE_MAX     =  2.0
