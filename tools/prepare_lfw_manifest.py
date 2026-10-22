#!/usr/bin/env python3
"""Create anonymized local benchmark splits from previously obtained LFW JPEGs.

Does not download images or expose identity names in logs or output labels.
The source dataset and generated manifest must remain in private storage.
"""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import random


def select_people(dataset_root, known=12, unknown_per_split=12, seed=20261022):
    root = Path(dataset_root).resolve()
    if not root.is_dir() or known < 2 or unknown_per_split < 1:
        raise ValueError('invalid dataset directory or group sizes')
    groups = []
    for folder in root.iterdir():
        if not folder.is_dir() or folder.is_symlink():
            continue
        images = sorted(p.resolve() for p in folder.glob('*.jpg') if p.is_file() and not p.is_symlink())
        if images:
            groups.append((folder.name, images))
    # Directory enumeration order is filesystem-dependent: sort before shuffling.
    groups.sort(key=lambda row: row[0])
    rng = random.Random(seed)
    rng.shuffle(groups)
    qualified = [(identity,images) for identity,images in groups if len(images) >= 7]
    if len(qualified) < known:
        raise ValueError('insufficient multi-image identities for calibration and holdout')
    known_groups = qualified[:known]
    known_names = {name for name,_ in known_groups}
    unknown_groups = [(identity,images) for identity,images in groups if identity not in known_names]
    if len(unknown_groups) < unknown_per_split * 2:
        raise ValueError('insufficient independent unknown identities')
    rows = []
    for i,(identity,images) in enumerate(known_groups):
        picked = images[:]
        rng.shuffle(picked)
        for role, subset in [('enroll',picked[:3]), ('dev_known',picked[3:5]),
                             ('holdout_known',picked[5:7])]:
            for image in subset:
                rows.append((image,f'known_{i:04d}',role,'unspecified'))
    for phase,subset in [('dev_unknown',unknown_groups[:unknown_per_split]),
                         ('holdout_unknown',unknown_groups[unknown_per_split:2*unknown_per_split])]:
        for i,(_,images) in enumerate(subset):
            rows.append((images[0],f'{phase}_{i:04d}',phase,'unspecified'))
    return rows


def write_manifest(rows, path):
    path = Path(path).expanduser().absolute()
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with os.fdopen(os.open(path,os.O_CREAT|os.O_WRONLY|os.O_EXCL|os.O_NOFOLLOW,0o600),'w',newline='') as fp:
        writer=csv.writer(fp)
        writer.writerow(('path','identity','role','pose'))
        for image,identity,role,pose in rows:
            writer.writerow((os.path.relpath(image,path.parent), identity,role,pose))


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--images-dir',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--known',type=int,default=12)
    ap.add_argument('--unknown-per-split',type=int,default=12)
    args=ap.parse_args(argv)
    try:
        rows=select_people(args.images_dir,args.known,args.unknown_per_split)
        write_manifest(rows,args.out)
    except (OSError,ValueError) as exc:
        ap.exit(2,'LFW manifest preparation unavailable: '+type(exc).__name__+'\n')
    # Do not print source celebrity names or image paths.
    print('Created local anonymized research manifest; verify rights and sample independence.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())