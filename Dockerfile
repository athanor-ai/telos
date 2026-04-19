# telos — self-contained verification environment.
#
# Pulls the public athanor-ai dafny-base image (Dafny 4.9.1 + Z3 4.12.1)
# and layers Lean 4 via elan, EBMC 5.11, Python + telos. Running
# `docker run telos telos verify examples/bbrv3-starvation.yaml`
# reproduces the paper's full 5-backend cross-check.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/opt/elan/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash git curl wget ca-certificates \
      python3 python3-pip \
      build-essential \
      texlive-publishers texlive-latex-extra texlive-plain-generic \
      texlive-fonts-recommended lmodern \
    && rm -rf /var/lib/apt/lists/*

# Lean 4 via elan, pinned to v4.14.0.
RUN curl --proto '=https' --tlsv1.2 -sSf \
      https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      -o /tmp/elan-init.sh \
    && ELAN_HOME=/opt/elan bash /tmp/elan-init.sh -y \
         --default-toolchain leanprover/lean4:v4.14.0 \
    && rm /tmp/elan-init.sh

WORKDIR /app

COPY pyproject.toml ./
COPY telos telos/
COPY examples examples/
COPY docs docs/
COPY tests tests/
COPY setup.sh ./

RUN pip install --no-cache-dir -e ".[dev]"

CMD ["telos", "--help"]
