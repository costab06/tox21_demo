#!/usr/bin/env python3
"""Generate Tox21 Demo explainer Word document."""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_heading_color(paragraph, r, g, b):
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(r, g, b)


def add_heading(doc, text, level, r=0x1F, g=0x4E, b=0x79):
    h = doc.add_heading(text, level=level)
    set_heading_color(h, r, g, b)
    return h


def add_table_row(table, cells, bold_first=False):
    row = table.add_row()
    for i, (cell, text) in enumerate(zip(row.cells, cells)):
        cell.text = text
        if bold_first and i == 0:
            cell.paragraphs[0].runs[0].bold = True
    return row


def shade_row(row, hex_color="D9E1F2"):
    for cell in row.cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_color)
        tcPr.append(shd)


doc = Document()

# ── Page margins ──────────────────────────────────────────────────────────────
section = doc.sections[0]
section.left_margin   = Inches(1.0)
section.right_margin  = Inches(1.0)
section.top_margin    = Inches(1.0)
section.bottom_margin = Inches(1.0)

# ── Title ─────────────────────────────────────────────────────────────────────
title = doc.add_heading("Understanding the Tox21 Demo", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_heading_color(title, 0x1F, 0x4E, 0x79)

doc.add_paragraph(
    "This document explains what the Tox21 dataset is, what each of the 12 biological "
    "assays measures, why that matters, and how the demo application uses a trained "
    "neural network to predict chemical toxicity from molecular structure."
)

# ── Section 1: What is Tox21 ──────────────────────────────────────────────────
add_heading(doc, "1. What is Tox21?", level=1)

doc.add_paragraph(
    "Tox21 — Toxicology in the 21st Century — is a collaborative research programme "
    "run by the US National Institutes of Health (NIH), the Environmental Protection "
    "Agency (EPA), and the Food and Drug Administration (FDA). Its goal is to shift "
    "toxicology away from slow, expensive animal studies toward fast, scalable, "
    "cell-based screening."
)
doc.add_paragraph(
    "The programme tested approximately 10,000 chemical compounds — including "
    "industrial chemicals, pesticides, food additives, and drug candidates — against "
    "12 biological assays. For each compound–assay pair the result is binary: "
    "1 (toxic signal detected) or 0 (no signal detected). Compounds with missing "
    "data for a particular assay are excluded from training for that assay."
)
doc.add_paragraph(
    "The value of this dataset to the wider scientific community is that it provides "
    "a standardised, publicly available benchmark for training and evaluating machine "
    "learning models that can predict whether a novel, untested chemical is likely to "
    "be toxic — before it is ever synthesised or administered."
)

# ── Section 2: What is a SMILES string ────────────────────────────────────────
add_heading(doc, "2. What is a SMILES String?", level=1)

doc.add_paragraph(
    "SMILES (Simplified Molecular Input Line Entry System) is a compact text notation "
    "for describing a molecule's chemical structure. Rather than requiring a 3-D "
    "diagram, the entire structure of even a complex drug molecule can be written as a "
    "single line of ASCII text."
)

p = doc.add_paragraph("Common examples:")
tbl = doc.add_table(rows=1, cols=2)
tbl.style = "Table Grid"
shade_row(tbl.rows[0], "BDD7EE")
tbl.rows[0].cells[0].text = "SMILES"
tbl.rows[0].cells[1].text = "Compound"
for run in tbl.rows[0].cells[0].paragraphs[0].runs:
    run.bold = True
for run in tbl.rows[0].cells[1].paragraphs[0].runs:
    run.bold = True

examples = [
    ("CCO",                                   "Ethanol (drinking alcohol)"),
    ("c1ccccc1",                              "Benzene (industrial solvent, carcinogen)"),
    ("CC(=O)Oc1ccccc1C(=O)O",                "Aspirin"),
    ("CN1CCC[C@H]1c2cccnc2",                 "Nicotine"),
    ("CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C",  "Testosterone"),
]
for smi, name in examples:
    add_table_row(tbl, [smi, name])

doc.add_paragraph()
doc.add_paragraph(
    "SMILES strings for any known compound can be looked up on PubChem "
    "(pubchem.ncbi.nlm.nih.gov). The demo accepts one or more SMILES strings and "
    "converts each to a Morgan fingerprint before feeding it to the neural network."
)

# ── Section 3: Morgan Fingerprints ────────────────────────────────────────────
add_heading(doc, "3. From SMILES to Neural Network Input: Morgan Fingerprints", level=1)

doc.add_paragraph(
    "A neural network requires a fixed-length numeric vector as input. A SMILES string "
    "has variable length and encodes topology, not a feature vector. The demo therefore "
    "converts each molecule to a 2048-bit Morgan fingerprint (also called a circular "
    "fingerprint) using the RDKit chemistry library."
)
doc.add_paragraph(
    "A Morgan fingerprint works by examining the chemical neighbourhood of each atom "
    "out to a radius of 2 bonds, hashing each unique substructure pattern into one of "
    "2048 binary 'slots'. If a pattern exists in the molecule, its slot is set to 1; "
    "otherwise it remains 0. The result is a 2048-element binary vector that encodes "
    "the structural features of the molecule in a form the neural network can process."
)
doc.add_paragraph(
    "This representation is well-established in computational chemistry and is used "
    "in many published QSAR (Quantitative Structure-Activity Relationship) models."
)

# ── Section 4: The 12 Assays ──────────────────────────────────────────────────
add_heading(doc, "4. The 12 Biological Assays", level=1)

doc.add_paragraph(
    "The assays fall into two groups: Nuclear Receptor assays and Stress Response "
    "assays. Each measures whether a chemical activates or disrupts a specific "
    "biological pathway."
)

# 4a Nuclear Receptor
add_heading(doc, "4a. Nuclear Receptor (NR) Panel", level=2)

doc.add_paragraph(
    "Nuclear receptors are proteins inside cells that, when activated by a chemical "
    "signal, migrate to the cell nucleus and switch genes on or off. They are the "
    "master regulators of development, metabolism, and reproduction. A chemical that "
    "binds a nuclear receptor uninvited can hijack this signalling system — a "
    "mechanism called endocrine disruption."
)

tbl2 = doc.add_table(rows=1, cols=3)
tbl2.style = "Table Grid"
shade_row(tbl2.rows[0], "BDD7EE")
for i, hdr in enumerate(["Assay", "Mechanism", "Why It Matters"]):
    tbl2.rows[0].cells[i].text = hdr
    tbl2.rows[0].cells[i].paragraphs[0].runs[0].bold = True

nr_rows = [
    ("NR-AR",
     "Androgen Receptor (full-length) agonist",
     "Chemicals that activate the androgen receptor mimic testosterone. This can "
     "cause reproductive abnormalities, early puberty, reduced fertility, and "
     "developmental defects in foetuses. Relevant to plasticisers, pesticides, and "
     "personal care product ingredients."),
    ("NR-AR-LBD",
     "Androgen Receptor Ligand Binding Domain agonist",
     "A selectivity assay that tests only the binding pocket of the AR, rather than "
     "the full-length receptor. A chemical that activates NR-AR-LBD but not NR-AR "
     "may bind the receptor without triggering a full hormonal response. Used to "
     "distinguish direct AR agonists from compounds acting via other mechanisms."),
    ("NR-AhR",
     "Aryl Hydrocarbon Receptor agonist",
     "The AhR mediates the toxicity of dioxins, PCBs, and polycyclic aromatic "
     "hydrocarbons (PAHs, found in smoke and grilled food). Activation induces "
     "CYP1A1/1A2 enzymes, altering drug metabolism, and is linked to "
     "immunosuppression, liver damage, and cancer. A positive here is a serious flag."),
    ("NR-Aromatase",
     "Aromatase (CYP19A1) enzyme inhibitor",
     "Aromatase converts androgens (e.g. testosterone) into oestrogens. Inhibiting it "
     "collapses oestrogen levels, disrupting female reproduction, bone density, and "
     "cardiovascular health. Many fungicides and some pharmaceuticals are aromatase "
     "inhibitors. This is a key target in endocrine disruption screening."),
    ("NR-ER",
     "Oestrogen Receptor α (full-length) agonist",
     "Chemicals that activate ERα mimic oestrogen. This is one of the most studied "
     "endocrine disruption pathways, linked to breast cancer risk, reproductive "
     "disorders, and developmental effects. Bisphenol A (BPA) and many phytoestrogens "
     "are ERα agonists. A positive here triggers strict regulatory scrutiny."),
    ("NR-ER-LBD",
     "Oestrogen Receptor Ligand Binding Domain agonist",
     "Selectivity counterpart to NR-ER; tests binding to the ERα pocket alone. "
     "Helps distinguish whether an oestrogenic effect is mediated by direct receptor "
     "binding or by an upstream mechanism (e.g. increased endogenous oestrogen). "
     "Important for mechanistic classification of endocrine disruptors."),
    ("NR-PPAR-gamma",
     "Peroxisome Proliferator-Activated Receptor γ agonist",
     "PPARγ is the master regulator of fat cell differentiation and glucose metabolism. "
     "Its agonists are used therapeutically (thiazolidinedione diabetes drugs), but "
     "environmental chemicals that activate it — such as tributyltin in antifouling "
     "paints — can cause obesity and metabolic syndrome at developmental exposures. "
     "An important target for obesogen screening."),
]
for row_data in nr_rows:
    add_table_row(tbl2, row_data)

doc.add_paragraph()

# 4b Stress Response
add_heading(doc, "4b. Stress Response (SR) Panel", level=2)

doc.add_paragraph(
    "Stress response assays use cell lines engineered with reporter genes — genes that "
    "produce a measurable signal (e.g. luciferase light) when a specific cellular "
    "stress pathway is activated. Unlike the nuclear receptor assays, which detect "
    "receptor binding, these assays measure downstream cellular damage responses."
)

tbl3 = doc.add_table(rows=1, cols=3)
tbl3.style = "Table Grid"
shade_row(tbl3.rows[0], "BDD7EE")
for i, hdr in enumerate(["Assay", "Mechanism", "Why It Matters"]):
    tbl3.rows[0].cells[i].text = hdr
    tbl3.rows[0].cells[i].paragraphs[0].runs[0].bold = True

sr_rows = [
    ("SR-ARE",
     "Antioxidant Response Element (NRF2 pathway) activation",
     "The ARE/NRF2 pathway is the cell's primary defence against oxidative stress — "
     "damage caused by reactive oxygen species (free radicals). Chemicals that "
     "activate this pathway are electrophilic or generate ROS. While low activation "
     "may indicate the cell is coping, high activation signals cytotoxic oxidative "
     "damage. Relevant to industrial chemicals, quinones, and heavy metals."),
    ("SR-ATAD5",
     "ATAD5 genotoxicity reporter",
     "ATAD5 is upregulated in response to DNA damage and replication stress. A "
     "positive result strongly suggests the compound damages DNA directly "
     "(genotoxicity). This is one of the most serious flags in early toxicology — "
     "genotoxic compounds are candidate carcinogens and mutagens, and typically "
     "require extensive follow-up testing including Ames tests and comet assays."),
    ("SR-HSE",
     "Heat Shock Element (HSP70 pathway) activation",
     "Heat shock proteins are molecular chaperones that refold damaged or misfolded "
     "proteins. When a chemical causes protein misfolding — proteotoxic stress — the "
     "heat shock pathway is activated. This is a broad indicator of cellular protein "
     "damage, relevant to heavy metals, solvents, and compounds that interfere with "
     "protein synthesis or folding machinery."),
    ("SR-MMP",
     "Mitochondrial Membrane Potential disruption",
     "Mitochondria maintain an electrochemical gradient across their inner membrane "
     "to drive ATP synthesis. Chemicals that collapse this potential (MMP disruptors) "
     "shut down cellular energy production, triggering apoptosis. MMP disruption is "
     "the primary mechanism of mitochondrial toxicity and is a precursor to "
     "cytotoxicity. Particularly important for cardiac and hepatic toxicity screening."),
    ("SR-p53",
     "p53 tumour suppressor pathway activation",
     "p53 is the cell's primary guardian against DNA damage — it halts the cell cycle "
     "and initiates repair or apoptosis when DNA is damaged. A positive SR-p53 result "
     "indicates genotoxic or severe cytotoxic stress. Combined with SR-ATAD5, these "
     "two assays form the core genotoxicity screen in the Tox21 panel. Compounds "
     "positive on both are high-priority carcinogenicity candidates."),
]
for row_data in sr_rows:
    add_table_row(tbl3, row_data)

doc.add_paragraph()

# ── Section 5: The Demo Application ───────────────────────────────────────────
add_heading(doc, "5. The Demo Application", level=1)

doc.add_paragraph(
    "The demo is a web application that sits in front of the nnsd neural network "
    "server and provides a Tox21-specific interface. It has three main functions:"
)

add_heading(doc, "5a. Assay Status Panel", level=2)
doc.add_paragraph(
    "The main screen lists all 12 assays with their current training status, last "
    "recorded accuracy, and training date. An assay marked as 'trained' has a neural "
    "network model ready to make predictions. Untrained assays can be trained "
    "directly from the interface."
)

add_heading(doc, "5b. Training an Assay", level=2)
doc.add_paragraph(
    "Clicking Train on an assay triggers the following pipeline:"
)
steps = [
    ("1. Data preparation",
     "The application reads the raw Tox21 CSV file and extracts the label column for "
     "the selected assay. Any compound with a missing label is discarded."),
    ("2. SMILES conversion",
     "Each compound's SMILES string is converted to a 2048-bit Morgan fingerprint "
     "using RDKit. Invalid SMILES strings are discarded."),
    ("3. Class balancing",
     "Tox21 data is heavily imbalanced — typically 5–15% of compounds are positive "
     "(toxic) for any given assay. If balancing is enabled, the minority class is "
     "oversampled by repetition so the network sees equal numbers of toxic and "
     "non-toxic examples during training. This prevents the network from learning "
     "to always predict 'non-toxic'."),
    ("4. Training",
     "The prepared CSV is submitted to the nnsd neural network server. Training "
     "runs on the GPU (NVIDIA RTX 4060) using backpropagation with Adam optimisation. "
     "A typical run from a cold start converges in 5,000–10,000 epochs, taking "
     "around 5–10 minutes. The model is automatically saved on completion."),
]
tbl4 = doc.add_table(rows=1, cols=2)
tbl4.style = "Table Grid"
shade_row(tbl4.rows[0], "BDD7EE")
tbl4.rows[0].cells[0].text = "Step"
tbl4.rows[0].cells[1].text = "Description"
for run in tbl4.rows[0].cells[0].paragraphs[0].runs:
    run.bold = True
for run in tbl4.rows[0].cells[1].paragraphs[0].runs:
    run.bold = True
for step, desc in steps:
    add_table_row(tbl4, [step, desc], bold_first=True)

doc.add_paragraph()

add_heading(doc, "5c. Predicting Toxicity for a New Compound", level=2)
doc.add_paragraph(
    "To predict the toxicity profile of an untested chemical, paste its SMILES string "
    "into the prediction panel and select which assays to evaluate. The application:"
)
doc.add_paragraph(
    "1. Converts the SMILES to a 2048-bit Morgan fingerprint via RDKit.",
    style="List Number"
)
doc.add_paragraph(
    "2. Submits the fingerprint to each selected trained model in nnsd.",
    style="List Number"
)
doc.add_paragraph(
    "3. Returns a prediction table showing, for each assay, whether the compound "
    "is predicted toxic (class 1) or non-toxic (class 0), along with the model's "
    "confidence score.",
    style="List Number"
)
doc.add_paragraph(
    "The result is not a definitive toxicology assessment — it is a fast computational "
    "screen to prioritise which compounds warrant laboratory follow-up. A positive "
    "prediction should be interpreted as 'this compound shares structural features "
    "with known actives in this assay' rather than 'this compound is definitively toxic'."
)

# ── Section 6: Interpreting Results ───────────────────────────────────────────
add_heading(doc, "6. Interpreting Results and Limitations", level=1)

doc.add_paragraph(
    "The neural network was trained on in vitro (cell-based) assay data. This means:"
)
bullets = [
    "A positive prediction indicates structural similarity to compounds that triggered "
    "a cellular response in a lab assay — not necessarily that the compound causes "
    "harm in a living organism.",
    "In vivo toxicity depends on absorption, distribution, metabolism, and excretion "
    "(ADME) factors that are not captured by the fingerprint.",
    "The 97% balanced accuracy reported on the training dataset reflects performance "
    "on known compounds. Novel compounds with unusual structural features may fall "
    "outside the model's training distribution.",
    "Regulatory toxicology requires validated assay data. These predictions are "
    "appropriate for research prioritisation and hypothesis generation, not for "
    "regulatory submissions.",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

# ── Save ──────────────────────────────────────────────────────────────────────
out = "/home/bcosta/Projects/CLionProjects/tox21_demo/Tox21_Demo_Guide.docx"
doc.save(out)
print(f"Saved: {out}")
