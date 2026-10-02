import os, sys, pathlib
root = sys.argv[1]
sys.path.insert(0, root)
os.environ["PIP_DATA_DIR"] = os.path.join(root, "data")
from backend.core import profiles, db_key
from backend.memory import profile_store
p = profiles.register("Alice")
d = os.path.join(root, "data", p.data_dir)
salt = db_key.create_salt(pathlib.Path(d, "salt.bin"))
key = db_key.derive_key("alice-password-1", salt)
c = profile_store.get_connection(os.path.join(d, "pip.db"), key)
profile_store.initialize_schema(c); c.close()
print("registered", p.slug, p.data_dir)
