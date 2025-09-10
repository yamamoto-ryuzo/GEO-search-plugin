import os
import zipfile
import shutil


def find_metadata():
    """Search for metadata.txt in the current directory or one-level subdirectories.
    Returns (metadata_path, source_dir). source_dir is the directory that contains metadata.txt.
    """
    root_meta = os.path.join('.', 'metadata.txt')
    if os.path.isfile(root_meta):
        return os.path.abspath(root_meta), os.path.abspath('.')
    for name in os.listdir('.'):
        candidate = os.path.join('.', name, 'metadata.txt')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate), os.path.abspath(name)
    return None, None


def read_metadata_version(metadata_path):
    with open(metadata_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('version='):
                return line.strip().split('=')[1]
    return None


def bump_version(version):
    parts = version.split('.')
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
    else:
        parts.append('1')
    return '.'.join(parts)


def update_metadata_version(metadata_path, new_version):
    with open(metadata_path, encoding='utf-8') as f:
        lines = f.readlines()
    with open(metadata_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith('version='):
                f.write(f'version={new_version}\n')
            else:
                f.write(line)


def get_plugin_name(metadata_path):
    with open(metadata_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('name='):
                return line.strip().split('=')[1]
    return 'plugin'


def remove_old_zip(plugin_name):
    for fname in os.listdir('.'):
        if fname.startswith(plugin_name) and fname.endswith('.zip'):
            os.remove(fname)


def main():
    metadata_path, src_dir = find_metadata()
    if not metadata_path:
        print('metadata.txt not found in current directory or one-level subdirectories')
        return

    version = read_metadata_version(metadata_path)
    if not version:
        print(f'version not found in {metadata_path}')
        return

    new_version = bump_version(version)
    update_metadata_version(metadata_path, new_version)

    plugin_name = get_plugin_name(metadata_path)
    # sanitize plugin name for filesystem usage in zip
    plugin_base = plugin_name.replace(' ', '-')
    zip_name = f'{plugin_base}_{new_version}.zip'

    remove_old_zip(plugin_base)

    temp_dir = f'{plugin_base}_pkg'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.mkdir(temp_dir)

    # 必要最小限のファイル・フォルダ（src_dir 内またはルートのいずれかから探す）
    includes = [
        '__init__.py', 'metadata.txt', 'plugin.py', 'constants.py', 'searchfeature.py', 'searchdialog.py',
        'resultdialog.py', 'autodialog.py', 'utils.py', 'resources.py', 'resources.qrc',
        'setting.json', 'README.md', 'view.sql', 'icon', 'ui', 'widget', 'i18n', 'jaconv', 'LICENSE'
    ]

    for item in includes:
        # prefer path under src_dir, but fall back to root
        src_path = os.path.join(src_dir, item) if src_dir and src_dir != os.path.abspath('.') else os.path.join('.', item)
        if not os.path.exists(src_path):
            # try fallback to root if we were looking in subdir
            alt = os.path.join('.', item)
            if os.path.exists(alt):
                src_path = alt

        if os.path.isdir(src_path):
            shutil.copytree(src_path, os.path.join(temp_dir, item))
        elif os.path.isfile(src_path):
            dest = os.path.join(temp_dir, item)
            # ensure destination directory exists
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src_path, dest)
        else:
            print(f'Warning: {src_path} not found, skipping')

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                path = os.path.join(root, file)
                arcname = os.path.relpath(path, temp_dir)
                zipf.write(path, os.path.join(plugin_base, arcname))

    shutil.rmtree(temp_dir)
    print(f'Created {zip_name}')


if __name__ == '__main__':
    main()
