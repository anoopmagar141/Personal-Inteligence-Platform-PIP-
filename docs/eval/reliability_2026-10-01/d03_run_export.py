import getpass, runpy, sys, os
answers = iter(["alice-password-1", "backup-password-9", "backup-password-9"])
getpass.getpass = lambda prompt="": next(answers)
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
sys.path.insert(0, os.path.dirname(script))
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    print("SystemExit:", e.code)
