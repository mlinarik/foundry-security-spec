FROM python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /build
COPY requirements.lock requirements-build.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock -r requirements-build.lock
COPY deploy/images/scanners.json deploy/images/install_scanners.py ./
RUN python install_scanners.py && osv-scanner --version && gitleaks version
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation .
RUN mkdir -p /scratch /artifacts && chown 10001:10001 /scratch /artifacts
USER 10001:10001
WORKDIR /scratch
ENTRYPOINT ["python", "-m", "foundry_v2.cli"]
CMD ["roles"]
