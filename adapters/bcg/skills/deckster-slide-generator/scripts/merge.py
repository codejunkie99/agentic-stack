"""
BCG Merge: Insert PptxGenJS-generated slides into a template scaffold deck.

Usage:
    python merge.py scaffold.pptx batch.pptx output.pptx --positions 3,4,5

Replaces slides at positions 3,4,5 in scaffold with slides 1,2,3 from batch.
"""

import os, re, shutil, sys
from pathlib import Path
from pptx_utils import unpack as _unpack, pack as _pack, clean as _clean, make_work_dir


def unpack(pptx_path, dest_dir):
    _unpack(pptx_path, dest_dir)


def pack(unpacked_dir, output_path, original_path):
    _clean(unpacked_dir)
    _pack(unpacked_dir, output_path, original_path)

def get_next_rid(content):
    rids = [int(m) for m in re.findall(r'Id="rId(\d+)"', content)]
    return max(rids) + 1 if rids else 1

def get_next_slide_id(content):
    ids = [int(m) for m in re.findall(r'<p:sldId[^>]*id="(\d+)"', content)]
    return max(ids) + 1 if ids else 256

def merge(scaffold_dir, batch_dir, positions):
    scaffold = Path(scaffold_dir)
    batch = Path(batch_dir)
    scaffold_slides = scaffold / 'ppt' / 'slides'
    batch_slides = batch / 'ppt' / 'slides'

    batch_slide_files = sorted(batch_slides.glob('slide*.xml'), key=lambda f: int(re.search(r'slide(\d+)', f.name).group(1)))
    if not batch_slide_files:
        print("No batch slides found", file=sys.stderr)
        return

    # Copy media from batch to scaffold
    batch_media = batch / 'ppt' / 'media'
    scaffold_media = scaffold / 'ppt' / 'media'
    scaffold_media.mkdir(exist_ok=True)
    media_map = {}
    existing = [int(re.search(r'image(\d+)', m.name).group(1)) for m in scaffold_media.glob('image*') if re.search(r'image(\d+)', m.name)]
    next_num = max(existing) + 1 if existing else 1
    if batch_media.exists():
        for mf in sorted(batch_media.iterdir()):
            if mf.is_file():
                new_name = f'image{next_num}{mf.suffix}'
                shutil.copy2(mf, scaffold_media / new_name)
                media_map[mf.name] = new_name
                next_num += 1

    # Copy charts if they exist
    batch_charts = batch / 'ppt' / 'charts'
    if batch_charts.exists():
        scaffold_charts = scaffold / 'ppt' / 'charts'
        scaffold_charts.mkdir(exist_ok=True)
        for cf in batch_charts.iterdir():
            if cf.is_file():
                shutil.copy2(cf, scaffold_charts / cf.name)
        batch_chart_rels = batch_charts / '_rels'
        if batch_chart_rels.exists():
            (scaffold_charts / '_rels').mkdir(exist_ok=True)
            for rf in batch_chart_rels.iterdir():
                shutil.copy2(rf, scaffold_charts / '_rels' / rf.name)

    # Load scaffold metadata files
    pres_path = scaffold / 'ppt' / 'presentation.xml'
    prels_path = scaffold / 'ppt' / '_rels' / 'presentation.xml.rels'
    ct_path = scaffold / '[Content_Types].xml'
    pres = pres_path.read_text('utf-8')
    prels = prels_path.read_text('utf-8')
    ct = ct_path.read_text('utf-8')

    for batch_idx, batch_slide in enumerate(batch_slide_files):
        if batch_idx >= len(positions):
            break
        target_pos = positions[batch_idx]
        target_name = f'slide{target_pos}.xml'

        # Remove old slide
        old = scaffold_slides / target_name
        if old.exists(): old.unlink()
        old_rels = scaffold_slides / '_rels' / f'{target_name}.rels'
        if old_rels.exists(): old_rels.unlink()

        # Copy and fix slide XML
        content = batch_slide.read_text('utf-8')
        for old_m, new_m in media_map.items():
            content = content.replace(old_m, new_m)
        (scaffold_slides / target_name).write_text(content, 'utf-8')

        # Copy and fix slide rels
        batch_rels = batch_slides / '_rels' / f'{batch_slide.name}.rels'
        dest_rels = scaffold_slides / '_rels' / f'{target_name}.rels'
        (scaffold_slides / '_rels').mkdir(exist_ok=True)
        if batch_rels.exists():
            rc = batch_rels.read_text('utf-8')
            for old_m, new_m in media_map.items():
                rc = rc.replace(old_m, new_m)
            # Remove notesSlide references (PptxGenJS adds them but scaffold lacks the files)
            rc = re.sub(r'\s*<Relationship[^>]*notesSlide[^>]*/>', '', rc)
            # Ensure slideLayout points to Title Only (slideLayout2) for BCG theme inheritance
            if 'slideLayout' not in rc:
                rc = rc.replace('</Relationships>', '  <Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>\n</Relationships>')
            else:
                rc = re.sub(r'Target="../slideLayouts/slideLayout\d+\.xml"', 'Target="../slideLayouts/slideLayout2.xml"', rc)
            dest_rels.write_text(rc, 'utf-8')
        else:
            dest_rels.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout2.xml"/>\n</Relationships>', 'utf-8')

        # Update content types
        override = f'<Override PartName="/ppt/slides/{target_name}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        if f'/ppt/slides/{target_name}' not in ct:
            ct = ct.replace('</Types>', f'  {override}\n</Types>')

        # Update presentation rels
        if f'slides/{target_name}' not in prels:
            rid = f'rId{get_next_rid(prels)}'
            prels = prels.replace('</Relationships>', f'  <Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/{target_name}"/>\n</Relationships>')
            sid = get_next_slide_id(pres)
            pres = pres.replace('</p:sldIdLst>', f'    <p:sldId id="{sid}" r:id="{rid}"/>\n  </p:sldIdLst>')

        print(f"  Merged {batch_slide.name} -> {target_name}")

    pres_path.write_text(pres, 'utf-8')
    prels_path.write_text(prels, 'utf-8')
    ct_path.write_text(ct, 'utf-8')

if __name__ == '__main__':
    if len(sys.argv) < 6 or sys.argv[4] != '--positions':
        print("Usage: python merge.py scaffold.pptx batch.pptx output.pptx --positions 3,4,5")
        sys.exit(1)
    scaffold_pptx, batch_pptx, output_pptx = sys.argv[1], sys.argv[2], sys.argv[3]
    positions = [int(p) for p in sys.argv[5].split(',')]
    scaffold_dir = str(make_work_dir('merge_scaffold_'))
    batch_dir = str(make_work_dir('merge_batch_'))
    for d in [scaffold_dir, batch_dir]:
        if os.path.exists(d): shutil.rmtree(d)
    print(f"Unpacking scaffold...")
    unpack(scaffold_pptx, scaffold_dir)
    print(f"Unpacking batch...")
    unpack(batch_pptx, batch_dir)
    print(f"Merging...")
    merge(scaffold_dir, batch_dir, positions)
    print(f"Packing...")
    pack(scaffold_dir, output_pptx, scaffold_pptx)
    shutil.rmtree(scaffold_dir, ignore_errors=True)
    shutil.rmtree(batch_dir, ignore_errors=True)
    if os.path.exists(output_pptx):
        print(f"Done: {output_pptx} ({os.path.getsize(output_pptx):,} bytes)")

# Alias for import compatibility
merge_slides = merge
