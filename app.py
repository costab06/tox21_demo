#!/usr/bin/env python3
"""Tox21 prediction platform — domain-specific frontend for nnsd_client.

Responsibilities (domain-specific):
  - SMILES → Morgan fingerprint conversion (RDKit)
  - Assay selection and description
  - Class balancing for training data
  - Domain-appropriate result presentation

nnsd_client responsibilities (kept opaque here):
  - Neural network architecture selection
  - Training, netID assignment, model file management
  - All NN hyperparameters
"""

import csv
import json
import logging
import logging.handlers
import math
import os
import random

import requests
from flask import Flask, jsonify, render_template, request

# ── Configuration ─────────────────────────────────────────────────────────────

NNSD_URL  = os.environ.get("NNSD_URL",   "http://localhost:8080")
NNSD_KEY  = os.environ.get("NNSD_KEY",   "admin-secret-key-change-me")
DATA_ROOT = os.environ.get("TOX21_DATA", "/opt/neural/data/tox21")
HTTP_PORT = int(os.environ.get("TOX21_PORT", "8081"))

FP_RADIUS  = 2
FP_BITS    = 2048
TRAIN_FRAC = 0.80
RAND_SEED  = 42

# ── Logging setup ─────────────────────────────────────────────────────────────

LOG_FILE = os.environ.get("TOX21_LOG", "/opt/neural/logs/tox21.log")
_log_fmt  = logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
                               datefmt="%H:%M:%S")

_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3
)
_handler.setFormatter(_log_fmt)

_stderr_handler = logging.StreamHandler()
_stderr_handler.setFormatter(_log_fmt)

log = logging.getLogger("tox21")
log.setLevel(logging.INFO)
log.addHandler(_handler)
log.addHandler(_stderr_handler)

# ── Assay definitions ─────────────────────────────────────────────────────────
# Keys are exact column names in tox21.csv.
# `model` is the name used with nnsd_client's /api/models/* API.

ASSAYS = {
    "NR-AR": {
        "model": "nr_ar",
        "group": "Nuclear Receptor",
        "mechanism": "Androgen Receptor agonist",
        "context": "Endocrine disruption; flagged in reproductive toxicity screens.",
    },
    "NR-AR-LBD": {
        "model": "nr_ar_lbd",
        "group": "Nuclear Receptor",
        "mechanism": "Androgen Receptor Ligand Binding Domain",
        "context": "Selectivity assay complementing full-length AR screen.",
    },
    "NR-AhR": {
        "model": "nr_ahr",
        "group": "Nuclear Receptor",
        "mechanism": "Aryl Hydrocarbon Receptor agonist",
        "context": "Predicts dioxin-like toxicity and CYP1A1/1A2 induction.",
    },
    "NR-Aromatase": {
        "model": "nr_aromatase",
        "group": "Nuclear Receptor",
        "mechanism": "Aromatase (CYP19A1) inhibition",
        "context": "Disrupts estrogen biosynthesis; reproductive and endocrine toxicity.",
    },
    "NR-ER": {
        "model": "nr_er",
        "group": "Nuclear Receptor",
        "mechanism": "Estrogen Receptor α agonist",
        "context": "Key endocrine disruptor target; linked to breast cancer risk.",
    },
    "NR-ER-LBD": {
        "model": "nr_er_lbd",
        "group": "Nuclear Receptor",
        "mechanism": "Estrogen Receptor Ligand Binding Domain",
        "context": "Selectivity assay for ERα LBD interactions.",
    },
    "NR-PPAR-gamma": {
        "model": "nr_ppar_gamma",
        "group": "Nuclear Receptor",
        "mechanism": "PPARγ agonist",
        "context": "Metabolic / adipogenic effects; relevant in diabetes and obesity research.",
    },
    "SR-ARE": {
        "model": "sr_are",
        "group": "Stress Response",
        "mechanism": "Antioxidant Response Element activation",
        "context": "Oxidative stress sentinel; flags electrophilic and ROS-generating compounds.",
    },
    "SR-ATAD5": {
        "model": "sr_atad5",
        "group": "Stress Response",
        "mechanism": "ATAD5 genotoxicity reporter",
        "context": "DNA-damage indicator; positives often require genotoxicity follow-up.",
    },
    "SR-HSE": {
        "model": "sr_hse",
        "group": "Stress Response",
        "mechanism": "Heat Shock Element activation",
        "context": "Proteotoxic stress marker; identifies compounds that misfold proteins.",
    },
    "SR-MMP": {
        "model": "sr_mmp",
        "group": "Stress Response",
        "mechanism": "Mitochondrial Membrane Potential disruption",
        "context": "Primary mitochondrial toxicity screen; precursor to cytotoxicity.",
    },
    "SR-p53": {
        "model": "sr_p53",
        "group": "Stress Response",
        "mechanism": "p53 pathway activation",
        "context": "Genotoxicity / DNA damage; mechanistically related to SR-ATAD5.",
    },
}

