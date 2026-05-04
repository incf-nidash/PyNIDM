#!/usr/bin/env bash
#
# PyNIDM QueryAI Demo Script
# ===========================
# Demonstrates the AI-assisted SPARQL query tool for NIDM files.
# The tool translates natural-language questions into SPARQL queries,
# resolves DataElement URIs from the data, and executes locally via rdflib.
#
# The script automatically downloads the required NIDM and CDE files from
# public GitHub repositories into a local cache directory.
#
# Prerequisites:
#   - pip install pynidm
#   - Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable
#     (or create ~/.pynidm/config.json)
#   - curl (for downloading files)
#
# Usage:
#   chmod +x queryai_demo.sh
#   ./queryai_demo.sh              # run all queries
#   ./queryai_demo.sh 1            # run only query 1
#   ./queryai_demo.sh 1 3          # run queries 1 and 3
#
# NOTE: Requires bash (not sh).  Use:  bash queryai_demo.sh
#       or:  chmod +x queryai_demo.sh && ./queryai_demo.sh
#
# Data Sources:
#   - NIDM file (KKI site, ABIDE dataset):
#       https://github.com/ReproNim/simple2_NIDM_examples
#   - FreeSurfer CDE:
#       https://github.com/ReproNim/segstats_jsonld
#   - FSL CDE:
#       https://github.com/ReproNim/fsl_seg_to_nidm
#   - ANTs CDE:
#       https://github.com/ReproNim/ants_seg_to_nidm

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Local cache directory for downloaded files (override with env var)
CACHE_DIR="${QUERYAI_CACHE_DIR:-${HOME}/.pynidm/demo_data}"

# GitHub raw URLs for each data file
NIDM_URL="https://raw.githubusercontent.com/ReproNim/simple2_NIDM_examples/master/datasets.datalad.org/abide/RawDataBIDS/KKI/nidm.ttl"
FS_CDE_URL="https://raw.githubusercontent.com/ReproNim/segstats_jsonld/master/segstats_jsonld/mapping_data/fs_cde.ttl"
FSL_CDE_URL="https://raw.githubusercontent.com/ReproNim/fsl_seg_to_nidm/master/fsl_seg_to_nidm/mapping_data/fsl_cde.ttl"
ANTS_CDE_URL="https://raw.githubusercontent.com/ReproNim/ants_seg_to_nidm/master/ants_seg_to_nidm/mapping_data/ants_cde.ttl"

# Local file paths (inside cache)
NIDM_FILE="${CACHE_DIR}/nidm.ttl"
FS_CDE="${CACHE_DIR}/fs_cde.ttl"
FSL_CDE="${CACHE_DIR}/fsl_cde.ttl"
ANTS_CDE="${CACHE_DIR}/ants_cde.ttl"

# Combined file list for queries that need CDE definitions
ALL_FILES="${NIDM_FILE},${FS_CDE},${FSL_CDE},${ANTS_CDE}"

# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

download_if_missing() {
    local url="$1"
    local dest="$2"
    local name
    name="$(basename "$dest")"

    if [[ -f "$dest" ]]; then
        echo "  [cached] $name"
        return 0
    fi

    echo "  [downloading] $name ..."
    if curl -fsSL --retry 3 -o "$dest" "$url"; then
        echo "  [ok] $name ($(du -h "$dest" | cut -f1))"
    else
        echo "  [FAILED] Could not download $name from:"
        echo "           $url"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

divider() {
    echo ""
    echo "=================================================================="
    echo "  QUERY $1: $2"
    echo "=================================================================="
    echo ""
}

should_run() {
    # Usage: should_run <query_number>
    # If the user passed no filter arguments (ARGS is empty), run everything.
    # Otherwise only run if the query number appears in ARGS.
    local query_num="$1"
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        return 0
    fi
    for arg in "${ARGS[@]}"; do
        [[ "$arg" == "$query_num" ]] && return 0
    done
    return 1
}

# Capture CLI args for selective execution
ARGS=("$@")

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------

if ! command -v pynidm &>/dev/null; then
    echo "ERROR: 'pynidm' command not found."
    echo "Install with:  pip install pynidm"
    exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]] && [[ -z "${OPENAI_API_KEY:-}" ]]; then
    if [[ ! -f "${HOME}/.pynidm/config.json" ]]; then
        echo "WARNING: No AI API key found."
        echo "Set ANTHROPIC_API_KEY or OPENAI_API_KEY, or create ~/.pynidm/config.json"
        echo ""
    fi
fi

# ---------------------------------------------------------------------------
# Download data files
# ---------------------------------------------------------------------------

echo "Checking data files in ${CACHE_DIR} ..."
mkdir -p "$CACHE_DIR"

fail=0
download_if_missing "$NIDM_URL"     "$NIDM_FILE" || fail=1
download_if_missing "$FS_CDE_URL"   "$FS_CDE"    || fail=1
download_if_missing "$FSL_CDE_URL"  "$FSL_CDE"   || fail=1
download_if_missing "$ANTS_CDE_URL" "$ANTS_CDE"  || fail=1

if [[ $fail -eq 1 ]]; then
    echo ""
    echo "Some files could not be downloaded. Queries that need them will fail."
    echo ""
fi

echo ""

# ---------------------------------------------------------------------------
# Query 1: Count subjects
# ---------------------------------------------------------------------------
if should_run 1; then
    divider 1 "How many subjects are there?"

    pynidm queryai \
        -nl "$NIDM_FILE" \
        -q "How many subjects are there?" \
        -s
fi

# ---------------------------------------------------------------------------
# Query 2: List all subjects
# ---------------------------------------------------------------------------
if should_run 2; then
    divider 2 "List all subjects"

    pynidm queryai \
        -nl "$NIDM_FILE" \
        -q "List all subjects" \
        -s
fi

# ---------------------------------------------------------------------------
# Query 3: Average age
# ---------------------------------------------------------------------------
if should_run 3; then
    divider 3 "What is the average age of all subjects?"

    pynidm queryai \
        -nl "$NIDM_FILE" \
        -q "What is the average age of all subjects?" \
        -s
fi

# ---------------------------------------------------------------------------
# Query 4: Complex multi-variable query with brain volumes
#
# NOTE: This query is interactive — if multiple DataElements match
# "left hippocampus volume" (e.g. from FreeSurfer, FSL, and ANTs),
# you will be prompted to select which one(s).  You can enter:
#   - A single number (e.g. 2)
#   - Multiple comma-separated numbers (e.g. 2,3)
#   - 'a' for all matches
#   - 0 to skip
# ---------------------------------------------------------------------------
if should_run 4; then
    divider 4 "Subject demographics + left hippocampus volume + software tool"

    pynidm queryai \
        -nl "$ALL_FILES" \
        -q "For each subject, get their ID, age, sex, diagnosis, and the left hippocampus volume from FreeSurfer, FSL, and/or ANTS with a column indicating the software tool that produced it" \
        -s
fi

echo ""
echo "Done.  All queries executed with -s (show SPARQL) flag."
echo "Add -o output.tsv to any query to save results to a file."
echo ""
echo "To re-download data files, delete the cache:"
echo "  rm -rf ${CACHE_DIR}"
