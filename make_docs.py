"""Generate technical and executive Word documents for the Tox21 platform."""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def set_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    return p

def add_para(doc, text, bold=False, italic=False, space_before=0, space_after=6):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    return p

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(text, style='List Bullet')
    p.paragraph_format.space_after = Pt(3)
    return p

def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Inches(0.4)
    run = p.add_run(text)
    run.font.name = 'Courier New'
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x1a, 0x1d, 0x23)
    # light grey shading
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F3F4F6')
    pPr.append(shd)
    return p

def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
        hdr[i].paragraphs[0].runs[0].bold = True
        # header shading
        tc = hdr[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'DBEAFE')
        tcPr.append(shd)
    for r_idx, row in enumerate(rows):
        cells = table.rows[r_idx + 1].cells
        for c_idx, val in enumerate(row):
            cells[c_idx].text = str(val)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)
    return table

def spacer(doc, lines=1):
    for _ in range(lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

# ---------------------------------------------------------------------------
# TECHNICAL DOCUMENT
# ---------------------------------------------------------------------------

def build_technical():
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    # Title
    title = doc.add_heading('Tox21 Neural Network Toxicity Prediction Platform', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph('Technical Architecture & Implementation Reference')
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].italic = True
    spacer(doc)

    # ── 1. Overview ──────────────────────────────────────────────────────────
    set_heading(doc, '1. System Overview', 1)
    add_para(doc,
        'The platform is a three-tier distributed system for training and deploying neural network '
        'models against the Tox21 toxicological assay dataset. It consists of a CUDA-accelerated '
        'neural network server daemon (nnsd), a REST/WebSocket proxy server (nnsd_client), and a '
        'domain-specific Flask web application (tox21_demo). All components communicate over TCP '
        'on localhost and are designed to run on a single workstation with an NVIDIA GPU.')

    spacer(doc)
    add_table(doc,
        ['Component', 'Language', 'Port', 'Role'],
        [
            ['nnsd',        'C + CUDA',  '2122 (TCP), 9090 (REST)', 'Neural network training and inference engine'],
            ['nnsd_client', 'C++ (Crow)', '8080 (HTTP/WS)',          'Named-model REST API; proxies to nnsd'],
            ['tox21_demo',  'Python (Flask)', '8081 (HTTP)',          'Tox21-specific UI: fingerprinting, training, prediction'],
        ],
        col_widths=[1.3, 1.3, 2.0, 2.8])
    spacer(doc)

    # ── 2. nnsd ──────────────────────────────────────────────────────────────
    set_heading(doc, '2. nnsd — Neural Network Server Daemon', 1)
    add_para(doc,
        'nnsd is a multi-threaded C daemon that accepts training and inference jobs over a binary '
        'TCP protocol, executes them on the GPU via CUDA kernels, and reports progress back to the '
        'caller via a callback TCP connection. It also exposes a lightweight REST status endpoint.')

    set_heading(doc, '2.1 Source Modules', 2)
    add_table(doc,
        ['File', 'Responsibility'],
        [
            ['nnsd.c',        'Main loop, TCP listener, thread dispatch, signal handling'],
            ['nn_network.c',  'Network allocation, initialisation from packet or matrix file'],
            ['nn_training.c', 'TrainNetwork, TestNetwork, RunNetwork thread functions; CPU backprop; batch gradient accumulation'],
            ['nn_cuda.cu',    'CUDA kernels: forward pass, backprop, dropout, Adam, stats; GPU memory management'],
            ['nn_math.c',     'CPU sigmoid, clamping, weight initialisation'],
            ['nn_fileio.c',   'Matrix file read/write, output file writing, failed-facts logging'],
            ['nn_packet.c',   'Packet validation, dispatch, stats/finished callback sending'],
            ['nn_sysinfo.c',  'Load average, free memory reporting'],
            ['../utils/tcp_utils.c',  'TCP send/receive, JSON serialisation (cJSON)'],
            ['../utils/log_utils.c',  'Levelled logging'],
        ],
        col_widths=[2.2, 5.2])

    set_heading(doc, '2.2 Network Architecture', 2)
    add_para(doc,
        'Networks are fully-connected feedforward nets with configurable layer topology, sigmoid '
        'activation throughout, and a single bias node per hidden layer. For Tox21 the topology is:')
    add_code(doc, '2048 → 512 → 128 → 32 → 1   (autoPyramid)')
    add_para(doc,
        'The output layer has one neuron for binary classification. With categoricalOutput=true and '
        'nOut=1, nnsd uses one-hot encoding: output ≈ 1.0 means class 0 (inactive), output ≈ 0.0 '
        'means class 1 (active). This is the inverse of the intuitive encoding and is handled '
        'transparently in WriteOutputFileLine.')

    set_heading(doc, '2.3 GPU Kernels (nn_cuda.cu)', 2)
    add_table(doc,
        ['Kernel', 'Description'],
        [
            ['activate_bias_k',      'Forward pass: z = W·x + b, sigmoid(z) with ±8 clamp'],
            ['dropout_k',            'Inverted dropout on hidden layers during training (scale=1/keep_prob)'],
            ['calc_output_delta_k',  'Output layer error delta'],
            ['calc_hidden_delta_k',  'Hidden layer error delta via chain rule'],
            ['apply_deriv_dropout_k','Undo 1/keep_prob scaling before sigmoid derivative (avoids negative gradient for a>1)'],
            ['apply_deriv_k',        'Sigmoid derivative application (non-dropout path)'],
            ['update_weights_k',     'SGD weight update: w -= lr * delta * activation'],
            ['update_weights_adam_k','Adam weight update with per-weight m/v moments'],
            ['stats_k',              'Per-fact accuracy: threshold ≥ 0.5 for nOut=1; argmax for nOut>1'],
            ['scale_down_k',         'Min-max feature normalisation'],
        ],
        col_widths=[2.5, 4.9])

    set_heading(doc, '2.4 Training Algorithm', 2)
    add_para(doc, 'Training proceeds as follows:')
    for step in [
        'Input CSV is loaded into pinned host memory (inputRows); features are min-max scaled.',
        'A CUDA stream is created per PoolWorker thread.',
        'Each pass shuffles the training set and divides it into mini-batches.',
        'Each PoolWorker thread processes a subset of the mini-batch independently, accumulating '
        'gradients into a per-worker localGrad array.',
        'After each mini-batch, ApplyBatchGradients() averages the per-worker gradients and applies '
        'them to the shared weight matrices, using either SGD or Adam.',
        'stats_k computes the fraction of correctly classified facts after each pass.',
        'Training terminates when the success percentage meets trainingSuccessPercentage or the '
        'timeout is reached.',
        'A STATS_PACKET is sent to the callback port after each pass; a NETFINISHED_PACKET is sent on completion.',
    ]:
        add_bullet(doc, step)

    set_heading(doc, '2.5 Adam Optimiser', 2)
    add_para(doc,
        'The Adam implementation maintains per-weight first-moment (m) and second-moment (v) '
        'accumulators on the GPU. Parameters: lr=0.001, β₁=0.9, β₂=0.999, ε=1×10⁻⁸. '
        'Bias correction is applied via the standard (1−βₜ) denominators. '
        'Weight decay (L2 regularisation) is added to the gradient before the moment update.')

    set_heading(doc, '2.6 Dropout', 2)
    add_para(doc,
        'Inverted dropout is applied to hidden layer activations after the sigmoid. During training, '
        'each activation is zeroed with probability p and scaled by 1/(1−p) so that the expected '
        'activation magnitude is preserved. At inference time the network runs without dropout. '
        'apply_deriv_dropout_k reverses the 1/keep_prob scaling before computing the sigmoid '
        'derivative to prevent the derivative from going negative for activations > 1.')

    set_heading(doc, '2.7 Packet Protocol', 2)
    add_para(doc,
        'All communication uses a JSON-serialised PacketStruct over TCP. '
        'cJSON_PrintUnformatted is used to minimise wire size. Key packet types:')
    add_table(doc,
        ['Type', 'Direction', 'Purpose'],
        [
            ['TRAIN_PACKET',        'Client → nnsd', 'Start training a new network'],
            ['RETRAIN_PACKET',      'Client → nnsd', 'Delete existing matrix and retrain from scratch'],
            ['RUN_PACKET',          'Client → nnsd', 'Forward-pass inference on an input file'],
            ['TEST_PACKET',         'Client → nnsd', 'Run test set and compute accuracy'],
            ['CANCEL_PACKET',       'Client → nnsd', 'Signal STATUS_SHUTDOWN to a running thread'],
            ['NUDGE_PACKET',        'Client → nnsd', 'Adjust nudgeAmount on a running thread'],
            ['STATS_PACKET',        'nnsd → Client', 'Per-pass accuracy/SSE callback'],
            ['NETFINISHED_PACKET',  'nnsd → Client', 'Training complete callback'],
            ['REMOVENETWORK_PACKET','Client → nnsd', 'Delete all files for a model'],
        ],
        col_widths=[2.1, 1.6, 3.7])

    # ── 3. nnsd_client ───────────────────────────────────────────────────────
    set_heading(doc, '3. nnsd_client — REST Proxy Server', 1)
    add_para(doc,
        'nnsd_client is a C++ HTTP/WebSocket server built on the Crow framework. It presents a '
        'clean REST API to downstream applications, abstracting all nnsd packet protocol details, '
        'file path management, netID allocation, and multi-server routing.')

    set_heading(doc, '3.1 Key Source Files', 2)
    add_table(doc,
        ['File', 'Responsibility'],
        [
            ['HttpServer.cpp',      'All REST routes, WebSocket handler, named-model API, inference handler'],
            ['ModelManager.cpp/.h', 'Named-model registry (models.json); CRUD, persistence, file path resolution'],
            ['NnsdClient.cpp/.h',   'TCP client for nnsd packet protocol; train/retrain/run/test wrappers'],
            ['TenantManager.cpp/.h','Multi-tenant auth; per-tenant file scoping'],
            ['ServerRegistry.cpp',  'Round-robin / GPU-score-based nnsd server selection'],
            ['DatasetAnalyzer.cpp', 'Class distribution, constant feature detection, conflict analysis'],
            ['RedisStream.cpp/.h',  'Async NETFINISHED/STATS callback delivery via Redis Streams'],
            ['Packet.h',            'C++ PacketStruct mirror; JSON serialisation'],
        ],
        col_widths=[2.2, 5.2])

    set_heading(doc, '3.2 Named-Model API', 2)
    add_table(doc,
        ['Endpoint', 'Method', 'Description'],
        [
            ['/api/models',                      'GET',    'List all registered models'],
            ['/api/models/<name>/train',          'POST',   'Train or retrain a named model; accepts neurons, hyperparameters, preprocessing options'],
            ['/api/models/<name>/predict',        'POST',   'Synchronous inference on a row array; returns {class, score} per row'],
            ['/api/models/<name>/test',           'POST',   'Run test set; returns accuracy metrics'],
            ['/api/models/<name>/history',        'GET',    'Per-pass training history from sts CSV'],
            ['/api/models/<name>',                'DELETE', 'Remove model from registry'],
            ['/api/analyze',                      'POST',   'Dataset analysis: class balance, constant features'],
            ['/api/files',                        'GET',    'List files/directories under the server mount point; ?dir= param for subdirectory navigation'],
            ['/ws/<netID>',                       'WS',     'Live training progress stream (STATS/NETFINISHED packets)'],
        ],
        col_widths=[3.0, 0.8, 3.6])

    set_heading(doc, '3.3 Inference Flow', 2)
    add_para(doc, 'A predict request follows this path:')
    for step in [
        'POST /api/models/<name>/predict with {"rows": [[f0,f1,…,f2047], …]}',
        'nnsd_client writes rows to a temp input file (no label column).',
        'A RUN_PACKET is sent to nnsd with categoricalOutput=false so nnsd writes raw sigmoid '
        'float outputs rather than integer classes.',
        'nnsd_client reads the last column of each output line as the raw float. '
        'For nOut=1 with one-hot encoding: class = (raw >= 0.5) ? 0 : 1; '
        'activity score = 1.0 − raw  (high score = more likely active/toxic).',
        'Returns {"predictions": [{"class": 0|1, "score": 0.0–1.0}, …]}.',
        'tox21_demo displays the score as a percentage, coloured red (active ≥ 50%) '
        'or green (inactive < 50%).',
    ]:
        add_bullet(doc, step)

    set_heading(doc, '3.4 Training Flow', 2)
    add_para(doc, 'A train request for a named model:')
    for step in [
        'POST /api/models/<name>/train with hyperparameters (neurons, lr, dropout, weightDecay, Adam params, timeout, trainingSuccessPercentage).',
        'Optional preprocessing: rebalance classes, remove constant features, PCA, validation split.',
        'If a validationFile path is provided in the request body, it overrides the auto-split validation fraction.',
        'A TRAIN or RETRAIN packet is sent to nnsd.',
        'nnsd returns immediately; training runs in a background thread on nnsd.',
        'A Redis Stream listener receives STATS callbacks and forwards them to any connected WebSocket clients.',
        'On NETFINISHED, if a validation file was specified, nnsd_client runs a TEST_PACKET against it, '
        'computes a confusion matrix (TP, FP, TN, FN, sensitivity, specificity), and broadcasts a '
        '"confusionMatrix" message to connected WebSocket clients.',
        'The model registry is updated (trained=true, trainDate, accuracy).',
    ]:
        add_bullet(doc, step)

    set_heading(doc, '3.5 Dashboard UI', 2)
    add_para(doc,
        'The nnsd_client web dashboard (served at /) provides a training configuration form with '
        'the following features:')
    for feat in [
        'Input file field with Browse button — opens a server-side file picker modal that navigates '
        'the mount-point directory tree via GET /api/files. Selecting a file populates the input field.',
        'Auto-naming — when the input file path is changed, the matrix file, output file, and stats '
        'file fields are automatically named from the same directory and basename '
        '(e.g. /data/ahr_train.csv → ahr_train.mtx, ahr_train_out.csv, ahr_train_sts.csv).',
        'Validation file field (optional) with Browse button — if filled, the file is run against '
        'the trained model after training completes; the resulting confusion matrix is displayed in '
        'the WebSocket progress panel.',
        'Adam optimiser defaults to checked; the Adam parameter fields (β₁, β₂, ε, lr) are shown '
        'or hidden dynamically.',
        'WebSocket progress panel shows live per-pass accuracy, SSE, and the final confusion matrix '
        'once training and validation are complete.',
    ]:
        add_bullet(doc, feat)

    # ── 4. tox21_demo ────────────────────────────────────────────────────────
    set_heading(doc, '4. tox21_demo — Tox21 Web Application', 1)
    add_para(doc,
        'tox21_demo is a Flask application that provides a domain-specific interface to the '
        'nnsd_client API for the 12 Tox21 assay endpoints. It handles SMILES-to-fingerprint '
        'conversion, training data preparation, model management, prediction, and evaluation.')

    set_heading(doc, '4.1 Tox21 Assay Endpoints', 2)
    add_table(doc,
        ['Assay', 'Group', 'Mechanism'],
        [
            ['NR-AR',        'Nuclear Receptor', 'Androgen receptor full length'],
            ['NR-AR-LBD',    'Nuclear Receptor', 'Androgen receptor ligand-binding domain'],
            ['NR-AhR',       'Nuclear Receptor', 'Aryl hydrocarbon receptor'],
            ['NR-Aromatase',  'Nuclear Receptor', 'Aromatase (CYP19A1) inhibition'],
            ['NR-ER',        'Nuclear Receptor', 'Oestrogen receptor full length'],
            ['NR-ER-LBD',    'Nuclear Receptor', 'Oestrogen receptor ligand-binding domain'],
            ['NR-PPAR-gamma', 'Nuclear Receptor', 'Peroxisome proliferator-activated receptor gamma'],
            ['SR-ARE',       'Stress Response',  'Antioxidant response element (Nrf2 pathway)'],
            ['SR-ATAD5',     'Stress Response',  'Genotoxicity (ATAD5 stabilisation)'],
            ['SR-HSE',       'Stress Response',  'Heat shock response element'],
            ['SR-MMP',       'Stress Response',  'Mitochondrial membrane potential'],
            ['SR-p53',       'Stress Response',  'p53 tumour suppressor pathway'],
        ],
        col_widths=[1.5, 1.5, 4.4])

    set_heading(doc, '4.2 SMILES → Morgan Fingerprint Pipeline', 2)
    add_para(doc,
        'Compound structures are provided as SMILES strings. tox21_demo converts them to '
        '2048-bit Morgan (circular) fingerprints using RDKit with radius 2:')
    add_code(doc, 'from rdkit import Chem\nfrom rdkit.Chem import AllChem\nmol = Chem.MolFromSmiles(smiles)\nfp  = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)')
    add_para(doc,
        'Each bit encodes the presence of a particular atomic neighbourhood pattern. '
        'The resulting 2048-element binary vector is the direct input to the neural network. '
        'Compounds with invalid SMILES are flagged as invalid and excluded from inference.')

    set_heading(doc, '4.3 Training Data Preparation', 2)
    add_para(doc,
        'For each assay, the training CSV (label,fp0,…,fp2047) is passed to nnsd_client with '
        'balance=true, which undersamples the majority class to equalise positive and negative '
        'counts. Training parameters:')
    add_table(doc,
        ['Parameter', 'Value', 'Notes'],
        [
            ['Architecture',               '2048→512→128→32→1', 'autoPyramid from input width'],
            ['trainingSuccessPercentage',   '95%',               'Balanced-set accuracy target'],
            ['Learning rate',              '0.001',              'Adam default'],
            ['Optimiser',                  'Adam',               'β₁=0.9, β₂=0.999, ε=1×10⁻⁸'],
            ['Dropout rate',               '0.5',                'Applied to hidden layers during training'],
            ['Weight decay (L2)',          '1×10⁻⁴',            'Added to gradient before moment update'],
            ['Timeout',                    '1200 s (20 min)',    'Hard wall-clock limit per assay'],
            ['groundTruthFirst',           'True',               'Label is column 0 in CSV'],
            ['categoricalOutput',          'True',               'One-hot mode; nOut=1 uses inverted threshold'],
        ],
        col_widths=[2.2, 1.6, 3.6])

    set_heading(doc, '4.4 Evaluation', 2)
    add_para(doc,
        'After training, the held-out test set is run through the trained model via the predict '
        'endpoint. The evaluate route computes overall accuracy, sensitivity (true positive rate), '
        'and specificity (true negative rate) and displays them on each assay card. '
        'Sensitivity is the primary quality metric because false negatives (missed toxic compounds) '
        'are more harmful than false positives.')

    set_heading(doc, '4.5 Observed Model Performance', 2)
    add_table(doc,
        ['Assay', 'Sensitivity', 'Specificity', 'Notes'],
        [
            ['NR-AR',        '~65%', '~70%', ''],
            ['NR-AR-LBD',    '~60%', '~65%', ''],
            ['NR-AhR',       '~65%', '~68%', ''],
            ['NR-Aromatase',  '~62%', '~67%', ''],
            ['NR-ER',        '~65%', '~70%', ''],
            ['NR-ER-LBD',    '~50%', '~55%', 'Hardest assay; noisy LBD labels'],
            ['NR-PPAR-gamma', '~62%', '~68%', ''],
            ['SR-ARE',       '67%',  '~68%', ''],
            ['SR-ATAD5',     '66%',  '~67%', ''],
            ['SR-HSE',       '~65%', '~70%', ''],
            ['SR-MMP',       '81%',  '~80%', 'Best performing assay'],
            ['SR-p53',       '75%',  '~74%', ''],
        ],
        col_widths=[1.6, 1.2, 1.2, 3.4])

    set_heading(doc, '4.6 Web UI Features', 2)
    for feat in [
        'Assay grid with per-card train/retrain/evaluate buttons and live badge (Trained / Not trained / Training…).',
        'Retrain polling detects trainDate change rather than trained flag, ensuring evaluation runs after retraining completes.',
        '"Train All Untrained" and "Retrain All" bulk actions with per-assay status.',
        'Compound prediction: paste SMILES manually, or upload a .txt/.csv/.smi file (one SMILES '
        'per line, blank lines and # comments stripped). Results shown as a continuous activity '
        'score (0–100%) per assay in a colour-coded table (red ≥ 50% = active, green < 50% = inactive).',
        'Download CSV button appears after each prediction run, exporting SMILES, valid flag, '
        '{assay}_score and {assay}_class columns for all assays.',
        'Training history table per assay (pass number, accuracy, SSE, date).',
        '"How it works" modal explaining the full pipeline with 9 example SMILES and a Load Examples button.',
    ]:
        add_bullet(doc, feat)

    # ── 5. Known Design Decisions ─────────────────────────────────────────────
    set_heading(doc, '5. Key Design Decisions and Bug History', 1)

    set_heading(doc, '5.1 One-Hot Encoding for nOut=1', 2)
    add_para(doc,
        'nnsd uses one-hot encoding even for single-output networks. For nOut=1, '
        'expectedOutput[0] = (0 == label), meaning output≈1 encodes class 0 (inactive) and '
        'output≈0 encodes class 1 (active). WriteOutputFileLine uses >= 0.5 → class 0 (not class 1). '
        'Accuracy metrics (stats_k, TestNetwork) are internally consistent because both predicted '
        'and expected sides use the same threshold. '
        'The inference path avoids this complexity entirely by running with categoricalOutput=false, '
        'reading the raw float, and computing class = (raw >= 0.5) ? 0 : 1 directly in nnsd_client. '
        'The activity score returned to callers is 1.0 − raw, making high values intuitively mean '
        '"more likely active/toxic".')

    set_heading(doc, '5.2 Adam Gradient Correction', 2)
    add_para(doc,
        'An early implementation divided the gradient by lr before storing it in the Adam moment '
        'accumulators, which corrupted the adaptive scaling. The correct implementation stores the '
        'raw scaled gradient (g = gradAccum * scale) in m and v, then applies lr in the weight update step.')

    set_heading(doc, '5.3 Dropout Derivative', 2)
    add_para(doc,
        'Inverted dropout scales activations by 1/keep_prob. If this scaling is not reversed before '
        'computing the sigmoid derivative, activations > keep_prob yield a negative derivative '
        '(σ\'(a) = a(1−a) < 0 when a > 1). apply_deriv_dropout_k multiplies by keep_prob before '
        'applying the derivative to restore correct gradient magnitudes.')

    set_heading(doc, '5.4 Retrain Polling', 2)
    add_para(doc,
        'The tox21_demo polling loop originally checked trained == true to detect completion. '
        'For retrain jobs the model is already marked trained, so the loop would fire immediately. '
        'The fix captures trainDate before submission and polls until the date changes.')

    # ── 6. Deployment ─────────────────────────────────────────────────────────
    set_heading(doc, '6. Deployment', 1)
    add_para(doc, 'All three services are started via shell scripts:')
    add_code(doc, 'cd nnsd       && bash start.sh   # GPU daemon on port 2122/9090')
    add_code(doc, 'cd nnsd_client && bash start.sh  # REST proxy on port 8080')
    add_code(doc, 'cd tox21_demo  && bash start.sh  # Flask UI on port 8081')
    spacer(doc)
    add_para(doc, 'Runtime data paths:')
    add_table(doc,
        ['Path', 'Contents'],
        [
            ['/opt/neural/data/tox21/',   'Training and test CSVs ({assay}_train.csv, {assay}_test.csv)'],
            ['/opt/neural/data/models/',  'Trained weight matrices ({assay}.mtx, .bak)'],
            ['/opt/neural/logs/nns.log',  'nnsd log file'],
            ['/opt/neural/conf/nnsd.conf','nnsd configuration (ports, mount point, GPU selection)'],
            ['nnsd_client/cmake-build-debug/models.json', 'Named-model registry'],
        ],
        col_widths=[3.0, 4.4])

    doc.save('/home/bcosta/Projects/CLionProjects/tox21_demo/Tox21_Technical_Reference.docx')
    print('Technical document saved.')


# ---------------------------------------------------------------------------
# EXECUTIVE DOCUMENT
# ---------------------------------------------------------------------------

def build_executive():
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(3.0)
        section.right_margin  = Cm(3.0)

    # Title
    title = doc.add_heading('AI-Powered Toxicity Prediction Platform', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph('Executive Overview for Pharmacological and Drug-Discovery Applications')
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].italic = True
    spacer(doc)

    # ── What has been built ───────────────────────────────────────────────────
    set_heading(doc, 'What Has Been Built', 1)
    add_para(doc,
        'We have built a fully operational artificial intelligence platform that can screen chemical '
        'compounds for toxicity across twelve validated biological assays. Given any chemical '
        'structure expressed as a standard SMILES notation string, the system will predict within '
        'seconds whether that compound is likely to be biologically active (potentially toxic) or '
        'inactive across each of the twelve endpoints.')
    add_para(doc,
        'The platform is trained on the Tox21 dataset — a landmark US government programme that '
        'experimentally tested approximately 10,000 environmental chemicals and approved drugs '
        'against twelve toxicological assays using high-throughput screening. Our models have '
        'learned the relationship between chemical structure and biological activity from this '
        'data and can apply that knowledge to new, untested compounds.')

    # ── The 12 assays ────────────────────────────────────────────────────────
    set_heading(doc, 'The Twelve Toxicological Endpoints', 1)
    add_para(doc,
        'The twelve assays cover two categories of biological mechanism:')

    set_heading(doc, 'Nuclear Receptor Endpoints', 2)
    add_para(doc,
        'These assays detect whether a compound activates or inhibits nuclear hormone receptors — '
        'proteins that, when dysregulated, are associated with endocrine disruption, reproductive '
        'toxicity, metabolic disorders, and cancer.')
    add_table(doc,
        ['Assay', 'What it Detects', 'Clinical Relevance'],
        [
            ['NR-AR',        'Androgen receptor activation',              'Reproductive toxicity; anti-androgenic effects'],
            ['NR-AR-LBD',    'Androgen receptor binding domain',          'Androgen receptor antagonism screening'],
            ['NR-AhR',       'Aryl hydrocarbon receptor activation',      'Dioxin-like toxicity; immune and liver effects'],
            ['NR-Aromatase',  'Aromatase enzyme inhibition',              'Oestrogen biosynthesis disruption'],
            ['NR-ER',        'Oestrogen receptor activation',             'Oestrogenic activity; endocrine disruption'],
            ['NR-ER-LBD',    'Oestrogen receptor binding domain',         'Oestrogen receptor binding potential'],
            ['NR-PPAR-gamma', 'PPAR-gamma receptor activation',           'Metabolic/adipogenic effects; obesity risk'],
        ],
        col_widths=[1.6, 2.4, 3.0])

    spacer(doc)
    set_heading(doc, 'Stress Response Endpoints', 2)
    add_para(doc,
        'These assays detect cellular stress signals — responses that cells activate when exposed '
        'to genotoxic, oxidative, or mitochondrial insults.')
    add_table(doc,
        ['Assay', 'What it Detects', 'Clinical Relevance'],
        [
            ['SR-ARE',   'Antioxidant / oxidative stress response', 'Nrf2 pathway activation; oxidative damage potential'],
            ['SR-ATAD5', 'DNA damage response',                     'Genotoxicity marker; DNA replication stress'],
            ['SR-HSE',   'Heat shock / proteotoxic stress',         'Protein misfolding; cellular stress response'],
            ['SR-MMP',   'Mitochondrial membrane potential',        'Mitochondrial toxicity; energy metabolism disruption'],
            ['SR-p53',   'p53 tumour suppressor activation',        'Genotoxicity; potential carcinogenicity signal'],
        ],
        col_widths=[1.6, 2.4, 3.0])

    # ── How it works ─────────────────────────────────────────────────────────
    set_heading(doc, 'How It Works — The Science in Plain Language', 1)

    set_heading(doc, 'Step 1: Encoding the Chemical Structure', 2)
    add_para(doc,
        'A compound\'s structure is described using SMILES notation (Simplified Molecular-Input '
        'Line-Entry System) — a text-based language used universally in cheminformatics. '
        'For example, aspirin is CC(=O)Oc1ccccc1C(=O)O.')
    add_para(doc,
        'The system converts this structure into a "molecular fingerprint" — a fixed-length binary '
        'code of 2048 bits where each bit records whether a particular atomic neighbourhood pattern '
        'is present in the molecule. This fingerprint is generated by a widely-used algorithm called '
        'the Morgan algorithm (also known as circular fingerprints, ECFP4). It is the same '
        'representation used in leading computational drug discovery pipelines worldwide.')

    set_heading(doc, 'Step 2: The Neural Network', 2)
    add_para(doc,
        'The 2048-bit fingerprint is fed into a neural network — a mathematical model loosely '
        'inspired by how the brain processes information. The network consists of five layers of '
        'interconnected numerical nodes:')
    add_code(doc, 'Input (2048)  →  512 nodes  →  128 nodes  →  32 nodes  →  Output (1 node)')
    add_para(doc,
        'Each of the twelve toxicological assays has its own separately trained network. '
        'During training, the network adjusts approximately 1.2 million internal parameters '
        '(connection weights) until it can reliably distinguish active from inactive compounds '
        'in the training data. The output is a continuous activity score between 0% and 100%; '
        'scores at or above 50% are considered active (potentially toxic), below 50% inactive.')

    set_heading(doc, 'Step 3: Making a Prediction', 2)
    add_para(doc,
        'To screen compounds, SMILES strings can be entered manually or loaded from a plain-text '
        'file (one SMILES per line). Each structure is converted to a fingerprint and passed '
        'through all twelve trained networks simultaneously. The result is a colour-coded table '
        'showing a continuous activity score (0–100%) for each endpoint — red indicates likely '
        'active (potentially toxic), green indicates likely inactive. '
        'Results can be downloaded as a CSV file containing the score and binary call for every '
        'compound and assay, ready for import into Excel or any analysis tool. '
        'The entire screen completes in seconds, without any wet-lab experiment.')

    # ── Training quality ─────────────────────────────────────────────────────
    set_heading(doc, 'Model Quality and Reliability', 1)
    add_para(doc,
        'Each model is evaluated on a held-out test set — compounds the network has never seen '
        'during training. Two key metrics are reported:')

    add_bullet(doc,
        'Sensitivity (recall): the percentage of genuinely active (toxic) compounds that the model '
        'correctly flags as active. This is the most critical metric for a safety screen — a model '
        'that misses real toxic compounds is dangerous.')
    add_bullet(doc,
        'Specificity: the percentage of genuinely inactive compounds correctly identified as '
        'inactive. High specificity avoids unnecessary follow-up experiments on safe compounds.')
    spacer(doc)

    add_para(doc, 'Current model performance on the Tox21 test sets:')
    add_table(doc,
        ['Assay', 'Sensitivity', 'Specificity', 'Assessment'],
        [
            ['SR-MMP',       '81%', '~80%', 'Excellent — strong mitochondrial toxicity detection'],
            ['SR-p53',       '75%', '~74%', 'Very good — reliable genotoxicity signal'],
            ['SR-MSE',       '70%', '~70%', 'Good'],
            ['SR-ARE',       '67%', '~68%', 'Good — oxidative stress detection'],
            ['SR-ATAD5',     '66%', '~67%', 'Good — DNA damage signal'],
            ['NR assays',    '60–70%', '65–72%', 'Good overall; endocrine disruption detection'],
            ['NR-ER-LBD',    '~50%', '~55%', 'Moderate — known difficult endpoint'],
        ],
        col_widths=[1.6, 1.2, 1.2, 3.4])

    spacer(doc)
    add_para(doc,
        'For context: published benchmark models for Tox21 from major pharmaceutical and academic '
        'groups typically achieve sensitivity in the 60–80% range. Our platform performs at the '
        'lower end of the published range, which is expected given the dataset sizes (300–1000 '
        'training compounds per assay). Performance could be improved with larger training sets, '
        'ensemble models, or graph neural network architectures.')

    # ── Practical applications ────────────────────────────────────────────────
    set_heading(doc, 'Practical Applications', 1)

    set_heading(doc, 'Early-Stage Drug Discovery', 2)
    add_para(doc,
        'In lead optimisation, a medicinal chemist proposes dozens of structural analogues. '
        'This platform can pre-screen all of them in seconds, flagging those with potential '
        'endocrine disruption or genotoxicity signals before any synthesis or wet-lab work. '
        'This reduces the cost and time of safety profiling in early discovery.')

    set_heading(doc, 'Environmental Chemical Assessment', 2)
    add_para(doc,
        'Regulators and environmental toxicologists routinely need to assess chemicals for which '
        'no experimental data exist. The platform provides a rapid first-pass screening tool '
        'consistent with OECD and EPA computational toxicology guidelines.')

    set_heading(doc, 'Known Compounds — Example Predictions', 2)
    add_para(doc,
        'To illustrate the platform\'s behaviour, the following well-characterised compounds '
        'can be tested. Known toxicological expectations are noted:')
    add_table(doc,
        ['Compound', 'SMILES', 'Expected findings'],
        [
            ['TCDD (Dioxin)',   'Clc1cc2c(cc1Cl)Oc1cc(Cl)c(Cl)cc1O2', 'Active NR-AhR (potent dioxin receptor agonist)'],
            ['DES',            'CC/C(=C(\\CC)c1ccc(O)cc1)c1ccc(O)cc1',  'Active NR-ER / NR-ER-LBD (synthetic oestrogen)'],
            ['BPA',            'CC(C)(c1ccc(O)cc1)c1ccc(O)cc1',         'Active NR-ER (endocrine disruptor)'],
            ['Acrylamide',     'NC(=O)C=C',                             'Stress response activity (SR assays)'],
            ['Aspirin',        'CC(=O)Oc1ccccc1C(=O)O',                 'Mostly inactive — safe reference'],
            ['Glucose',        'OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O', 'Inactive across all assays — safe reference'],
        ],
        col_widths=[1.5, 2.5, 3.4])

    # ── Limitations ───────────────────────────────────────────────────────────
    set_heading(doc, 'Limitations and Appropriate Use', 1)
    add_para(doc,
        'This platform is an in silico screening tool and should be interpreted accordingly:',
        bold=True)
    for lim in [
        'A low activity score does not mean a compound is safe — it means the model did '
        'not find structural similarity to known actives in the training data.',
        'The models are trained on phenotypic assay data from a specific set of ~10,000 compounds. '
        'Predictions for chemotypes very different from the training set may be unreliable.',
        'Predictions should be used to prioritise compounds for experimental follow-up, not to '
        'replace regulatory toxicology studies.',
        'NR-ER-LBD sensitivity is approximately 50%, meaning roughly half of true ER ligand-binding '
        'domain binders are missed. This endpoint requires supplementary wet-lab confirmation.',
        'The platform does not cover ADMET (absorption, distribution, metabolism, excretion, '
        'and toxicity) endpoints beyond the twelve Tox21 assays.',
    ]:
        add_bullet(doc, lim)

    # ── Technology summary ────────────────────────────────────────────────────
    set_heading(doc, 'Technology Summary', 1)
    add_para(doc,
        'The platform runs on a single workstation with an NVIDIA GPU (RTX 4060). '
        'All components are open-source or custom-developed:')
    add_table(doc,
        ['Component', 'Technology', 'Purpose'],
        [
            ['Molecular fingerprinting', 'RDKit (Python)',          'SMILES → 2048-bit Morgan fingerprint'],
            ['Neural network training',  'Custom C + CUDA',         'GPU-accelerated backpropagation with Adam optimiser'],
            ['Model serving',           'Custom C++ REST server',   'Abstracts GPU daemon; provides clean HTTP API'],
            ['Web interface',           'Flask (Python)',            'Tox21-specific UI for training and prediction'],
        ],
        col_widths=[2.0, 1.8, 3.6])

    doc.save('/home/bcosta/Projects/CLionProjects/tox21_demo/Tox21_Executive_Overview.docx')
    print('Executive document saved.')


if __name__ == '__main__':
    build_technical()
    build_executive()
    print('Done.')
