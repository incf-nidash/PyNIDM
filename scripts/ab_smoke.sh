#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ab_smoke.sh -- A/B smoke test: run the same `pynidm query` read-only commands
# in the linkml env and the legacy (master) env over real NIDM data, and flag
# whether the outputs match after normalization.
#
# Scope: the *read-only* query modes, where BOTH envs read the SAME file and so
# should produce identical results (same UUIDs, same values -- no new UUIDs are
# minted on read).  A normalized MATCH is therefore the expected outcome; a DIFF
# is a real signal worth inspecting.
#
# NOT covered here (need the dedicated harnesses, because they mint new UUIDs or
# emit version-sensitive numeric formatting -- a raw diff is meaningless):
#   * merge / concat / convert  -> scripts/graph_transform_parity.py
#   * linear-regression         -> scripts/linreg_parity.py
#   * queryai                   -> LLM-backed, needs an API key (manual)
#
# Usage:
#   bash scripts/ab_smoke.sh
# Override any path by exporting it first, e.g.:
#   LINKML_BIN=... LEGACY_BIN=... NYU=... ON=... bash scripts/ab_smoke.sh
# ---------------------------------------------------------------------------
set -u

# --- environment binaries --------------------------------------------------
LINKML_BIN="${LINKML_BIN:-/Users/dkeator/opt/anaconda3/envs/pynidm_linkml/bin/pynidm}"
LEGACY_BIN="${LEGACY_BIN:-/Users/dkeator/opt/anaconda3/envs/pynidm_legacy/bin/pynidm}"

# --- real data files -------------------------------------------------------
ABIDE=/Users/dkeator/Documents/Coding/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS
OPENNEURO=/Users/dkeator/Documents/Coding/simple2_NIDM_examples/datasets.datalad.org/openneuro/ds002411
NYU="${NYU:-$ABIDE/NYU/nidm.ttl}"          # demographics + assessment instruments
CMU="${CMU:-$ABIDE/CMU_a/nidm.ttl}"        # second demographic site (for -gf / multi-file)
ON="${ON:-$OPENNEURO/nidm.ttl}"            # FreeSurfer derivatives -> brain volumes

OUT="${OUT:-/tmp/pynidm_ab_smoke}"
rm -rf "$OUT"; mkdir -p "$OUT"

# --- noise filter + normalizer ---------------------------------------------
# strip startup noise (etelemetry / dependency / deprecation warnings), drop the
# leading pandas row-index column, and sort so row-ordering differences are not
# treated as content differences.
_norm() {
  grep -vE "newer version|RequestsDependencyWarning|warnings.warn|UserWarning|DeprecationWarning|setParseAction|delimitedList|is not defined in namespace" \
    | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+//' \
    | sed -E 's/[[:space:]]+$//' \
    | sort
}

PASS=0; FAIL=0; ERR=0
declare -a SUMMARY

run_pair() {
  local name="$1"; shift
  local lk="$OUT/${name}.linkml.txt"
  local lg="$OUT/${name}.legacy.txt"
  echo "==================================================================="
  echo "[$name]  pynidm $*"
  "$LINKML_BIN" "$@" >"$lk" 2>"$OUT/${name}.linkml.err"; local rc_lk=$?
  "$LEGACY_BIN" "$@" >"$lg" 2>"$OUT/${name}.legacy.err"; local rc_lg=$?

  if [ $rc_lk -ne 0 ] || [ $rc_lg -ne 0 ]; then
    echo "  ERROR  linkml rc=$rc_lk  legacy rc=$rc_lg  (see $OUT/${name}.*.err)"
    ERR=$((ERR+1)); SUMMARY+=("ERROR  $name (rc linkml=$rc_lk legacy=$rc_lg)")
    return
  fi

  local nlk nlg
  nlk=$(_norm <"$lk"); nlg=$(_norm <"$lg")
  local clk clg
  clk=$(printf '%s\n' "$nlk" | grep -c . )
  clg=$(printf '%s\n' "$nlg" | grep -c . )

  if [ "$nlk" == "$nlg" ]; then
    echo "  MATCH  ($clk normalized lines both sides)"
    PASS=$((PASS+1)); SUMMARY+=("MATCH  $name  ($clk lines)")
  else
    echo "  DIFF   linkml=$clk lines  legacy=$clg lines"
    diff <(printf '%s\n' "$nlg") <(printf '%s\n' "$nlk") | head -20 \
      | sed 's/^/    /'
    echo "    (< legacy, > linkml; full outputs in $OUT/${name}.*.txt)"
    FAIL=$((FAIL+1)); SUMMARY+=("DIFF   $name  (linkml=$clk legacy=$clg)")
  fi
}

# --- a tiny SPARQL query file for the -q mode ------------------------------
QF="$OUT/count.rq"
cat >"$QF" <<'SPARQL'
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?s WHERE { ?s a prov:Person } ORDER BY ?s
SPARQL

# --- the test matrix -------------------------------------------------------
# demographic/assessment queries over ABIDE NYU
run_pair participants        query -nl "$NYU" -p
run_pair instruments         query -nl "$NYU" -i
run_pair instrument_vars     query -nl "$NYU" -iv
run_pair sparql_persons      query -nl "$NYU" -q "$QF"
run_pair rest_projects       query -nl "$NYU" -u /projects
run_pair rest_subjects       query -nl "$NYU" -u /subjects
run_pair fields_age          query -nl "$NYU" -gf age

# data-element / brain-volume queries over the ds002411 FreeSurfer derivatives
run_pair dataelements        query -nl "$ON" -de
run_pair dataelements_bvols  query -nl "$ON" -debv
run_pair brainvols           query -nl "$ON" -bv

# --- summary ---------------------------------------------------------------
echo "==================================================================="
echo "SUMMARY   MATCH=$PASS  DIFF=$FAIL  ERROR=$ERR"
for line in "${SUMMARY[@]}"; do echo "  $line"; done
echo "outputs saved under: $OUT"
[ $FAIL -eq 0 ] && [ $ERR -eq 0 ]
