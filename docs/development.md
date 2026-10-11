# Foundry-v2 development

The implementation is starting with the locked runtime and shared substrate.
Current commands list role identities; service entrypoints reject startup until
their authenticated runtime is implemented. This package is not ready to evaluate targets.

Use CPython 3.12 on Linux for the production build. A separate Windows dependency
lock supports local editing/tests without changing Linux environment markers.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock -r requirements-build.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m foundry_v2.cli roles
python -m pytest tests/unit tests/contract tests/integration
```

On Windows activate `.venv\Scripts\Activate.ps1` and replace `requirements.lock`
with `requirements.windows.lock`. Tests never execute deliberately vulnerable source
fixtures. Live-cluster/model suites require explicit flags and authorized inputs.

```sh
docker build --platform linux/amd64 -f deploy/images/Dockerfile -t foundry-v2:development .
docker run --rm foundry-v2:development roles
```

The image base is pinned by official manifest digest; scanner downloads are verified
against committed upstream release checksums. The image's ID is recorded by CI.
`deploy/images/pin_inputs.py` explicitly refreshes these inputs and verifies downloaded
scanner archives; review the resulting changes before rebuilding. Production service
and worker entrypoint selection will use the same immutable image and distinct processes.

GitHub CI runs deterministic tests and a Linux image build. Live workflow dispatch uses
the organization's `foundry-authorized` self-hosted runner and protected environment;
no credentials or reachable cluster are assumed by ordinary CI.
