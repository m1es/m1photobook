#!/usr/bin/env bash

set -euo pipefail
shopt -s nullglob

DIR="."
OUT_DIR="./renamed"
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n)
      DRY_RUN=true
      shift
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    *)
      DIR="$1"
      shift
      ;;
  esac
done

TMP_SORTABLE=$(mktemp)
TMP_UNSORTABLE=$(mktemp)
TMP_ORDERED=$(mktemp)

echo "Scanning files in: $DIR"
echo "Output directory: $OUT_DIR"
echo

scanned=0
sortable=0
unsortable=0

# Scan files (ignore dotfiles like .DS_Store)
while IFS= read -r -d '' file; do
  ((scanned++))
  base=$(basename "$file")

  # Only DateTimeOriginal makes a file sortable
  date=$(exiftool -s -s -s -DateTimeOriginal "$file")

  if [[ -z "$date" ]]; then
    ((unsortable++))
    echo "[$scanned] No DateTimeOriginal → UNSORTABLE: $base"
    echo "$file" >> "$TMP_UNSORTABLE"
    continue
  fi

  ((sortable++))
  sortable_date=$(echo "$date" | sed -E 's/[^0-9]//g')
  echo "[$scanned] Sortable: $base → $date"
  echo "$sortable_date|$file" >> "$TMP_SORTABLE"

done < <(
  find "$DIR" \
    -maxdepth 1 \
    -type f \
    ! -name '.*' \
    -print0
)

echo
echo "Scanned:     $scanned files"
echo "Sortable:    $sortable files"
echo "Unsortable:  $unsortable files"
echo

# Sort sortable files by DateTimeOriginal
sort "$TMP_SORTABLE" > "${TMP_SORTABLE}.sorted"

# Build final ordered list:
# 1) sorted files
# 2) unsortable files
cut -d'|' -f2 "${TMP_SORTABLE}.sorted" > "$TMP_ORDERED"
cat "$TMP_UNSORTABLE" >> "$TMP_ORDERED"

total=$(wc -l < "$TMP_ORDERED" | tr -d ' ')
pad_width=${#total}

mkdir -p "$OUT_DIR"

echo "Copying files to: $OUT_DIR"
echo

counter=1
while IFS= read -r file; do
  base=$(basename "$file")
  ext="${base##*.}"

  num=$(printf "%0*d" "$pad_width" "$counter")
  newname="${num}.${ext}"

  if $DRY_RUN; then
    echo "[$counter/$total] DRY-RUN: $base → $OUT_DIR/$newname"
  else
    echo "[$counter/$total] Copying: $base → $OUT_DIR/$newname"
    cp -n "$file" "$OUT_DIR/$newname"
  fi

  ((counter++))
done < "$TMP_ORDERED"

# Cleanup
rm -f "$TMP_SORTABLE" "$TMP_SORTABLE.sorted" "$TMP_UNSORTABLE" "$TMP_ORDERED"

echo
if $DRY_RUN; then
  echo "Dry-run complete. No files were copied."
else
  echo "Done. Files copied successfully."
fi

