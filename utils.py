import os



def get_real_file_list(directory="."):
    allowed = ('.py', '.txt', '.md', '.json', '.yaml')
    try:
        files = [f for f in os.listdir(directory)
                 if os.path.isfile(f) and f.endswith(allowed)]
        return sorted(files) if files else ["No Files"]
    except Exception:
        return ["Error"]


def get_file_list_recursive(directory=".", allowed=('.py', '.txt', '.md', '.json', '.yaml'),
                            exclude_dirs=('.git', '__pycache__', 'logs', 'uploads', 'assets', '.venv', 'venv')):
    try:
        results = []
        for root, dirs, files in os.walk(directory):
            # 제외할 디렉터리 필터링
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            for f in files:
                if f.endswith(allowed):
                    rel = os.path.relpath(os.path.join(root, f), directory)
                    # Windows 경로 구분자 -> '/' 로 통일
                    results.append(rel.replace("\\", "/"))
        results.sort()
        return results if results else ["No Files"]
    except Exception:
        return ["Error"]


def _insert_path_into_tree(tree, path_parts, full_path):
    node = tree
    for part in path_parts[:-1]:
        node = node.setdefault(part, {})
    node[path_parts[-1]] = full_path  # leaf 노드의 값은 실제 파일 경로(str)


def get_file_tree(directory=".", allowed=('.py', '.txt', '.md', '.json', '.yaml'),
                  exclude_dirs=('.git', '__pycache__', 'logs', 'uploads', 'assets', '.venv', 'venv')):
    files = get_file_list_recursive(directory, allowed=allowed, exclude_dirs=exclude_dirs)
    if not files or files in (["No Files"], ["Error"]):
        return {}
    tree = {}
    for rel_path in files:
        parts = rel_path.split("/")
        _insert_path_into_tree(tree, parts, rel_path)
    return tree


def load_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


def save_file(filename, content):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return "Saved"
    except Exception:
        return "Error"
