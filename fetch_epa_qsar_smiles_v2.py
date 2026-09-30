#!/usr/bin/env python3
import argparse, json, os, sys, time
from pathlib import Path
import pandas as pd
import requests

BASE = "https://comptox.epa.gov/ctx-api"
PATH = "/chemical/detail/search/by-dtxsid/"
FIELDS = ["dtxsid","dtxcid","casrn","preferredName","smiles","qsarReadySmiles",
          "msReadySmiles","inchikey","inchiString"]

def dtxsid_column(df):
    for c in ("dtxsid","DTXSID","dsstox_substance_id","DSSTOX_SUBSTANCE_ID"):
        if c in df.columns:
            return c
    raise ValueError("No DTXSID column found.")

def batches(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def request_batch(session, url, key, ids, timeout, retries):
    headers={"x-api-key":key,"Content-Type":"application/json","Accept":"application/json"}
    for attempt in range(retries+1):
        try:
            r=session.post(url, params={"projection":"chemicalstructure"},
                           headers=headers, json=ids, timeout=timeout)
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:800]}")
            data=r.json()
            if isinstance(data,list): return data
            if isinstance(data,dict):
                for k in ("data","results","content"):
                    if isinstance(data.get(k),list): return data[k]
                if "dtxsid" in data: return [data]
            raise RuntimeError("Unexpected response: "+json.dumps(data)[:800])
        except (requests.RequestException,RuntimeError,ValueError) as e:
            if attempt==retries: raise
            wait=min(2**attempt,30)
            print(f"  retry after error: {e} ({wait}s)",file=sys.stderr)
            time.sleep(wait)

def main():
    p=argparse.ArgumentParser(description="Fetch EPA QSAR-ready SMILES by DTXSID.")
    p.add_argument("input_csv")
    p.add_argument("-o","--output",default="liver_target_with_smiles.csv")
    p.add_argument("--missing-output",default="liver_target_missing_structures.csv")
    p.add_argument("--smiles-output",default="liver_smiles.txt",help="One QSAR-ready SMILES per line, no header")
    p.add_argument("--batch-size",type=int,default=50)
    p.add_argument("--timeout",type=int,default=60)
    p.add_argument("--retries",type=int,default=4)
    p.add_argument("--base-url",default=BASE)
    a=p.parse_args()

    key=os.environ.get("EPA_CTX_API_KEY")
    if not key:
        sys.exit("ERROR: set EPA_CTX_API_KEY first.")
    df=pd.read_csv(a.input_csv)
    idcol=dtxsid_column(df)
    norm=df[idcol].astype("string").str.strip()
    valid=norm.notna() & norm.str.match(r"^DTXSID\d+$",na=False)
    ids=list(dict.fromkeys(norm[valid].tolist()))
    if not ids: sys.exit("ERROR: no valid DTXSIDs.")

    url=a.base_url.rstrip("/")+PATH
    session=requests.Session()
    records=[]; failed=[]
    bs=list(batches(ids,a.batch_size))
    print(f"{len(df)} rows; {len(ids)} unique valid DTXSIDs; {len(bs)} batches")
    for i,b in enumerate(bs,1):
        print(f"Batch {i}/{len(bs)} ({len(b)} IDs)")
        try:
            x=request_batch(session,url,key,b,a.timeout,a.retries)
            records.extend(x); print(f"  returned {len(x)}")
        except Exception as e:
            print(f"  FAILED: {e}",file=sys.stderr); failed.extend(b)

    s=pd.DataFrame(records)
    for c in FIELDS:
        if c not in s.columns: s[c]=pd.NA
    s=s[FIELDS].copy()
    if len(s):
        s["dtxsid"]=s["dtxsid"].astype("string").str.strip()
        s["_q"]=s["qsarReadySmiles"].fillna("").astype(str).str.strip().ne("")
        s=s.sort_values(["dtxsid","_q"],ascending=[True,False]).drop_duplicates("dtxsid").drop(columns="_q")

    work=df.copy()
    work["_join"]=norm

    # Rename the EPA response key before merging so an input column named
    # "dtxsid" does not cause pandas to create dtxsid_x / dtxsid_y.
    s_merge=s.rename(columns={"dtxsid":"_epa_dtxsid"})
    out=work.merge(
        s_merge,
        how="left",
        left_on="_join",
        right_on="_epa_dtxsid",
        validate="m:1"
    ).drop(columns="_join")
    out.to_csv(a.output,index=False)

    # Evaluation input: exactly one non-empty QSAR-ready SMILES per line,
    # with no header, IDs, quotes, or commas.
    smiles = (
        out["qsarReadySmiles"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    smiles = smiles[smiles.ne("")]
    Path(a.smiles_output).write_text(
        "".join(smile + "\n" for smile in smiles),
        encoding="utf-8"
    )

    returned=set(s["dtxsid"].dropna().astype(str))
    missing=[]
    bad=df[~valid].copy()
    if len(bad):
        bad["failure_reason"]="invalid_or_missing_dtxsid"; missing.append(bad)
    unmatched=set(ids)-returned
    if unmatched:
        x=df[norm.isin(unmatched)].copy(); x["failure_reason"]="no_record_returned_by_api"; missing.append(x)
    if failed:
        x=df[norm.isin(set(failed))].copy(); x["failure_reason"]="api_batch_failed"; missing.append(x)
    noqs=out[out["_epa_dtxsid"].notna() & out["qsarReadySmiles"].fillna("").astype(str).str.strip().eq("")].copy()
    if len(noqs):
        noqs["failure_reason"]="qsarReadySmiles_missing"; missing.append(noqs)
    miss=pd.concat(missing,ignore_index=True,sort=False) if missing else pd.DataFrame(columns=list(df.columns)+["failure_reason"])
    miss.to_csv(a.missing_output,index=False)

    q=out["qsarReadySmiles"].fillna("").astype(str).str.strip().ne("").sum()
    print(f"\nReturned IDs: {len(returned)}/{len(ids)}")
    print(f"Rows with QSAR-ready SMILES: {q}/{len(out)}")
    print(f"Output: {a.output}")
    print(f"SMILES evaluation file: {a.smiles_output} ({len(smiles)} lines)")
    print(f"Exceptions: {a.missing_output}")
    if unmatched or failed or len(noqs): sys.exit(2)

if __name__=="__main__":
    main()
