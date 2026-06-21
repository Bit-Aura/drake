import glob

def find_sql_injection():
    for f in glob.glob('src/**/*.py', recursive=True):
        with open(f, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for i, line in enumerate(lines):
                if ('execute(' in line or 'executemany(' in line) and ('f"' in line or "f'" in line or '.format(' in line or ' % ' in line):
                    print(f'{f}:{i+1}: {line.strip()}')

find_sql_injection()
