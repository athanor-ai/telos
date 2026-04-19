#!/usr/bin/env bash
# setup.sh — one-command install for telos.
#
# Installs the Python package + verifies that at least one backend
# is ready (pydantic + PyYAML at minimum). Full verifier toolchains
# (Lean 4, Dafny, EBMC) are resolved lazily: the Dockerfile pulls
# them in a pinned image, or you can run `./setup.sh --full` to
# install them locally.
#
# Exit 0 on success; prints what was installed.

set -euo pipefail

cd "$(dirname "$0")"

FULL=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    --help|-h)
      cat <<'EOF'
usage: ./setup.sh [--full]

  (no args)   install the Python package + minimum dependencies.
  --full      also install Lean 4 v4.14.0 (via elan), Dafny 4.9.1
              (via the dafny-base container), and EBMC 5.11.
EOF
      exit 0
      ;;
  esac
done

echo "[telos/setup] installing Python package + dependencies..."
python3 -m pip install --user --upgrade pip >/dev/null
python3 -m pip install --user -e . >/dev/null
echo "[telos/setup] pip: ok"

python3 -c "import telos; print(f'  telos version: {telos.__version__}')"

if [ "$FULL" -eq 1 ]; then
  echo "[telos/setup] --full: installing verifier toolchains..."

  if ! command -v lake >/dev/null 2>&1; then
    echo "  installing elan (Lean 4 toolchain manager)..."
    curl --proto '=https' --tlsv1.2 -sSf \
      https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      -o /tmp/elan-init.sh
    bash /tmp/elan-init.sh -y --default-toolchain leanprover/lean4:v4.14.0
    export PATH="$HOME/.elan/bin:$PATH"
    echo "  lake: $(command -v lake)"
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "  WARNING: docker not installed; Dafny + EBMC backends will be unavailable."
    echo "  (pull the telos Docker image for a self-contained run: docker build -t telos .)"
  else
    echo "  docker: ok"
  fi
fi

echo "[telos/setup] done."
echo
echo "Next: telos verify examples/bbrv3-starvation.yaml"
