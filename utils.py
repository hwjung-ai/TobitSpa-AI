import os


def get_real_file_list(directory="."):
    allowed = ('.py', '.txt', '.md', '.json', '.yaml')
    try:
        files = [f for f in os.listdir(directory)
                 if os.path.isfile(f) and f.endswith(allowed)]
        return sorted(files) if files else ["No Files"]
    except Exception:
        return ["Error"]


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