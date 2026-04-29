"""
Dual-mode PPTX utilities.

When /mnt/skills/public/pptx/scripts exists, delegates to platform scripts via
subprocess. Otherwise, provides pure-Python fallbacks
using only stdlib (zipfile, xml.etree, os, re, tempfile).
"""

import os, re, subprocess, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

PLATFORM_SCRIPTS = Path('/mnt/skills/public/pptx/scripts')
_HAS_PLATFORM = PLATFORM_SCRIPTS.exists()


def find_skill_root(anchor=None):
    """Locate the skill root directory regardless of script layout.

    Works whether scripts live in a ``scripts/`` subdirectory (local dev,
    workspace runtimes) or are flattened into the skill root (sandbox runtimes).

    Detection: walk up from *anchor* (default ``__file__`` of the caller)
    looking for ``styles/`` or ``assets/`` — the first directory that
    contains one of these is the skill root.  Falls back to cwd.
    """
    start = Path(anchor or __file__).resolve().parent
    for candidate in (start, start.parent, start.parent.parent, Path.cwd()):
        if (candidate / "styles").is_dir() or (candidate / "assets").is_dir():
            return candidate
    return Path.cwd()


def make_work_dir(prefix='bcg_'):
    """Create a cross-platform temporary working directory."""
    return Path(tempfile.mkdtemp(prefix=prefix))


def unpack(pptx_path, dest_dir):
    """Extract a .pptx (ZIP) to dest_dir."""
    if _HAS_PLATFORM:
        subprocess.run(
            ['python', str(PLATFORM_SCRIPTS / 'office' / 'unpack.py'),
             str(pptx_path), str(dest_dir)],
            capture_output=True, text=True
        )
    else:
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(str(pptx_path)) as zf:
            zf.extractall(str(dest_dir))


def pack(work_dir, output_path, original_path=None):
    """Re-zip a directory into a .pptx file."""
    if _HAS_PLATFORM:
        args = ['python', str(PLATFORM_SCRIPTS / 'office' / 'pack.py'),
                str(work_dir), str(output_path)]
        if original_path:
            args += ['--original', str(original_path)]
        subprocess.run(args, capture_output=True, text=True)
    else:
        # [Content_Types].xml must be first entry for maximum Office compatibility
        work = Path(work_dir)
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            ct = work / '[Content_Types].xml'
            if ct.exists():
                zf.write(str(ct), '[Content_Types].xml')
            for root, dirs, files in os.walk(str(work)):
                dirs.sort()
                for f in sorted(files):
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, str(work))
                    if arcname == '[Content_Types].xml':
                        continue  # already written first
                    zf.write(fp, arcname)


def clean(work_dir):
    """Validate/normalize XML files in the unpacked pptx."""
    if _HAS_PLATFORM:
        subprocess.run(
            ['python', str(PLATFORM_SCRIPTS / 'clean.py'), str(work_dir)],
            capture_output=True, text=True
        )
    else:
        # Lightweight: parse every .xml and .rels to verify well-formedness
        work = Path(work_dir)
        for xml_file in list(work.rglob('*.xml')) + list(work.rglob('*.rels')):
            try:
                ET.parse(str(xml_file))
            except ET.ParseError as e:
                print(f"XML warning: {xml_file.name}: {e}", file=sys.stderr)


def add_slide(work_dir, layout_file):
    """Create a new slide from a layout file.

    Returns a string matching the platform script output format:
        "Created slideN.xml ... r:id=\"rIdN\""

    The caller (bcg_template._add_slide_from_layout) parses this with:
        re.search(r'Created (slide\\d+\\.xml)', output)
        re.search(r'r:id="(rId\\d+)"', output)
    """
    if _HAS_PLATFORM:
        result = subprocess.run(
            ['python', str(PLATFORM_SCRIPTS / 'add_slide.py'),
             str(work_dir), layout_file],
            capture_output=True, text=True
        )
        return result.stdout
    else:
        return _add_slide_fallback(Path(work_dir), layout_file)


def _add_slide_fallback(work_dir, layout_file):
    """Pure-Python implementation of add_slide."""
    slides_dir = work_dir / 'ppt' / 'slides'
    rels_dir = slides_dir / '_rels'
    slides_dir.mkdir(parents=True, exist_ok=True)
    rels_dir.mkdir(parents=True, exist_ok=True)

    # 1. Determine next slide number
    existing = []
    for f in slides_dir.glob('slide*.xml'):
        m = re.search(r'slide(\d+)', f.name)
        if m:
            existing.append(int(m.group(1)))
    next_num = max(existing) + 1 if existing else 1
    slide_name = f'slide{next_num}.xml'

    # 2. Create minimal slide XML
    slide_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld></p:sld>'
    )
    (slides_dir / slide_name).write_text(slide_xml, 'utf-8')

    # 3. Create slide .rels pointing to the layout
    slide_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        f'Target="../slideLayouts/{layout_file}"/>'
        '</Relationships>'
    )
    (rels_dir / f'{slide_name}.rels').write_text(slide_rels, 'utf-8')

    # 4. Add relationship in presentation.xml.rels
    prels_path = work_dir / 'ppt' / '_rels' / 'presentation.xml.rels'
    prels = prels_path.read_text('utf-8')
    rids = [int(m) for m in re.findall(r'Id="rId(\d+)"', prels)]
    next_rid = max(rids) + 1 if rids else 1
    rid_str = f'rId{next_rid}'

    new_rel = (
        f'<Relationship Id="{rid_str}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/{slide_name}"/>'
    )
    prels = prels.replace('</Relationships>', f'{new_rel}</Relationships>')
    prels_path.write_text(prels, 'utf-8')

    # 5. Add Override in [Content_Types].xml
    ct_path = work_dir / '[Content_Types].xml'
    ct = ct_path.read_text('utf-8')
    override = (
        f'<Override PartName="/ppt/slides/{slide_name}" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
    )
    if f'/ppt/slides/{slide_name}' not in ct:
        ct = ct.replace('</Types>', f'{override}</Types>')
        ct_path.write_text(ct, 'utf-8')

    # 6. Return output in the same format as the platform script
    return f'Created {slide_name} r:id="{rid_str}"'


