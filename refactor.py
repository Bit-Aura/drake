import os
import re
from pathlib import Path

def refactor_imports(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Replace "from src." or "from src import" with "from drake"
                new_content = re.sub(r"from\s+src\b", r"from drake", content)
                # Replace "import src." with "import drake."
                new_content = re.sub(r"import\s+src\b(?!\.)", r"import drake", new_content)
                # Ensure we also match import src.something
                new_content = re.sub(r"import\s+src\.", r"import drake.", new_content)

                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated imports in {file_path}")

if __name__ == "__main__":
    refactor_imports("src")
    refactor_imports("tests")
    refactor_imports("scripts")
