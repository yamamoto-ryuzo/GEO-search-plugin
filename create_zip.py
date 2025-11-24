import argparse
import fnmatch
import os
import zipfile
import shutil
from typing import Iterable


DEFAULT_EXCLUDES = [
    '__pycache__', '*.pyc', '*.pyo', '*.pyd', '.git', '.gitignore', '.pytest_cache', '.mypy_cache',
    '*.egg-info', 'dist', 'build', '.venv', 'venv', '.vscode', '.idea', 'tests', 'node_modules',
    '*.log', '*.sqlite', '*.db', '.DS_Store'
]


def read_gitignore_files(src_dir: str):
    """Read .gitignore from the source directory and repository root.
    Return list of patterns (simple, trimmed) to add to excludes.
    """
    patterns = []
    candidates = [os.path.join(src_dir, '.gitignore'), os.path.join('.', '.gitignore')]
    seen = set()
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        pat = line
                        # normalize leading slash (we'll treat patterns as relative to src_dir)
                        if pat.startswith('/'):
                            pat = pat.lstrip('/')
                        # directory pattern ending with '/'
                        if pat.endswith('/'):
                            pat = pat.rstrip('/')
                            if pat and pat not in seen:
                                patterns.append(pat)
                                seen.add(pat)
                            sub = pat + '/*'
                            if sub not in seen:
                                patterns.append(sub)
                                seen.add(sub)
                        else:
                            if pat not in seen:
                                patterns.append(pat)
                                seen.add(pat)
            except Exception:
                # don't fail packaging if gitignore can't be read
                pass
    return patterns


def find_metadata(src_hint: str = None):
    """Search for metadata.txt. If src_hint is provided and contains metadata.txt use it.
    Returns absolute path to metadata and the folder containing it.
    """
    if src_hint:
        candidate = os.path.join(src_hint, 'metadata.txt')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate), os.path.abspath(src_hint)

    root_meta = os.path.join('.', 'metadata.txt')
    if os.path.isfile(root_meta):
        return os.path.abspath(root_meta), os.path.abspath('.')
    for name in os.listdir('.'):
        candidate = os.path.join('.', name, 'metadata.txt')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate), os.path.abspath(name)
    return None, None


def read_metadata_value(metadata_path: str, key: str):
    with open(metadata_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith(f'{key}='):
                return line.strip().split('=', 1)[1]
    return None


def bump_version(version: str) -> str:
    parts = version.split('.')
    if len(parts) == 3 and parts[2].isdigit():
        parts[2] = str(int(parts[2]) + 1)
    else:
        parts.append('1')
    return '.'.join(parts)


def update_metadata_version(metadata_path: str, new_version: str):
    with open(metadata_path, encoding='utf-8') as f:
        lines = f.readlines()
    with open(metadata_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith('version='):
                f.write(f'version={new_version}\n')
            else:
                f.write(line)


def remove_old_zip(plugin_base: str, out_dir: str = '.'):
    for fname in os.listdir(out_dir):
        if fname.startswith(plugin_base) and fname.endswith('.zip'):
            os.remove(os.path.join(out_dir, fname))


def should_exclude(relpath: str, patterns: Iterable[str]) -> bool:
    """Return True if relpath matches any glob pattern in patterns."""
    for pat in patterns:
        # match both filename and path-like globs
        if fnmatch.fnmatch(relpath, pat) or fnmatch.fnmatch(os.path.basename(relpath), pat):
            return True
    return False


def create_zip_from_folder(src_dir: str, zip_path: str, plugin_base: str, excludes: Iterable[str]):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(src_dir):
            # compute relative path from src_dir
            rel_root = os.path.relpath(root, src_dir)
            if rel_root == '.':
                rel_root = ''

            # filter dirs in-place to avoid walking excluded directories
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_root, d), excludes) and d != '__pycache__']

            for file in files:
                relpath = os.path.join(rel_root, file) if rel_root else file
                if should_exclude(relpath, excludes) or file.endswith('.pyc'):
                    continue
                abs_path = os.path.join(root, file)
                arcname = os.path.join(plugin_base, relpath).replace('\\', '/')
                zipf.write(abs_path, arcname)


def parse_args():
    p = argparse.ArgumentParser(description='Create ZIP for QGIS plugin (geo_search)')
    p.add_argument('--src', default='geo_search', help='Source folder to package (default: geo_search)')
    p.add_argument('--out', default=None, help='Output zip path (default: <plugin>_<version>.zip in current dir)')
    p.add_argument('-e', '--exclude', action='append', default=[], help='Glob pattern to exclude (repeatable)')
    p.add_argument('--no-bump', action='store_true', help="Don't bump metadata version")
    p.add_argument('--dry-run', action='store_true', help='Show what would be included without creating zip')
    return p.parse_args()


def main():
    args = parse_args()

    metadata_path, detected_src = find_metadata(args.src if args.src else None)

    # prefer explicit src if it exists, otherwise use detected location
    if os.path.isdir(args.src):
        src_dir = os.path.abspath(args.src)
    elif detected_src:
        src_dir = detected_src
    else:
        print(f"Source folder '{args.src}' not found and metadata not detected.")
        return

    if not metadata_path:
        print('metadata.txt not found; packaging will still proceed but version/name are unknown')

    version = None
    plugin_name = os.path.basename(src_dir)
    if metadata_path:
        version = read_metadata_value(metadata_path, 'version')
        name = read_metadata_value(metadata_path, 'name')
        if name:
            plugin_name = name

    if version and not args.no_bump:
        new_version = bump_version(version)
        update_metadata_version(metadata_path, new_version)
        version = new_version

    plugin_base = plugin_name.replace(' ', '-')

    # build zip name
    if args.out:
        zip_name = args.out
    else:
        ver = version if version else 'dev'
        zip_name = f'{plugin_base}_{ver}.zip'

    # assemble exclude list
    excludes = list(DEFAULT_EXCLUDES)
    # add patterns from .gitignore (src folder and repo root)
    try:
        gitignore_patterns = read_gitignore_files(src_dir)
    except Exception:
        gitignore_patterns = []
    excludes.extend(gitignore_patterns)
    # user provided excludes override or extend
    if args.exclude:
        excludes.extend(args.exclude)

    # dry run: just list files that would be added
    if args.dry_run:
        print('Dry run: files that would be included:')
        for root, dirs, files in os.walk(src_dir):
            rel_root = os.path.relpath(root, src_dir)
            if rel_root == '.':
                rel_root = ''
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_root, d), excludes) and d != '__pycache__']
            for file in files:
                relpath = os.path.join(rel_root, file) if rel_root else file
                if should_exclude(relpath, excludes) or file.endswith('.pyc'):
                    continue
                print(relpath)
        return

    remove_old_zip(plugin_base)

    # create output dir if nested path provided
    out_dir = os.path.dirname(os.path.abspath(zip_name)) or '.'
    os.makedirs(out_dir, exist_ok=True)

    create_zip_from_folder(src_dir, zip_name, plugin_base, excludes)

    print(f'Created {zip_name}')


if __name__ == '__main__':
    main()
