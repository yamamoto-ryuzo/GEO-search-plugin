import os
import re
import zipfile
import shutil

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
    metadata_path = 'metadata.txt'
    version = read_metadata_version(metadata_path)
    if not version:
        print('version not found in metadata.txt')
        return
    new_version = bump_version(version)
    update_metadata_version(metadata_path, new_version)
    plugin_name = get_plugin_name(metadata_path)
    zip_name = f'{plugin_name}_{new_version}.zip'
    remove_old_zip(plugin_name)
    plugin_dir = f'{plugin_name}'
    if os.path.exists(plugin_dir):
        shutil.rmtree(plugin_dir)
    os.mkdir(plugin_dir)
    # 必要最小限のファイル・フォルダ
    includes = [
        '__init__.py', 'metadata.txt', 'plugin.py', 'constants.py', 'searchfeature.py', 'searchdialog.py',
        'resultdialog.py', 'autodialog.py', 'utils.py', 'resources.py', 'resources.qrc',
        'setting.json', 'README.md', 'view.sql', 'icon', 'ui', 'widget', 'i18n', 'jaconv'
    ]
    for item in includes:
        if os.path.isdir(item):
            shutil.copytree(item, os.path.join(plugin_dir, item))
        elif os.path.isfile(item):
            shutil.copy2(item, os.path.join(plugin_dir, item))
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(plugin_dir):
            for file in files:
                path = os.path.join(root, file)
                arcname = os.path.relpath(path, plugin_dir)
                zipf.write(path, os.path.join(plugin_name, arcname))
    shutil.rmtree(plugin_dir)
    print(f'Created {zip_name}')

if __name__ == '__main__':
    main()
