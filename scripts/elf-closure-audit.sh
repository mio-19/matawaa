#!/usr/bin/env bash
# elf-closure-audit -- static linkage audit for a Nix closure.
#
# Finds the two failure modes that black-screen a device without any
# compile-time error:
#
#   1. a shared object that DT_NEEDED's a library which is not in the
#      closure at all (missing NEEDED);
#   2. a shared object with undefined symbols that none of the libraries
#      in its own transitive DT_NEEDED closure provide -- the library that
#      defines them exists in the image but was never linked (this is what
#      produced "undefined symbol: hybris_gralloc_release" and
#      "undefined symbol: _ZTI22HWComposerNativeWindow" for the hoki QPA
#      plugin).
#
# Both are invisible to the compiler and to a plain `nix build`; they only
# appear when the loader dlopen()s the object on the device.
#
# Usage:
#   scripts/elf-closure-audit.sh [options] STORE-PATH...
#
#   STORE-PATH may be a system closure root (/nix/store/...-nixos-system-...)
#   or any package; its runtime closure is scanned.
#
# Options:
#   --only REGEX   only audit ELF files whose path matches REGEX
#                  (e.g. --only 'libhwcomposer|libhybris|asteroid-launcher')
#   --all-arches   audit every architecture, not just ARM (useful when the
#                  closure mixes build-platform tools into the image)
#   --verbose      list every audited file
#
# Exit status: 0 when no findings, 1 when findings exist, 2 on usage error.
#
# Known-benign undefined symbols are filtered: the C++/Itanium ABI
# bookkeeping symbols (_ITM_*, __cxa_pure_virtual, _ZGTt*) and glibc
# runtime internals. They are satisfied by libstdc++/libc at load time and
# never indicate a missing link.
set -uo pipefail

ONLY=""
ALL_ARCHES=0
VERBOSE=0
ROOTS=()

die() {
  printf 'elf-closure-audit: %s\n' "$1" >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --only)
      [ $# -ge 2 ] || die "--only needs an argument"
      ONLY="$2"
      shift 2
      ;;
    --only=*)
      ONLY="${1#--only=}"
      shift
      ;;
    --all-arches)
      ALL_ARCHES=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h | --help)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      ROOTS+=("$1")
      shift
      ;;
  esac
done

[ ${#ROOTS[@]} -gt 0 ] || die "no store path given"
command -v readelf >/dev/null || die "readelf not found (binutils)"
command -v nm >/dev/null || die "nm not found (binutils)"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/elf-closure-audit.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# --- 1. collect the closure and its ELF files ------------------------------
nix-store -qR "${ROOTS[@]}" 2>/dev/null | sort -u >"$WORK/closure.txt" ||
  die "cannot query the closure of ${ROOTS[*]}"

: >"$WORK/elfs.txt"
while read -r store_path; do
  [ -d "$store_path" ] || continue
  find -L "$store_path" -type f \
    \( -path '*/lib/*.so*' -o -path '*/bin/*' -o -path '*/sbin/*' \) \
    2>/dev/null
done <"$WORK/closure.txt" | sort -u >"$WORK/candidates.txt"

while read -r f; do
  [ "$(head -c4 "$f" 2>/dev/null | od -An -tx1 | tr -d ' \n')" = "7f454c46" ] || continue
  if [ "$ALL_ARCHES" -eq 0 ]; then
    machine=$(readelf -h "$f" 2>/dev/null | sed -n 's/.*Machine:[[:space:]]*//p' | head -1)
    case "$machine" in
      *ARM*) ;;
      *) continue ;;
    esac
  fi
  echo "$f"
done <"$WORK/candidates.txt" >"$WORK/all-elfs.txt"

# The soname index must always cover the whole closure; --only narrows the
# set of objects that are *audited*, not the set of libraries available to
# resolve their DT_NEEDED entries.
if [ -n "$ONLY" ]; then
  grep -E "$ONLY" "$WORK/all-elfs.txt" >"$WORK/elfs.txt" || true
else
  cp "$WORK/all-elfs.txt" "$WORK/elfs.txt"
fi

total=$(wc -l <"$WORK/elfs.txt")
[ "$total" -gt 0 ] || die "no matching ELF files in the closure"
printf 'auditing %d ELF file(s) of %d in the closure\n' \
  "$total" "$(wc -l <"$WORK/all-elfs.txt")"

