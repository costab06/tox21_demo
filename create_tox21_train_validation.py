#!/usr/bin/env python3
"""
Create training and validation CSVs from liver_tox21_modeling_dataset.csv.

Output format:
    column 1: log10_loael_median
    remaining columns: 12 continuous Tox21 *_score predictors

Non-predictive identifiers, SMILES, study metadata, binary *_class outputs,
and other columns are intentionally excluded.

The split is performed by structure_group so identical QSAR-ready structures
cannot appear in both training and validation sets.
"""

import argparse
import sys
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

TARGET = "log10_loael_median"

PREDICTORS = [
    "NR-AR_score",
    "NR-AR-LBD_score",
    "NR-AhR_score",
    "NR-Aromatase_score",
    "NR-ER_score",
    "NR-ER-LBD_score",
    "NR-PPAR-gamma_score",
    "SR-ARE_score",
    "SR-ATAD5_score",
    "SR-HSE_score",
    "SR-MMP_score",
    "SR-p53_score",
]

GROUP = "structure_group"


def main():
    p = argparse.ArgumentParser(
        description="Create leakage-safe Tox21 training and validation CSVs."
    )
    p.add_argument(
        "input_csv",
        nargs="?",
        default="liver_tox21_modeling_dataset.csv",
        help="Master modeling CSV"
    )
    p.add_argument(
        "--validation-fraction",
        type=float,
        default=0.20,
        help="Fraction reserved for validation (default: 0.20)"
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible split (default: 42)"
    )
    p.add_argument(
        "--train-output",
        default="liver_tox21_train.csv"
    )
    p.add_argument(
        "--validation-output",
        default="liver_tox21_validation.csv"
    )
    args = p.parse_args()

    if not 0.0 < args.validation_fraction < 1.0:
        sys.exit("ERROR: --validation-fraction must be between 0 and 1.")

    df = pd.read_csv(args.input_csv)

    required = [TARGET, GROUP] + PREDICTORS
    missing = [c for c in required if c not in df.columns]
    if missing:
        sys.exit("ERROR: missing required columns: " + ", ".join(missing))

    # Reject rows that cannot be used rather than silently imputing values.
    usable = df[required].copy()
    bad = usable.isna().any(axis=1)
    if bad.any():
        print(
            f"WARNING: dropping {bad.sum()} row(s) with missing target, "
            "predictor, or structure_group.",
            file=sys.stderr,
        )
        usable = usable.loc[~bad].copy()

    # Split by modeled structure, not by row. This keeps identical structures
    # together and prevents train/validation leakage.
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=args.validation_fraction,
        random_state=args.seed,
    )
    train_idx, val_idx = next(
        splitter.split(
            usable,
            y=usable[TARGET],
            groups=usable[GROUP],
        )
    )

    train_source = usable.iloc[train_idx].copy()
    val_source = usable.iloc[val_idx].copy()

    # Final files contain ONLY target + continuous predictors.
    columns = [TARGET] + PREDICTORS
    train = train_source[columns].copy()
    validation = val_source[columns].copy()

    # Safety checks.
    train_groups = set(train_source[GROUP])
    val_groups = set(val_source[GROUP])
    overlap = train_groups & val_groups
    if overlap:
        sys.exit(
            f"ERROR: {len(overlap)} structure group(s) leaked across split."
        )

    train.to_csv(args.train_output, index=False)
    validation.to_csv(args.validation_output, index=False)

    print(f"Usable rows: {len(usable)}")
    print(f"Unique structure groups: {usable[GROUP].nunique()}")
    print(f"Training rows: {len(train)}")
    print(f"Validation rows: {len(validation)}")
    print(f"Training structure groups: {len(train_groups)}")
    print(f"Validation structure groups: {len(val_groups)}")
    print(f"Structure-group overlap: {len(overlap)}")
    print(f"Columns per output file: {len(columns)}")
    print(f"Target: {columns[0]}")
    print(f"Predictors: {len(PREDICTORS)}")
    print(f"Training file: {args.train_output}")
    print(f"Validation file: {args.validation_output}")


if __name__ == "__main__":
    main()
