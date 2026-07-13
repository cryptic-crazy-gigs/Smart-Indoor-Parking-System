python - <<'PY'
import os
print("CWD:", os.getcwd())
print("Files:", os.listdir())
print("NPY files:", [f for f in os.listdir() if f.lower().endswith('.npy')])