# --- 2. index: soname -> defining file -------------------------------------
: >"$WORK/index.tsv"
while read -r f; do
  so=$(readelf -d --wide "$f" 2>/dev/null | sed -n 's/.*(SONAME).*\[\(.*\)\]/\1/p' | head -1)
  [ -n "$so" ] && printf '%s\t%s\n' "$so" "$f" >>"$WORK/index.tsv"
done <"$WORK/all-elfs.txt"
sort -u "$WORK/index.tsv" -o "$WORK/index.tsv"

# --- 3. audit ---------------------------------------------------------------
: >"$WORK/missing-needed.tsv"
: >"$WORK/unresolved.tsv"

while read -r f; do
  [ "$VERBOSE" -eq 1 ] && printf '  %s\n' "$f"

  # 3a. every direct NEEDED must exist somewhere in the scanned set
  while read -r so; do
    [ -z "$so" ] && continue
    if ! cut -f1 "$WORK/index.tsv" | grep -qxF "$so"; then
      printf '%s\t%s\n' "$f" "$so" >>"$WORK/missing-needed.tsv"
    fi
  done < <(readelf -d --wide "$f" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p')

  # 3b. walk the transitive DT_NEEDED closure of this object
  declare -A dep=()
  dep["$f"]=1
  queue=("$f")
  while [ ${#queue[@]} -gt 0 ]; do
    cur="${queue[0]}"
    queue=("${queue[@]:1}")
    while read -r so; do
      [ -z "$so" ] && continue
      p=$(awk -F'\t' -v k="$so" '$1==k{print $2; exit}' "$WORK/index.tsv")
      [ -z "$p" ] && continue
      [ -n "${dep[$p]:-}" ] && continue
      dep["$p"]=1
      queue+=("$p")
    done < <(readelf -d --wide "$cur" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p')
  done

  # 3c. undefined symbols minus everything the closure defines
  : >"$WORK/defs.tmp"
  for d in "${!dep[@]}"; do
    nm -D --defined-only "$d" 2>/dev/null | awk 'NF{print $NF}' | sed 's/@.*//'
  done | sort -u >"$WORK/defs.tmp"

  readelf -Ws --wide "$f" 2>/dev/null |
    awk '$7=="UND" && $8!="" {print $8}' |
    sed 's/@.*//' | sort -u |
    grep -vE '^(_ITM_.*|__gmon_start__|__cxa_finalize|__cxa_pure_virtual|_Jv_RegisterClasses|_ZGTt.*)$' |
    comm -23 - "$WORK/defs.tmp" |
    sed "s|^|$f\t|" >>"$WORK/unresolved.tsv"

  unset dep
done <"$WORK/elfs.txt"

# --- 4. report --------------------------------------------------------------
missing=$(wc -l <"$WORK/missing-needed.tsv")
unresolved=$(wc -l <"$WORK/unresolved.tsv")

if [ "$missing" -eq 0 ] && [ "$unresolved" -eq 0 ]; then
  printf 'OK: %d ELF file(s), every NEEDED entry resolvable, every symbol supplied by its own dependency closure\n' "$total"
  exit 0
fi

if [ "$missing" -gt 0 ]; then
  printf '\n== DT_NEEDED libraries missing from the closure ==\n'
  printf '   (the loader will fail with "cannot open shared object file")\n'
  sort -u "$WORK/missing-needed.tsv" |
    while IFS=$'\t' read -r f so; do
      printf '  %s\n      needs %s\n' "$f" "$so"
    done
fi

if [ "$unresolved" -gt 0 ]; then
  printf '\n== undefined symbols not provided by the object'"'"'s own DT_NEEDED closure ==\n'
  printf '   (the defining library exists in the image but was never linked;\n'
  printf '    the loader reports "undefined symbol: <name>" on dlopen)\n'
  sort -u "$WORK/unresolved.tsv" |
    while IFS=$'\t' read -r f sym; do
      printf '  %s\n      %s\n' "$f" "$sym"
    done
fi

printf '\nFAIL: %d missing-NEEDED entr(ies), %d unresolved symbol(s)\n' "$missing" "$unresolved"
exit 1
