FROM python:3.12.3-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg
WORKDIR /opt/project

RUN useradd --create-home --uid 10001 researcher
COPY requirements-lock.txt pyproject.toml README.md ./
COPY src ./src
COPY p1_extension ./p1_extension
RUN python -m pip install --no-cache-dir -r requirements-lock.txt && \
    python -m pip install --no-cache-dir . && \
    python -m pip check

COPY analysis_plan ./analysis_plan
COPY locks ./locks
COPY manifests ./manifests
COPY tables ./tables
COPY scripts ./scripts
COPY tests ./tests
COPY v6_revision ./v6_revision
COPY data_manifest ./data_manifest
COPY release_config ./release_config
COPY CITATION.cff NOTICE THIRD_PARTY_NOTICES ./

RUN chown -R researcher:researcher /opt/project
USER researcher
CMD ["python", "scripts/verify_release.py"]