def export_slides_as_images(pptx_path, output_dir, dpi=120, fmt='png'):
    """Export every slide in *pptx_path* as an individual image file.

    Strategy (in order of preference):
      1. LibreOffice headless  -> PDF  -> pdftoppm  (per-page PNGs, best fidelity)
      2. LibreOffice headless  -> PNG  (single composite image, then split by aspect ratio)
      3. Raises RuntimeError if neither tool is available.

    Parameters
    ----------
    pptx_path : str | Path
        Source .pptx file.
    output_dir : str | Path
        Directory where slide images will be written.  Created if absent.
    dpi : int
        Resolution for rasterisation (default 120).
    fmt : str
        Output image format, 'png' or 'jpg' (default 'png').

    Returns
    -------
    list[Path]
        Sorted list of output image paths (slide-1.png, slide-2.png, …).

    Raises
    ------
    RuntimeError
        If no rendering backend is found.
    """
    pptx_path = Path(pptx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _cmd_exists(name):
        return subprocess.run(
            ['which', name], capture_output=True
        ).returncode == 0

    has_lo = _cmd_exists('libreoffice')
    has_pdftoppm = _cmd_exists('pdftoppm')

    # ── Strategy 1: LibreOffice → PDF → pdftoppm ────────────────────────────
    if has_lo and has_pdftoppm:
        pdf_path = output_dir / (pptx_path.stem + '.pdf')
        subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pdf',
             '--outdir', str(output_dir), str(pptx_path)],
            capture_output=True, text=True, timeout=120,
        )
        if not pdf_path.exists():
            raise RuntimeError(
                f'LibreOffice failed to produce PDF from {pptx_path}'
            )
        stem = str(output_dir / 'slide')
        subprocess.run(
            ['pdftoppm', '-r', str(dpi), f'-{fmt}', str(pdf_path), stem],
            capture_output=True, text=True, timeout=120,
        )
        slides = sorted(output_dir.glob(f'slide-*.{fmt}'))
        if slides:
            return slides
        # fall through to strategy 2 if pdftoppm produced nothing

    # ── Strategy 2: LibreOffice → single PNG, then tile-split ────────────────
    if has_lo:
        subprocess.run(
            ['libreoffice', '--headless', '--convert-to', fmt,
             '--outdir', str(output_dir), str(pptx_path)],
            capture_output=True, text=True, timeout=120,
        )
        composite = output_dir / f'{pptx_path.stem}.{fmt}'
        if not composite.exists():
            raise RuntimeError(
                f'LibreOffice failed to produce image from {pptx_path}'
            )
        # Try to split composite into per-slide tiles using Pillow
        try:
            from PIL import Image as _Image
            img = _Image.open(str(composite))
            iw, ih = img.size
            # Standard 16:9 slide aspect ratio
            slide_aspect = 16 / 9
            # Detect whether slides are stacked horizontally or vertically,
            # or whether the composite is already a single slide
            h_count = round((iw / ih) / slide_aspect)  # horizontal tiles
            v_count = round((ih / iw) * slide_aspect)  # vertical tiles
            if h_count > 1:
                tile_w = iw // h_count
                paths = []
                for i in range(h_count):
                    tile = img.crop((i * tile_w, 0, (i + 1) * tile_w, ih))
                    p = output_dir / f'slide-{i + 1}.{fmt}'
                    tile.save(str(p))
                    paths.append(p)
                composite.unlink(missing_ok=True)
                return sorted(paths)
            elif v_count > 1:
                tile_h = ih // v_count
                paths = []
                for i in range(v_count):
                    tile = img.crop((0, i * tile_h, iw, (i + 1) * tile_h))
                    p = output_dir / f'slide-{i + 1}.{fmt}'
                    tile.save(str(p))
                    paths.append(p)
                composite.unlink(missing_ok=True)
                return sorted(paths)
            else:
                # Single slide — just rename to slide-1
                dest = output_dir / f'slide-1.{fmt}'
                composite.rename(dest)
                return [dest]
        except ImportError:
            # Pillow not available; return composite as-is
            return [composite]

    raise RuntimeError(
        'No rendering backend found. '
        'Install LibreOffice (libreoffice) and pdftoppm (poppler-utils) '
        'to enable slide image export.'
    )
