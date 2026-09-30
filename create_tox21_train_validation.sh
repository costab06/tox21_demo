#!/bin/bash
set -e

python3 -m pip install --user pandas scikit-learn

python3 create_tox21_train_validation.py liver_tox21_modeling_dataset.csv