# ── RDKit import ──────────────────────────────────────────────────────────────

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator
    RDLogger.DisableLog('rdApp.*')
    _morgan_gen = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_BITS)
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False

# ── Helpers ───────────────────────────────────────────────────────────────────

def nnsd_headers():
    h = {"Content-Type": "application/json"}
    if NNSD_KEY:
        h["Authorization"] = f"Bearer {NNSD_KEY}"
    return h


def smiles_to_fp(smiles: str):
    """Return Morgan fingerprint bit list, or None if SMILES is invalid."""
    if not RDKIT_OK:
        return None
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return None
    fp = _morgan_gen.GetFingerprintAsNumPy(mol)
    return fp.tolist()


def assay_train_file(assay_key: str) -> str:
    meta = ASSAYS[assay_key]
    return os.path.join(DATA_ROOT, f"{meta['model']}_train.csv")

def assay_test_file(assay_key: str) -> str:
    meta = ASSAYS[assay_key]
    return os.path.join(DATA_ROOT, f"{meta['model']}_test.csv")

def assay_eval_file(assay_key: str) -> str:
    meta = ASSAYS[assay_key]
    return os.path.join(DATA_ROOT, f"{meta['model']}_eval.json")


def generate_fingerprints(assay_key: str, balance: bool) -> dict:
    """Convert tox21.csv → labelled fingerprint CSV for one assay.
    Returns summary dict on success; raises on error.
    """
    if not RDKIT_OK:
        raise RuntimeError("RDKit not available in this Python environment")

    tox21_csv = os.path.join(DATA_ROOT, "tox21.csv")
    random.seed(RAND_SEED)

    rows, skipped_missing, skipped_invalid = [], 0, 0
    with open(tox21_csv) as f:
        for rec in csv.DictReader(f):
            label_str = rec[assay_key].strip()
            if not label_str:
                skipped_missing += 1
                continue
            mol = Chem.MolFromSmiles(rec["smiles"])
            if mol is None:
                skipped_invalid += 1
                continue
            fp = _morgan_gen.GetFingerprintAsNumPy(mol).tolist()
            rows.append([int(float(label_str))] + fp)

    random.shuffle(rows)
    split = int(len(rows) * TRAIN_FRAC)
    train_rows = rows[:split]

    if balance:
        pos = [r for r in train_rows if r[0] == 1]
        neg = [r for r in train_rows if r[0] == 0]
        if pos and neg:
            # Undersample the majority class (negatives) to match positives.
            # Avoids duplicate fingerprints that cause memorisation/overfitting.
            random.shuffle(neg)
            neg = neg[:len(pos)]
            train_rows = pos + neg
            random.shuffle(train_rows)

    test_rows = rows[split:]

    out_path = assay_train_file(assay_key)
    with open(out_path, "w", newline="") as f:
        csv.writer(f).writerows(train_rows)

    test_path = assay_test_file(assay_key)
    with open(test_path, "w", newline="") as f:
        csv.writer(f).writerows(test_rows)

    pos_total = sum(1 for r in rows if r[0] == 1)
    return {
        "assay":          assay_key,
        "total":          len(rows),
        "positives":      pos_total,
        "negatives":      len(rows) - pos_total,
        "trainRows":      len(train_rows),
        "balanced":       balance,
        "skippedMissing": skipped_missing,
        "skippedInvalid": skipped_invalid,
    }


# ── Regression/classification statistics ─────────────────────────────────────

