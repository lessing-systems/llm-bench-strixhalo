#!/usr/bin/env bash
# download-models.sh [group ...]
#
# Downloads every model that was benchmarked on Strix Halo (results/strix-halo-395/), skipping any file that is already
# there. Files land where profiles/strix-halo-395.sh and launch/*/docker-compose.yml expect them, under $MODELS_DIR
# (default ~/models). Nothing is ever overwritten or re-downloaded; an interrupted download resumes (hf CLI).
#
#   groups (default: all, ~490 GB; pick what you need):
#     swift-halogen   ~100 GB  the winner: Swift-1.5 Flash-Next IQ4_XS GGUF + halogen draft head and tokenizer
#     halogen-base    ~120 GB  baseline/#2: halogen's own Flash-Next checkpoint (v2 + n-gram table) + head + tokenizer
#     llamacpp        ~260 GB  llama.cpp runs: unsloth UD-IQ4_XS (+ MTP heads), ISTA GSQ-RCO IQ3_S, Swift GSQ-RCO IQ3_XXS
#     dense-ref         12 GB  Swift-1.5 Qwen3.8-27B GSQ-RCO IQ3_S + MTP (dense reference)
#
#   DRY_RUN=1   only print what is present and what WOULD be downloaded
#   VERIFY=1    also check sha256 of every file in the selected groups against Hugging Face (reads all of it)
#   MODELS_DIR  target root (default ~/models)       HF_TOKEN  optional, faster and rate-limit free
#
# Licenses differ per model (Swift: free below US$1M annual revenue, Swift Open License v1.0); read the model cards.
set -euo pipefail
MODELS_DIR=${MODELS_DIR:-$HOME/models}
GROUPS_ALL=(swift-halogen halogen-base llamacpp dense-ref)
SEL=("$@"); (( ${#SEL[@]} )) || SEL=("${GROUPS_ALL[@]}")

HF_CMD=""
if command -v hf >/dev/null; then HF_CMD=hf
elif [[ ${DRY_RUN:-0} != 1 ]]; then
  VENV=${HF_VENV:-$MODELS_DIR/.hf-venv}
  [[ -x $VENV/bin/hf ]] || { echo "installing huggingface_hub into $VENV"; python3 -m venv "$VENV" && "$VENV/bin/pip" install -q huggingface_hub; }
  HF_CMD=$VENV/bin/hf
fi

PLAN=()   # repo|file-in-repo|target-dir  (file may be a dir/* glob for tokenizer)
add() { PLAN+=("$1|$2|$MODELS_DIR/$3"); }
shards() { local repo=$1 dir=$2 prefix=$3 n=$4 sub=$5 i; for ((i=1;i<=n;i++)); do
            add "$repo" "${sub:+$sub/}$(printf '%s-%05d-of-%05d.gguf' "$prefix" "$i" "$n")" "$dir"; done; }

for g in "${SEL[@]}"; do case $g in
  swift-halogen)   # Swift Open License v1.0
    shards ukisai/Swift-1.5-Qwen3.8-Flash-Next-GGUF swift-flashnext-gguf Swift-1.5-Qwen3.8-Flash-Next-IQ4_XS 3 IQ4_XS
    add peonist-ai/halogen-qwen3.8-flash-next qwen38-flash-next-mtp.hgn halogen-qwen38-flash-next
    add peonist-ai/halogen-qwen3.8-flash-next 'tokenizer/*' halogen-qwen38-flash-next ;;
  halogen-base)
    add peonist-ai/halogen-qwen3.8-flash-next qwen38-flash-next-v2.hgn halogen-qwen38-flash-next
    add peonist-ai/halogen-qwen3.8-flash-next qwen38-flash-next-ngram.hgn halogen-qwen38-flash-next
    add peonist-ai/halogen-qwen3.8-flash-next qwen38-flash-next-mtp.hgn halogen-qwen38-flash-next
    add peonist-ai/halogen-qwen3.8-flash-next 'tokenizer/*' halogen-qwen38-flash-next ;;
  llamacpp)
    shards unsloth/Qwen3.8-Flash-Next-GGUF Qwen3.8-UD_IQ4_XS Qwen3.8-Flash-Next-UD-IQ4_XS 3 UD-IQ4_XS
    # MTP heads: unsloth re-uploaded them 2026-10-05 (new weights, same size). What Hugging Face serves now is the new head.
    add unsloth/Qwen3.8-Flash-Next-GGUF MTP/mtp-Qwen3.8-Flash-Next-Q8_0.gguf flashnext-mtp/unsloth-20261005
    add unsloth/Qwen3.8-Flash-Next-GGUF MTP/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf Qwen3.8-UD_IQ4_XS
    shards ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF flashnext Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S 2 IQ3_S
    shards ukisai/Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-GGUF swift-flashnext/IQ3_XXS Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS 2 "" ;;
  dense-ref)
    add ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf swift27b ;;
  *) echo "unknown group '$g' (known: ${GROUPS_ALL[*]})"; exit 1 ;;
esac; done

# present = the file exists (a glob counts as present when its dir has tokenizer.json)
present() { local f=$1 d=$2; [[ $f == 'tokenizer/*' ]] && [[ -f $d/tokenizer/tokenizer.json ]] || [[ $f != *'*' && -e $d/$f ]]; }

todo=0
echo "target: $MODELS_DIR   groups: ${SEL[*]}"
for e in "${PLAN[@]}"; do IFS='|' read -r repo f dir <<<"$e"
  if present "$f" "$dir"; then echo "  present   $dir/$f"; continue; fi
  todo=$((todo+1))
  if [[ ${DRY_RUN:-0} == 1 ]]; then echo "  WOULD DOWNLOAD  $repo  $f  ->  $dir"; continue; fi
  avail=$(( $(df -Pk "$(mkdir -p "$dir" && echo "$dir")" | awk 'NR==2{print $4}') / 1048576 ))
  echo "  downloading $repo $f  ($avail GB free in $dir)"
  if [[ $f == *'*' ]]; then "$HF_CMD" download "$repo" --include "$f" --local-dir "$dir" >/dev/null
  else "$HF_CMD" download "$repo" "$f" --local-dir "$dir" >/dev/null; fi
done
(( todo )) && [[ ${DRY_RUN:-0} == 1 ]] && { echo "$todo file(s) missing; rerun without DRY_RUN=1 to download"; }
(( todo == 0 )) && echo "everything already present"

if [[ ${VERIFY:-0} == 1 && ${DRY_RUN:-0} != 1 ]]; then
  echo "verifying sha256 against Hugging Face (reads every file)"
  printf '%s\n' "${PLAN[@]}" | python3 -I -c '
import hashlib, json, sys, urllib.request
bad = 0; trees = {}
for line in sys.stdin:
    repo, f, d = line.rstrip("\n").split("|")
    if f.endswith("*"): continue
    if repo not in trees:
        trees[repo] = {e["path"]: (e.get("lfs") or {}).get("oid") for e in json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=1")) if e["type"] == "file"}
    h = hashlib.sha256()
    with open(f"{d}/{f}", "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""): h.update(c)
    ok = h.hexdigest() == trees[repo].get(f); bad += not ok
    print("  ok " if ok else "  BAD", f"{d}/{f}")
sys.exit(1 if bad else 0)'
fi
