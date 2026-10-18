"""Run the public reproduction workflow with the current Python interpreter."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch and verify the original Shenzhen subset from Figshare')
    args = parser.parse_args()
    for folder in ['results/scenarios', 'paper/figures', 'paper/qa']:
        (ROOT/folder).mkdir(parents=True, exist_ok=True)
    steps = []
    if args.download:
        steps.append(['fetch_cptond_shenzhen.py'])
    steps += [
        ['test_geometry.py'], ['prepare_network.py'], ['validate_official.py'],
        ['coverage_analysis.py', '--grid', '--variants'], ['summarize_results.py'],
        ['make_figures.py'], ['check_revision_evidence.py'],
        ['make_method_schematic.py'], ['analyze_application_cases.py'],
        ['make_application_figure.py'],
    ]
    for step in steps:
        print('Running: ' + ' '.join(step), flush=True)
        subprocess.run([sys.executable, str(ROOT/'scripts'/step[0]), *step[1:]], cwd=ROOT, check=True)
    print('Reproduction completed. Derived files in results/ and paper/figures/ were regenerated.')

if __name__ == '__main__':
    main()
