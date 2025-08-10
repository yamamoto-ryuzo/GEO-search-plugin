
import os
import zipfile

def should_exclude(file_path, exclude_patterns):
    for pattern in exclude_patterns:
        if pattern in file_path:
            return True
    return False

def make_zip(zip_name="GEO_search_2.20.15_py.zip", target_dir=None):
    if target_dir is None:
        target_dir = os.path.dirname(__file__)
    exclude_patterns = [
        ".git", "__pycache__", ".DS_Store", ".zip", ".pyc", "create_zip_py.py"
    ]
    with zipfile.ZipFile(os.path.join(target_dir, zip_name), 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(target_dir):
            # 除外ディレクトリ
            dirs[:] = [d for d in dirs if not should_exclude(d, exclude_patterns)]
            for file in files:
                if should_exclude(file, exclude_patterns):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, target_dir)
                zipf.write(file_path, arcname)
    print(f"Created {zip_name}")

if __name__ == "__main__":
    make_zip()
