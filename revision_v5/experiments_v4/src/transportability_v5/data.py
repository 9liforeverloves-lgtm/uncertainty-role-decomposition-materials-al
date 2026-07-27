from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def load_materials_csv(path):
    df=pd.read_csv(path)
    aliases={"id":"material_id","composition":"formula","target_value":"target"}
    df=df.rename(columns={k:v for k,v in aliases.items() if k in df.columns})
    required={"material_id","formula","target"}
    if not required.issubset(df.columns): raise ValueError(f"missing columns: {sorted(required-set(df.columns))}")
    clean=df[list(required)].dropna().drop_duplicates("material_id").reset_index(drop=True)
    return clean


def featurize_formulas(formulas):
    try:
        from material_al.features import _parse_formula, _element_features
        rows=[_element_features(_parse_formula(x)) for x in formulas]
        return pd.DataFrame(rows).fillna(0).to_numpy(float)
    except Exception:
        from pymatgen.core import Composition
        elements=sorted({str(e) for f in formulas for e in Composition(str(f)).elements})
        rows=[]
        for f in formulas:
            comp=Composition(str(f)); total=comp.num_atoms; rows.append([comp.get_atomic_fraction(e) for e in elements]+[total,len(comp.elements)])
        return np.asarray(rows,float)


def synthetic_materials(n=180,seed=7):
    rng=np.random.default_rng(seed); systems=[("Li","Fe","O"),("Si","O"),("Al","Mg"),("Na","Cl"),("C","O"),("Ti","O")]
    rows=[]
    for i in range(n):
        elems=systems[i%len(systems)]; counts=rng.integers(1,5,size=len(elems)); formula="".join(e+(str(c) if c>1 else "") for e,c in zip(elems,counts))
        x=np.array([len(elems),counts.sum(),counts.max(),i%11],float); y=.4*x[0]+.06*x[1]+.03*x[2]+np.sin(x[3])+rng.normal(0,.05)
        rows.append({"material_id":f"syn_{i:04d}","formula":formula,"target":y})
    df=pd.DataFrame(rows); X=np.column_stack([df.formula.str.len(),df.formula.str.count("[A-Z]"),np.arange(n)%11,np.arange(n)%7]).astype(float)
    return df,X
