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
                # Replace mock string literals starting with src.core, src.governance, etc.
                new_content = re.sub(r"([\"'])src\.core\.", r"\1drake.core.", new_content)
                new_content = re.sub(r"([\"'])src\.governance\.", r"\1drake.governance.", new_content)
                new_content = re.sub(r"([\"'])src\.proxy\.", r"\1drake.proxy.", new_content)
                new_content = re.sub(r"([\"'])src\.drake\.", r"\1drake.", new_content)
                new_content = re.sub(r"([\"'])src\.ai_clustering\.", r"\1drake.ai_clustering.", new_content)
                new_content = re.sub(r"([\"'])src\.cli\.", r"\1drake.cli.", new_content)
                # Clean up double drake imports introduced by previous replacements
                new_content = new_content.replace("drake.drake", "drake")

                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated imports in {file_path}")

if __name__ == "__main__":
    refactor_imports("src")
    refactor_imports("tests")
    refactor_imports("scripts")
