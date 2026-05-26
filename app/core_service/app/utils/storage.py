import os
import zipfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple

SCORM_ROOT = Path("/mnt/scorm")

def save_upload_file(upload_file, destination: Path) -> None:
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()

def extract_scorm_package(zip_path: Path, extract_to: Path) -> Optional[str]:
    """
    Extracts a SCORM ZIP package and returns the relative path to the entry point
    by parsing imsmanifest.xml. Works for SCORM 1.2 and SCORM 2004 namespaces.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Path traversal protection: ensure no member escapes extract_to
            resolved_base = extract_to.resolve()
            for member in zip_ref.namelist():
                member_path = (extract_to / member).resolve()
                if not str(member_path).startswith(str(resolved_base)):
                    raise ValueError(f"Path traversal detected in ZIP: {member}")
            zip_ref.extractall(extract_to)

        manifest_path = extract_to / "imsmanifest.xml"
        if not manifest_path.exists():
            return None

        tree = ET.parse(manifest_path)
        root = tree.getroot()

        # Namespace-agnostic search: works for SCORM 1.2 (imsproject.org namespace),
        # SCORM 2004 (imsglobal.org namespace), and no-namespace manifests.
        for elem in root.iter():
            local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if local == 'resource':
                href = elem.get('href')
                if href:
                    return href

        return None
    except Exception as e:
        print(f"Error processing SCORM: {e}")
        return None

def prepare_storage_path(tenant_id: str, training_id: str, chapter_id: str) -> Path:
    path = SCORM_ROOT / tenant_id / training_id / chapter_id
    path.mkdir(parents=True, exist_ok=True)
    return path

def save_banner_image(upload_file, tenant_id: str, training_id: str, ext: str) -> str:
    """Save banner image to /mnt/images/banners/ and return the public URL path."""
    banner_dir = Path("/mnt/images/banners") / tenant_id
    banner_dir.mkdir(parents=True, exist_ok=True)
    dest = banner_dir / f"{training_id}{ext}"
    save_upload_file(upload_file, dest)
    return f"/storage/banners/{tenant_id}/{training_id}{ext}"


def save_pdf_file(upload_file, tenant_id: str, training_id: str, chapter_id: str) -> str:
    """Save a PDF chapter file to /mnt/images/pdfs/<tenant>/<training>/<chapter>.pdf
    and return its public URL. The file is served by the gateway under
    /storage/pdfs/ — see app/gateway/nginx.conf.
    """
    pdf_dir = Path("/mnt/images/pdfs") / tenant_id / training_id
    pdf_dir.mkdir(parents=True, exist_ok=True)
    dest = pdf_dir / f"{chapter_id}.pdf"
    save_upload_file(upload_file, dest)
    return f"/storage/pdfs/{tenant_id}/{training_id}/{chapter_id}.pdf"
