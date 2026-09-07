from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


class UnsafeArchive(ValueError):
    pass


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def extract_zip_safe(archive: Path, dest: Path, *, max_files: int, max_bytes: int) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > max_files:
            raise UnsafeArchive("too many files")
        for info in infos:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                raise UnsafeArchive(f"illegal path {name}")
            if info.is_dir():
                continue
            if stat_is_symlink(info):
                raise UnsafeArchive(f"symlink {name}")
            total += info.file_size
            if total > max_bytes:
                raise UnsafeArchive("archive exceeds size limit")
            target = dest / name
            if not _is_within(dest, target):
                raise UnsafeArchive(f"path escape {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                out.write(src.read())


def stat_is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def extract_tar_safe(archive: Path, dest: Path, *, max_files: int, max_bytes: int) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    with tarfile.open(archive, "r:*") as tf:
        members = tf.getmembers()
        if len(members) > max_files:
            raise UnsafeArchive("too many files")
        for member in members:
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                raise UnsafeArchive(f"illegal path {name}")
            if member.issym() or member.islnk():
                raise UnsafeArchive(f"link {name}")
            if member.isfile():
                total += member.size
                if total > max_bytes:
                    raise UnsafeArchive("archive exceeds size limit")
            target = dest / name
            if not _is_within(dest, target):
                raise UnsafeArchive(f"path escape {name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                with extracted, target.open("wb") as out:
                    out.write(extracted.read())
            else:
                raise UnsafeArchive(f"unsupported member {name}")
