"""Compile static fixtures and compare baseline, exact PR, and integrated scanners."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path('/workspace')
records = []
fixtures = {
    'quoted-variable': 'variable (True : Prop)',
    'quoted-namespace': 'namespace Fake\ndef True',
}
for name, content in fixtures.items():
    source = ('def «marker\n' + content + '» : Nat := 0\n'
              'theorem mcaPrizeResidual : True := trivial\n'
              '#check mcaPrizeResidual\n#print axioms mcaPrizeResidual\n')
    with tempfile.TemporaryDirectory(dir='/tmp') as directory:
        path = Path(directory) / 'Probe.lean'
        path.write_text(source, encoding='utf-8')
        lean = subprocess.run(['/toolchain/bin/lean', str(path)],
                              capture_output=True, text=True, timeout=30)
        assert lean.returncode == 0, lean.stdout + lean.stderr
        assert 'mcaPrizeResidual : True' in lean.stdout
        assert "'mcaPrizeResidual' does not depend on any axioms" in lean.stdout
        scans = []
        for label, scanner, expected in (
            ('main-d167049', root/'verification-inputs/main-forbidden.py', 1),
            ('pr228-c77cafb', root/'verification-inputs/pr228-forbidden.py', 0),
            ('integrated-fix', root/'scripts/forbidden_tokens.py', 1),
        ):
            result = subprocess.run([sys.executable, '-I', str(scanner), str(path)],
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == expected, (label, result.stdout, result.stderr)
            if expected:
                assert 'forbidden vacuous placebo' in result.stderr
            scans.append({'label': label, 'exit': result.returncode,
                          'expected_exit': expected, 'stdout': result.stdout,
                          'stderr': result.stderr})
        records.append({'name': name, 'source': source, 'lean_exit': lean.returncode,
                        'lean_output': lean.stdout + lean.stderr, 'scanners': scans})
print(json.dumps(records, indent=2, ensure_ascii=False))