def compute_stats(labels, values):
    """Compute regression and classification metrics for binary labels + continuous predictions.

    labels : list of int (0 or 1)
    values : list of float (0–1, higher = more likely active)
    Returns a dict with MAE, RMSE, R², Spearman ρ, ROC-AUC, PR-AUC, ±5/10/20%.
    """
    n = len(labels)
    if n == 0:
        return {}

    errors    = [abs(v - l) for v, l in zip(values, labels)]
    sq_errors = [(v - l) ** 2 for v, l in zip(values, labels)]

    mae  = sum(errors) / n
    rmse = math.sqrt(sum(sq_errors) / n)

    mean_l = sum(labels) / n

    # Spearman ρ via average-rank correlation
    def rank_avg(lst):
        order = sorted(range(len(lst)), key=lambda i: lst[i])
        ranks = [0.0] * len(lst)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and lst[order[j + 1]] == lst[order[j]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rl, rv   = rank_avg(list(labels)), rank_avg(values)
    mrl, mrv = sum(rl) / n, sum(rv) / n
    cov      = sum((a - mrl) * (b - mrv) for a, b in zip(rl, rv))
    std_l    = math.sqrt(sum((a - mrl) ** 2 for a in rl))
    std_v    = math.sqrt(sum((b - mrv) ** 2 for b in rv))
    spearman = cov / (std_l * std_v) if std_l * std_v > 0 else 0.0

    pos_total = sum(labels)
    neg_total = n - pos_total

    # ROC-AUC via trapezoidal rule (sort by score descending)
    if pos_total == 0 or neg_total == 0:
        roc_auc = None
    else:
        paired = sorted(zip(values, labels), key=lambda x: -x[0])
        tp = fp = 0
        prev_fpr = prev_tpr = 0.0
        roc_auc = 0.0
        for _, l in paired:
            if l == 1:
                tp += 1
            else:
                fp += 1
            fpr = fp / neg_total
            tpr = tp / pos_total
            roc_auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2.0
            prev_fpr, prev_tpr = fpr, tpr

    # PR-AUC via trapezoidal rule
    if pos_total == 0:
        pr_auc = None
    else:
        paired = sorted(zip(values, labels), key=lambda x: -x[0])
        tp = fp = 0
        prev_rec = 0.0
        prev_prec = 1.0
        pr_auc = 0.0
        for _, l in paired:
            if l == 1:
                tp += 1
            else:
                fp += 1
            prec = tp / (tp + fp)
            rec  = tp / pos_total
            pr_auc += (rec - prev_rec) * (prec + prev_prec) / 2.0
            prev_rec, prev_prec = rec, prec

    def pct_within(tol):
        return round(100.0 * sum(1 for e in errors if e <= tol) / n, 1)

    return {
        "n":        n,
        "mae":      round(mae, 4),
        "rmse":     round(rmse, 4),
        "spearman": round(spearman, 4),
        "rocAuc":   round(roc_auc, 4) if roc_auc is not None else None,
        "prAuc":    round(pr_auc,  4) if pr_auc  is not None else None,
        "within5":  pct_within(0.05),
        "within10": pct_within(0.10),
        "within20": pct_within(0.20),
    }


# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
log.info("tox21_demo starting — port=%d nnsd=%s data=%s", HTTP_PORT, NNSD_URL, DATA_ROOT)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/assays")
def get_assays():
    """Return status for all assays by querying nnsd_client model registry."""
    try:
        r = requests.get(f"{NNSD_URL}/api/models", headers=nnsd_headers(), timeout=5)
        model_map = {m["name"]: m for m in (r.json() if r.ok else [])}
    except Exception:
        model_map = {}

    result = []
    for assay_key, meta in ASSAYS.items():
        model_name = meta["model"]
        m = model_map.get(model_name, {})
        eval_data = {}
        eval_path = assay_eval_file(assay_key)
        if os.path.exists(eval_path):
            try:
                with open(eval_path) as f:
                    eval_data = json.load(f)
            except Exception:
                pass
        result.append({
            "assay":     assay_key,
            "model":     model_name,
            "group":     meta["group"],
            "mechanism": meta["mechanism"],
            "context":   meta["context"],
            "trained":   m.get("trained", False),
            "accuracy":  m.get("lastAccuracy"),
            "trainDate": m.get("lastTrainDate"),
            "train":     eval_data.get("train"),
            "test":      eval_data.get("test"),
        })
    return jsonify(result)


@app.route("/api/assays/<assay_key>/evaluate", methods=["POST"])
def evaluate_assay(assay_key):
    """Run training and test sets through the model and return full regression/classification stats."""
    if assay_key not in ASSAYS:
        return jsonify({"error": f"Unknown assay: {assay_key}"}), 400

    model_name = ASSAYS[assay_key]["model"]

    def load_csv(path):
        labels, rows = [], []
        with open(path) as f:
            for row in csv.reader(f):
                if not row:
                    continue
                labels.append(int(row[0]))
                rows.append([float(x) for x in row[1:]])
        return labels, rows

    def run_predict(rows):
        r = requests.post(
            f"{NNSD_URL}/api/models/{model_name}/predict",
            json={"rows": rows},
            headers=nnsd_headers(),
            timeout=300,
        )
        if not r.ok:
            raise RuntimeError(f"Predict failed: {r.status_code}")
        return [p.get("value", 0.0) for p in r.json().get("predictions", [])]

    test_path = assay_test_file(assay_key)
    if not os.path.exists(test_path):
        return jsonify({"error": "No test set found — train the assay first to generate one"}), 404

    log.info("EVAL START     assay=%s model=%s", assay_key, model_name)

    try:
        test_labels, test_rows = load_csv(test_path)
        if not test_rows:
            return jsonify({"error": "Test set is empty"}), 400
        test_values = run_predict(test_rows)
    except (requests.RequestException, RuntimeError) as e:
        log.error("EVAL FAIL      assay=%s error=%s", assay_key, e)
        return jsonify({"error": str(e)}), 502

    train_stats = None
    train_path = assay_train_file(assay_key)
    if os.path.exists(train_path):
        try:
            train_labels, train_rows = load_csv(train_path)
            train_values = run_predict(train_rows)
            train_stats = compute_stats(train_labels, train_values)
        except Exception:
            pass  # non-fatal; test stats are still returned

    result = {
        "assay": assay_key,
        "test":  compute_stats(test_labels, test_values),
        "train": train_stats,
    }

    ts = result["test"]
    log.info("EVAL DONE      assay=%s test_n=%d roc=%.4f pr=%.4f mae=%.4f",
             assay_key, ts.get("n", 0), ts.get("rocAuc") or 0.0,
             ts.get("prAuc") or 0.0, ts.get("mae", 0.0))

    with open(assay_eval_file(assay_key), "w") as f:
        json.dump(result, f)

    return jsonify(result)


@app.route("/api/assays/<assay_key>/train", methods=["POST"])
def train_assay(assay_key):
    """Prepare fingerprint data then submit training job to nnsd_client."""
    if assay_key not in ASSAYS:
        return jsonify({"error": f"Unknown assay: {assay_key}"}), 400

    body = request.get_json() or {}
    balance = body.get("balance", True)
    retrain = body.get("retrain", False)
    search  = body.get("search",  False)

    mode = "search" if search else ("retrain" if retrain else "train")
    log.info("TRAIN REQUEST  assay=%s model=%s mode=%s balance=%s",
             assay_key, ASSAYS[assay_key]["model"], mode, balance)

    # Domain-specific step: SMILES → fingerprints
    try:
        prep = generate_fingerprints(assay_key, balance)
        log.info("TRAIN PREP     assay=%s total=%d trainRows=%d pos=%d neg=%d",
                 assay_key, prep["total"], prep["trainRows"],
                 prep["positives"], prep["negatives"])
    except Exception as e:
        log.error("TRAIN PREP FAIL assay=%s error=%s", assay_key, e)
        return jsonify({"error": f"Fingerprint generation failed: {e}"}), 500

    # nnsd-relative path (strip DATA_ROOT's parent = /opt/neural/data)
    data_parent = os.path.dirname(DATA_ROOT)   # /opt/neural/data
    train_abs   = assay_train_file(assay_key)
    train_rel   = train_abs[len(data_parent):]  # /tox21/nr_ahr_train.csv

    model_name = ASSAYS[assay_key]["model"]
    if search:
        # Auto-search: omit fixed hyperparams so nnsd_client runs HyperSearch.
        # Do NOT pass the natural-imbalance test file as validationFile: on
        # heavily skewed test sets (3–15% positives) a degenerate model that
        # outputs a constant ≈ 0 achieves lower MSE than a trained model, so
        # the search would install the degenerate trial as "best".  Without a
        # validationFile the search scores on balanced training-set MSE, which
        # correctly penalises stuck / constant-output trials.
        payload = {
            "infile":           train_rel,
            "categorical":      False,
            "groundTruthFirst": True,
        }
    else:
        payload = {
            "infile":                    train_rel,
            "categorical":               False,
            "groundTruthFirst":          True,
            "retrain":                   retrain,
            "trainingSuccessPercentage": 95.0,
            "weightDecay":               1e-4,
            "dropoutRate":               0.5,
            "timeout":                   1200,
        }
    try:
        r = requests.post(f"{NNSD_URL}/api/models/{model_name}/train",
                          json=payload, headers=nnsd_headers(), timeout=10)
        resp = r.json()
        resp["prep"] = prep
        if r.ok:
            log.info("TRAIN ACCEPTED  assay=%s model=%s status=%d", assay_key, model_name, r.status_code)
        else:
            log.warning("TRAIN REJECTED  assay=%s model=%s status=%d resp=%s",
                        assay_key, model_name, r.status_code, r.text[:200])
        return jsonify(resp), r.status_code
    except requests.RequestException as e:
        log.error("TRAIN ERROR     assay=%s model=%s error=%s", assay_key, model_name, e)
        return jsonify({"error": str(e)}), 502


@app.route("/api/assays/<assay_key>/history")
def assay_history(assay_key):
    if assay_key not in ASSAYS:
        return jsonify({"error": f"Unknown assay: {assay_key}"}), 400
    model_name = ASSAYS[assay_key]["model"]
    try:
        r = requests.get(f"{NNSD_URL}/api/models/{model_name}/history",
                         headers=nnsd_headers(), timeout=5)
        return jsonify(r.json()), r.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/predict", methods=["POST"])
def predict():
    """Convert SMILES to fingerprints and run inference across all trained assays.

    Body: {"smiles": ["CCO", "c1ccccc1", ...], "assays": ["NR-AhR", ...]}
    Response: {"compounds": [{"smiles": "CCO", "valid": true,
                               "predictions": {"NR-AhR": {"class": 0}, ...}}, ...]}
    """
    if not RDKIT_OK:
        return jsonify({"error": "RDKit not available"}), 500

    body = request.get_json() or {}
    smiles_list = body.get("smiles", [])
    assay_filter = set(body.get("assays", list(ASSAYS.keys())))

    if not smiles_list:
        return jsonify({"error": "smiles list required"}), 400

    log.info("PREDICT        compounds=%d assays=%d", len(smiles_list), len(assay_filter))

    # Convert SMILES → fingerprints
    compounds = []
    for smi in smiles_list:
        fp = smiles_to_fp(smi)
        compounds.append({
            "smiles":      smi,
            "valid":       fp is not None,
            "fp":          fp,
            "predictions": {},
        })

    valid = [c for c in compounds if c["valid"]]

    # Run inference assay by assay
    for assay_key, meta in ASSAYS.items():
        if assay_key not in assay_filter:
            continue
        model_name = meta["model"]
        rows = [c["fp"] for c in valid]
        if not rows:
            continue
        try:
            r = requests.post(
                f"{NNSD_URL}/api/models/{model_name}/predict",
                json={"rows": rows},
                headers=nnsd_headers(),
                timeout=120,
            )
            if r.ok:
                preds = r.json().get("predictions", [])
                for i, c in enumerate(valid):
                    if i < len(preds):
                        c["predictions"][assay_key] = preds[i]
        except requests.RequestException:
            pass  # model might not be trained; silently omit

    # Strip fp from response (too large to echo back)
    for c in compounds:
        del c["fp"]

    valid_count = sum(1 for c in compounds if c["valid"])
    log.info("PREDICT DONE   valid=%d/%d", valid_count, len(compounds))
    return jsonify({"compounds": compounds})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)
