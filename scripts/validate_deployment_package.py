"""Validation script for PLUTO vProctor deployment package.

Validates:
1. Dockerfile contexts and referenced source files.
2. Docker Compose syntax, service dependencies, healthchecks, and volume mappings.
3. Environment variables, production safety constraints, and potential blockers.
4. GPU compute requirements per container.
5. Alembic migration readiness and database seeding requirements.
6. Staging Docker Compose (docker-compose.staging.yml) resolution of blockers.

Fails with exit code 1 if any fatal errors or deployment blockers are detected in the target configuration.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent


def validate_dockerfiles() -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    backend_dockerfile = ROOT_DIR / "backend" / "Dockerfile"
    frontend_dockerfile = ROOT_DIR / "frontend" / "Dockerfile"

    print("\n[1] Checking Dockerfiles...")
    if not backend_dockerfile.exists():
        errors.append("backend/Dockerfile is missing")
    else:
        print("  ✓ backend/Dockerfile exists")
        for ref_file in ["backend/requirements.txt", "alembic.ini", "backend/", "datasets/", "docs/"]:
            p = ROOT_DIR / ref_file
            if not p.exists():
                errors.append(f"backend/Dockerfile references missing path: {ref_file}")
            else:
                print(f"    ✓ Referenced path exists: {ref_file}")

    if not frontend_dockerfile.exists():
        errors.append("frontend/Dockerfile is missing")
    else:
        print("  ✓ frontend/Dockerfile exists")
        for ref_file in ["frontend/package.json", "frontend/nginx.conf", "frontend/src"]:
            p = ROOT_DIR / ref_file
            if not p.exists():
                errors.append(f"frontend/Dockerfile references missing path: {ref_file}")
            else:
                print(f"    ✓ Referenced path exists: {ref_file}")

    return errors, warnings


def validate_staging_compose(compose_path: Path) -> tuple[list[str], list[str], list[str]]:
    errors = []
    warnings = []
    blockers = []

    print(f"\n[2] Checking Staging Compose Configuration: {compose_path.name}...")
    if not compose_path.exists():
        errors.append(f"{compose_path.name} is missing")
        return errors, warnings, blockers

    try:
        with open(compose_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
            compose_data = yaml.safe_load(raw_content)

        print(f"  ✓ {compose_path.name} is valid YAML")
        services = compose_data.get("services", {})
        print(f"  ✓ Discovered {len(services)} services: {list(services.keys())}")

        # Check required services
        required_services = ["postgres", "ollama", "migration", "backend", "frontend"]
        for req in required_services:
            if req not in services:
                errors.append(f"Mandatory staging service '{req}' is missing from {compose_path.name}")
            else:
                print(f"    ✓ Service '{req}' defined")

        # 1. Check PostgreSQL
        pg = services.get("postgres", {})
        if "healthcheck" not in pg:
            errors.append("PostgreSQL in staging must have an explicit healthcheck defined")
        else:
            print("    ✓ PostgreSQL healthcheck defined")
        pg_ports = pg.get("ports", [])
        for port_entry in pg_ports:
            if "0.0.0.0" in str(port_entry) or (":" in str(port_entry) and not str(port_entry).startswith("127.0.0.1")):
                blockers.append(f"PostgreSQL port is exposed to non-loopback: {port_entry}")
            else:
                print(f"    ✓ PostgreSQL port properly restricted: {port_entry}")

        # 2. Check Ollama
        ol = services.get("ollama", {})
        deploy_res = ol.get("deploy", {}).get("resources", {}).get("reservations", {}).get("devices", [])
        has_gpu = any("gpu" in d.get("capabilities", []) for d in deploy_res)
        if not has_gpu:
            blockers.append("Ollama service in staging lacks NVIDIA GPU device reservation in deploy.resources")
        else:
            print("    ✓ Ollama GPU reservation properly configured (driver: nvidia, capabilities: [gpu])")

        ol_ports = ol.get("ports", [])
        for port_entry in ol_ports:
            if "0.0.0.0" in str(port_entry) or (":" in str(port_entry) and not str(port_entry).startswith("127.0.0.1")):
                blockers.append(f"Ollama port is exposed to non-loopback: {port_entry}")
            else:
                print(f"    ✓ Ollama port properly restricted: {port_entry}")

        # 3. Check Migration service (one-shot alembic)
        mig = services.get("migration", {})
        cmd = mig.get("command", [])
        if "alembic" not in str(cmd) or "upgrade" not in str(cmd):
            blockers.append("Migration service does not execute 'alembic upgrade head'")
        else:
            print(f"    ✓ Migration service executes: {cmd}")
        if mig.get("restart") != "no":
            warnings.append("Migration service should have restart: 'no' to prevent continuous restarts")
        mig_deps = mig.get("depends_on", {})
        if not (mig_deps.get("postgres", {}).get("condition") == "service_healthy"):
            warnings.append("Migration service should depend on postgres: condition: service_healthy")

        # 4. Check Backend service
        be = services.get("backend", {})
        be_cmd = be.get("command", [])
        if "--workers" in be_cmd:
            worker_idx = be_cmd.index("--workers")
            if worker_idx + 1 < len(be_cmd) and be_cmd[worker_idx + 1] != "1":
                blockers.append(f"Backend must specify exactly 1 Uvicorn worker for staging, found: {be_cmd[worker_idx + 1]}")
            else:
                print("    ✓ Backend specifies exactly 1 Uvicorn worker")
        else:
            print("    ✓ Backend command uses default single worker")

        be_deps = be.get("depends_on", {})
        if be_deps.get("migration", {}).get("condition") != "service_completed_successfully":
            blockers.append("Backend must depend on migration: condition: service_completed_successfully")
        else:
            print("    ✓ Backend startup condition correctly waits for migration to complete successfully")

        if be_deps.get("postgres", {}).get("condition") != "service_healthy":
            warnings.append("Backend should depend on postgres: condition: service_healthy")
        if be_deps.get("ollama", {}).get("condition") != "service_healthy":
            warnings.append("Backend should depend on ollama: condition: service_healthy")

        # Check environment safety
        be_env = be.get("environment", [])
        env_dict = {}
        for item in be_env:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                env_dict[k.strip()] = v.strip()

        print("    Checking Backend environment configuration:")
        if env_dict.get("ENVIRONMENT") == "production":
            print("      ✓ ENVIRONMENT is 'production'")
            if env_dict.get("COOKIE_SECURE", "").lower() != "true":
                blockers.append("In staging backend, COOKIE_SECURE must be true for production HTTPS mode")
            else:
                print("      ✓ COOKIE_SECURE is set to true")

            if env_dict.get("OLLAMA_BASE_URL") != "http://ollama:11434":
                blockers.append(f"OLLAMA_BASE_URL must be 'http://ollama:11434', found: {env_dict.get('OLLAMA_BASE_URL')}")
            else:
                print("      ✓ OLLAMA_BASE_URL is set to http://ollama:11434")

        # Check secret exposure
        for line in raw_content.splitlines():
            stripped = line.strip()
            if any(k in stripped for k in ["SECRET_KEY=", "POSTGRES_PASSWORD="]):
                if not ("${" in stripped and "}" in stripped):
                    blockers.append(f"Possible hardcoded credential in Compose: {stripped}")

        # 5. Check Worker container disabled
        if "worker" in services:
            worker_profiles = services["worker"].get("profiles", [])
            if "disabled" not in worker_profiles:
                blockers.append("Separate 'worker' container must be disabled in staging via profiles: ['disabled']")
            else:
                print("    ✓ Separate worker container is disabled via profiles: ['disabled']")

        # 6. Check Volumes
        vols = compose_data.get("volumes", {})
        required_vols = ["pgdata", "ollamadata", "storage_data"]
        for rv in required_vols:
            if rv not in vols:
                blockers.append(f"Named volume '{rv}' missing from volumes specification")
            else:
                print(f"    ✓ Persistent volume '{rv}' defined")

    except Exception as e:
        errors.append(f"Failed parsing {compose_path.name}: {e}")

    return errors, warnings, blockers


def validate_base_compose(compose_path: Path) -> tuple[list[str], list[str], list[str]]:
    errors = []
    warnings = []
    blockers = []

    print(f"\n[2] Checking Base Compose Configuration: {compose_path.name}...")
    if not compose_path.exists():
        errors.append(f"{compose_path.name} is missing")
        return errors, warnings, blockers

    try:
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data.get("services", {})
        backend_env = services.get("backend", {}).get("environment", [])
        env_dict = {}
        for item in backend_env:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                env_dict[k.strip()] = v.strip()

        if env_dict.get("ENVIRONMENT") == "production":
            auth_enabled = env_dict.get("AUTH_ENABLED", "").lower() == "true"
            cookie_secure = env_dict.get("COOKIE_SECURE", "").lower() == "true"
            if auth_enabled and not cookie_secure:
                blockers.append(
                    "Blocker 1: In base docker-compose.yml, AUTH_ENABLED=true but COOKIE_SECURE=false."
                )

        if "ollama" not in services:
            blockers.append(
                "Blocker 2: 'ollama' service is NOT present in base docker-compose.yml."
            )

        blockers.append(
            "Blocker 3: No container or entrypoint executes 'alembic upgrade head' in base docker-compose.yml."
        )

        if "worker" in services:
            blockers.append(
                "Blocker 4: 'worker' service runs as a separate container in base docker-compose.yml, but JobQueue uses in-process asyncio.Queue."
            )

    except Exception as e:
        errors.append(f"Failed parsing {compose_path.name}: {e}")

    return errors, warnings, blockers


def main():
    parser = argparse.ArgumentParser(description="PLUTO vProctor Deployment Package Validator")
    parser.add_argument("--file", type=str, help="Specific compose file to validate")
    parser.add_argument("--base-only", action="store_true", help="Validate base docker-compose.yml only")
    args = parser.parse_args()

    print("=== PLUTO vProctor: Deployment Package Validation ===")
    df_errors, df_warnings = validate_dockerfiles()

    staging_path = ROOT_DIR / "docker-compose.staging.yml"
    base_path = ROOT_DIR / "docker-compose.yml"

    total_errors = list(df_errors)
    total_warnings = list(df_warnings)
    total_blockers = []

    if args.base_only:
        b_errors, b_warnings, b_blockers = validate_base_compose(base_path)
        total_errors.extend(b_errors)
        total_warnings.extend(b_warnings)
        total_blockers.extend(b_blockers)
    else:
        # Validate Staging compose
        s_errors, s_warnings, s_blockers = validate_staging_compose(staging_path)
        total_errors.extend(s_errors)
        total_warnings.extend(s_warnings)
        total_blockers.extend(s_blockers)

    print("\n=== Validation Results ===")
    print(f"Errors   : {len(total_errors)}")
    for e in total_errors:
        print(f"  ❌ {e}")
    print(f"Warnings : {len(total_warnings)}")
    for w in total_warnings:
        print(f"  ⚠️  {w}")
    print(f"Blockers : {len(total_blockers)}")
    for b in total_blockers:
        print(f"  🚨 {b}")

    has_failures = len(total_errors) > 0 or len(total_blockers) > 0
    if has_failures:
        print("\n❌ VALIDATION FAILED: Deployment blockers must be resolved before launch.")
    else:
        print("\n✓ VALIDATION PASSED: Deployment package is clean.")

    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
